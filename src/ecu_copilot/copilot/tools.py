"""The five tools. Their docstrings are not comments - they are the tool descriptions the
model reads, so they say *when* to use the tool and what comes back.

Each tool returns a JSON string. Errors are returned as JSON too (never raised): the
model should see "station 7 does not exist" and recover, not crash the request.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from anthropic import beta_tool
from opentelemetry import trace

from .. import config
from ..rag.index import DocumentIndex
from .twin_client import TwinClient

tracer = trace.get_tracer("ecu-copilot.tools")

# Shared backends, created once per process (api.py may replace them, tests inject fakes).
_index: DocumentIndex | None = None
_twin: TwinClient | None = None
_bom: dict | None = None


def configure(index: DocumentIndex | None = None, twin: TwinClient | None = None, bom_file: Path | None = None) -> None:
    global _index, _twin, _bom
    if index is not None:
        _index = index
    if twin is not None:
        _twin = twin
    bom_file = bom_file or (config.DOCS_DIR / "BOM-DCU.json")
    if bom_file.exists():
        _bom = json.loads(bom_file.read_text(encoding="utf-8"))


def _get_index() -> DocumentIndex:
    global _index
    if _index is None:
        _index = DocumentIndex().load()
    return _index


def _get_twin() -> TwinClient:
    global _twin
    if _twin is None:
        _twin = TwinClient()
    return _twin


def _dumps(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _error(msg: str) -> str:
    return _dumps({"error": msg})


# ------------------------------------------------------------------------------------
@beta_tool
def search_docs(query: str, k: int = 5) -> str:
    """Search the engineering documentation: EOL test specification (limits, failure codes,
    test conditions), component datasheets (MCU, motor driver), process FMEA, product change
    notifications (PCN, end-of-life parts) and work instructions (pseudo failures, 8D report).

    Use it whenever an answer needs a limit, a rule, a root cause or a procedure. The documents
    are in English - write the query in English. Returns the best matching sections with a
    citation like "TS-DCU-EOL §4.2" that you must quote in your answer.

    Args:
        query: What to look for, in English, e.g. "quiescent current limit variant B".
        k: Number of sections to return (1-8).
    """
    with tracer.start_as_current_span("tool.search_docs") as span:
        span.set_attribute("query", query)
        try:
            hits = _get_index().search(query, k=max(1, min(int(k), 8)))
        except FileNotFoundError as e:
            return _error(str(e))
        span.set_attribute("hits", len(hits))
        return _dumps([{k_: v for k_, v in h.items() if k_ != "score"} for h in hits])


@beta_tool
def get_station_stats(minutes: int = 10) -> str:
    """Get live end-of-line test statistics from the test line for the last N minutes, grouped
    by station and variant: units tested, failure rate in percent, failure codes with counts,
    mean PCB temperature (°C), mean background noise (dB(A)), mean quiescent current (µA),
    mean acoustic score.

    Use it first for any question about current failure rates, trends or "what is going on".
    Compare two windows (e.g. 10 and 60 minutes) to see whether something changed recently.

    Args:
        minutes: Time window in minutes (1-240).
    """
    with tracer.start_as_current_span("tool.get_station_stats") as span:
        span.set_attribute("minutes", minutes)
        try:
            return _dumps(_get_twin().stats(minutes=max(1, min(int(minutes), 240))))
        except Exception as e:  # noqa: BLE001 - the model should see the failure, not a traceback
            return _error(f"twin not reachable: {e}")


@beta_tool
def get_recent_results(
    station: int | None = None,
    variant: str | None = None,
    minutes: int = 10,
    only_failed: bool = True,
    limit: int = 40,
) -> str:
    """Get individual test results (newest first) with all measurements, serial number, lot and
    failure code. Use it after get_station_stats to look at the actual units: which lots fail,
    how far a measurement is above its limit, whether failures cluster in time.
    The response also contains a summary by lot and by failure code.

    Args:
        station: Station number 1-3, or omit for all stations.
        variant: "A" or "B", or omit for both.
        minutes: Time window in minutes (1-240).
        only_failed: True returns only failed units (default), False returns all units.
        limit: Maximum number of results (1-200).
    """
    with tracer.start_as_current_span("tool.get_recent_results") as span:
        span.set_attribute("station", station or 0)
        try:
            rows = _get_twin().results(
                station=station,
                variant=variant,
                minutes=max(1, min(int(minutes), 240)),
                only_failed=only_failed,
                limit=max(1, min(int(limit), 40)),  # raw rows are expensive context; summaries come from the engineering tools
            )
        except Exception as e:  # noqa: BLE001
            return _error(f"twin not reachable: {e}")
        by_lot = Counter(r["lot"] for r in rows)
        by_code = Counter(r["failure_code"] for r in rows if r.get("failure_code"))
        return _dumps({"count": len(rows), "by_lot": dict(by_lot), "by_failure_code": dict(by_code), "results": rows})


@beta_tool
def lookup_part(query: str) -> str:
    """Look up a component in the bill of materials (BOM) of DCU-A1 / DCU-B2 by part number,
    board position (e.g. "U7", "J3") or description keyword. Returns lifecycle status
    (active, end_of_life, qualification_in_progress), PCN reference, last-time-buy date,
    alternatives and notes. Use it for questions about parts, obsolescence or replacements.

    Args:
        query: Part number, position or keyword, e.g. "HB4821", "U7", "motor driver".
    """
    with tracer.start_as_current_span("tool.lookup_part") as span:
        span.set_attribute("query", query)
        if _bom is None:
            configure()
        q = query.lower().strip()
        hits = [
            p
            for p in (_bom or {}).get("parts", [])
            if q in p["part_number"].lower() or q == p["position"].lower().split(" ")[0] or q in p["description"].lower()
        ]
        if not hits:
            return _error(f"no BOM entry matches '{query}'")
        return _dumps(hits)


@beta_tool
def draft_8d_report(
    title: str,
    d2_problem: str,
    d3_containment: str,
    d4_root_cause: str,
    d5_corrective_action: str,
    evidence_citations: list[str],
    affected_units: int = 0,
    affected_lots: list[str] | None = None,
) -> str:
    """Create a draft 8D report (disciplines D1-D5 filled, D6-D8 left open) and save it as a
    markdown file. Call it only when the user asks for an 8D report, a Problemlösungsbericht
    or an escalation document, and only after you have gathered evidence with the other tools.

    Args:
        title: Short problem title, e.g. "E-204 increase station 2 variant B".
        d2_problem: Problem description: station, variant, failure code, time window, rate before/after.
        d3_containment: Immediate containment (units blocked / re-tested, station condition corrected).
        d4_root_cause: Confirmed or suspected root cause with the evidence.
        d5_corrective_action: Proposed corrective action with owner role and timing.
        evidence_citations: Document citations used, e.g. ["TS-DCU-EOL §4.2", "FMEA-DCU-B2 item 11"].
        affected_units: Number of affected units, if known.
        affected_lots: Lot numbers involved, if any.
    """
    with tracer.start_as_current_span("tool.draft_8d_report"):
        config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC)
        path = config.REPORTS_DIR / f"8D-{ts:%Y%m%d-%H%M%S}.md"
        lots = ", ".join(affected_lots or []) or "n/a"
        body = f"""# 8D Report (draft) – {title}

Created: {ts:%Y-%m-%d %H:%M} UTC · Status: DRAFT (D1–D5), generated by ECU Copilot, to be reviewed by Test Engineering

| Discipline | Content |
|---|---|
| D1 Team | Test engineering (owner), quality engineering, production line lead – to be named |
| D2 Problem description | {d2_problem} Affected units: {affected_units}. Lots: {lots}. |
| D3 Containment | {d3_containment} |
| D4 Root cause | {d4_root_cause} |
| D5 Corrective action | {d5_corrective_action} |
| D6 Implementation | open |
| D7 Prevention | open |
| D8 Closure | open |

Evidence: {", ".join(evidence_citations) or "none cited"}
"""
        path.write_text(body, encoding="utf-8")
        return _dumps({"saved_to": str(path), "markdown": body})


# ---- deterministic engineering tools (V2) -----------------------------------------------
def _window(station: int | None, variant: str | None, minutes: int) -> list[dict]:
    return _get_twin().results(station=station, variant=variant, minutes=max(1, min(int(minutes), 240)), only_failed=False, limit=10000)


@beta_tool
def check_validity(station: int, variant: str | None = None, minutes: int = 10) -> str:
    """Apply the specification's validity rules to every test result of a station in a time window:
    per failure code, how many FAIL verdicts are INVALID per spec (board temperature outside the
    18–32 °C window for E-204, background noise above 45 dB(A) for E-310) and how many remain real
    FAILs after that. Includes the rule references and example units. Call this BEFORE you say
    anything about validity, pseudo failures or the test environment. INVALID means "the unit
    cannot be assessed from this result", not "the unit is good".

    Args:
        station: Station number 1-3.
        variant: "A" or "B", or omit for both.
        minutes: Time window in minutes (1-240).
    """
    with tracer.start_as_current_span("tool.check_validity"):
        try:
            from ..engineering.validity import check_validity as _cv

            out = _cv(_window(station, variant, minutes))
            out["scope"] = {"station": station, "variant": variant, "window_minutes": minutes}
            return _dumps(out)
        except Exception as e:  # noqa: BLE001
            return _error(f"check_validity failed: {e}")


@beta_tool
def detect_change(station: int, variant: str | None = None, metric: str = "failure_rate", minutes: int = 60, bucket_s: int = 60) -> str:
    """Find when and how strongly a metric changed in a time window (two-sample change-point scan over
    time buckets): onset time, level before/after, relative change, z-score and whether the change is
    significant. Metrics: failure_rate, quiescent_current_ua, board_temp_c, ambient_noise_db,
    acoustic_score. Call this BEFORE you say "since X minutes" or "rising" - do not estimate trends
    yourself from two windows.

    Args:
        station: Station number 1-3.
        variant: "A" or "B", or omit for both.
        metric: Which metric to scan (see list above).
        minutes: Window to scan in minutes (10-240).
        bucket_s: Bucket size in seconds (30-600).
    """
    with tracer.start_as_current_span("tool.detect_change"):
        try:
            from ..engineering.change import detect_change as _dc

            out = _dc(_window(station, variant, max(10, minutes)), metric=metric, bucket_s=max(30, min(int(bucket_s), 600)))
            out["scope"] = {"station": station, "variant": variant, "window_minutes": minutes}
            return _dumps(out)
        except Exception as e:  # noqa: BLE001
            return _error(f"detect_change failed: {e}")


@beta_tool
def cluster_failures(
    station: int | None = None, variant: str | None = None, by: str = "lot", code: str | None = None, minutes: int = 30
) -> str:
    """Check whether failures concentrate in one group - by lot, firmware, station, hour or code -
    with the references that make concentration meaningful: lift (share of failures vs share of
    tested units), failure rate inside vs outside the group (rate ratio) and a z-score. Call this
    BEFORE you say a lot, a firmware version or a station is affected.

    Args:
        station: Station number 1-3, or omit for all stations.
        variant: "A" or "B", or omit for both.
        by: Grouping: lot | firmware | station | hour | variant | code.
        code: Restrict to one failure code, e.g. "E-120"; omit for all failures.
        minutes: Time window in minutes (1-240).
    """
    with tracer.start_as_current_span("tool.cluster_failures"):
        try:
            from ..engineering.cluster import cluster_failures as _cf

            out = _cf(_window(station, variant, minutes), by=by, code=code)
            out["scope"] = {"station": station, "variant": variant, "window_minutes": minutes}
            return _dumps(out)
        except Exception as e:  # noqa: BLE001
            return _error(f"cluster_failures failed: {e}")


@beta_tool
def describe_signal(station: int, variant: str | None = None, minutes: int = 20) -> str:
    """Compact descriptors of the measurements in a window: mean/min/max and trend per measurement,
    the relation between quiescent current and station temperature (does Iq follow T1 as the leakage
    model predicts, or are they decoupled - the signature of a faulty temperature sensor), and flags
    for conditions outside the specification. Use this instead of reading raw result lists.

    Args:
        station: Station number 1-3.
        variant: "A" or "B", or omit for both.
        minutes: Time window in minutes (1-240).
    """
    with tracer.start_as_current_span("tool.describe_signal"):
        try:
            from ..engineering.describe import describe_signal as _ds

            out = _ds(_window(station, variant, minutes))
            out["scope"] = {"station": station, "variant": variant, "window_minutes": minutes}
            return _dumps(out)
        except Exception as e:  # noqa: BLE001
            return _error(f"describe_signal failed: {e}")


TOOLS_V1 = [search_docs, get_station_stats, get_recent_results, lookup_part, draft_8d_report]
TOOLS_V2 = [check_validity, detect_change, cluster_failures, describe_signal, *TOOLS_V1]
ALL_TOOLS = TOOLS_V2


def tools_for(profile: str) -> list:
    return TOOLS_V1 if profile == "v1" else TOOLS_V2
