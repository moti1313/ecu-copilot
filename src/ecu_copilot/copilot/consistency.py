"""Consistency check of the final assessments - runs after the model, next to provenance/support. No LLM.

Concept: design/CONCEPT.md §11 ("markieren, nicht verbieten"). The check never sets a cause, never changes an
assessment and never changes derive_finding(). It only makes certain unsupported or contradictory
commitments visible, so the engineer (and the benchmark) can see them.

Inputs are exclusively what the run stored: the report's `assessments` and the tool calls that were actually
executed (name, input, output). Nothing is recomputed from snapshots. If a check was not run in this run,
the flag says "not checked", not "contradictory".

Known limits of this first version (CONCEPT §11): assessments carry no link to their evidence, so flags are
reasoned hints, not conditions that evidence can clear; nested scopes ("station 2/B, all lots" contains a
single lot) are NOT treated as the same scope - K3 fires only on identical scope tuples; time windows are not
compared because assessments carry none.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

STATION_CAUSES = {"station_temperature", "cell_noise", "fixture", "sensor_t1"}
DEFECT_CLAIMS = {"suspected", "strong"}

TEXTS = {
    "K0": "Temperaturursache festgelegt, Sensorplausibilität (Iq↔T1) nicht geprüft",
    "K1": "Temperaturmessung dieses Messpfads in Zweifel; reale Übertemperatur nicht unabhängig belegt",
    "K2": "Gemeinsame Festlegung von Stationsursache und Bauteilverdacht benötigt getrennte Begründung",
    "K3": "Gemeinsame Festlegung benötigt getrennte Begründung; kann ein berechtigter Mehrfachfehler sein",
    "K4": "Stationsübergreifender Vergleich für dieses Los fehlt",
}
KINDS = {"K0": "coverage", "K1": "conflict", "K2": "hint", "K3": "hint", "K4": "coverage"}


@dataclass
class ConsistencyFlag:
    code: str  # K0..K4
    kind: str  # coverage | conflict | hint
    assessments: list[int]  # 0-based indices into report["assessments"]
    text: str
    detail: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------------------------
def _triple(a: dict) -> str:
    return f"{a.get('test_validity')}/{a.get('defect_indication')}/{a.get('root_cause')}"


def _scope(a: dict) -> tuple[str | None, str | None, str | None]:
    s = a.get("scope") or {}
    norm = lambda v: None if v in (None, "", "null") else str(v).strip().upper()  # noqa: E731
    return norm(s.get("station")), norm(s.get("variant")), norm(s.get("lot"))


def _ok_outputs(tool_calls: list, name: str) -> list[tuple[dict, dict]]:
    """(input, output) of successful calls of one tool - JSON output without an 'error' key."""
    out = []
    for c in tool_calls or []:
        if getattr(c, "name", None) != name:
            continue
        try:
            o = json.loads(getattr(c, "output", "") or "")
        except (TypeError, ValueError):
            continue
        if not isinstance(o, dict) or "error" in o:
            continue
        out.append((getattr(c, "input", None) or {}, o))
    return out


def _covers(called: object, claimed: str | None) -> bool:
    """A call for 'all' (None) or for exactly the claimed station/variant covers the assessment."""
    return called in (None, "", "null") or (claimed is not None and str(called).strip().upper() == claimed)


def _describe_for(a: dict, tool_calls: list) -> tuple[list[dict], str]:
    """describe_signal outputs that cover this assessment: same station, variant covered, and data in the window
    (tested > 0). describe_signal is station-bound, so an assessment without a station is never fully covered."""
    st, var, _ = _scope(a)
    calls = _ok_outputs(tool_calls, "describe_signal")
    if st is None:
        seen = sorted({str((o.get("scope") or {}).get("station", i.get("station"))) for i, o in calls})
        return [], (
            "Bewertung ohne Stationsangabe; describe_signal ist stationsbezogen"
            + (f" (ausgeführt für Station {', '.join(seen)})" if seen else " (nicht ausgeführt)")
        )
    hits, empty = [], 0
    for inp, out in calls:
        sc = out.get("scope") if isinstance(out.get("scope"), dict) else {}
        c_st, c_var = sc.get("station", inp.get("station")), sc.get("variant", inp.get("variant"))
        if str(c_st).upper() != st or not _covers(c_var, var):
            continue
        tested = out.get("tested")
        if isinstance(tested, int | float) and tested <= 0:
            empty += 1
            continue
        hits.append(out)
    if hits:
        return hits, ""
    if empty:
        return [], f"describe_signal für Station {st} lieferte keine Prüfungen im Fenster (tested = 0)"
    return [], "describe_signal wurde für diesen Geltungsbereich nicht erfolgreich ausgeführt"


def _codes_in_report(report: dict | None) -> set[str]:
    return set(re.findall(r"E-\d{3}", json.dumps(report or {}, ensure_ascii=False)))


def _lot_in_output(out: dict, lot: str | None) -> bool:
    if lot is None:
        return True
    groups = out.get("groups") if isinstance(out.get("groups"), list) else []
    names = {str((g or {}).get("group") or "").upper() for g in groups} | {str((out.get("top") or {}).get("group") or "").upper()}
    return lot in names


# ---------------------------------------------------------------------------------------------
def check_consistency(report: dict | None, tool_calls: list) -> list[ConsistencyFlag]:
    flags: list[ConsistencyFlag] = []
    assessments = (report or {}).get("assessments") or []
    if not assessments:
        return flags

    for i, a in enumerate(assessments):
        validity = str(a.get("test_validity") or "")
        defect = str(a.get("defect_indication") or "")
        cause = str(a.get("root_cause") or "")
        st, var, lot = _scope(a)

        if validity == "invalid_temperature":
            described, coverage_note = _describe_for(a, tool_calls)
            if not described:
                flags.append(ConsistencyFlag("K0", KINDS["K0"], [i], TEXTS["K0"], coverage_note))
            # K1 compares assessments with each other and with stored signal output - independent of K0
            decoupled = [d for d in described if str(d.get("iq_t1_relation") or "") == "decoupled"]
            coupled = [d for d in described if str(d.get("iq_t1_relation") or "") == "iq_follows_t1"]
            same_scope_sensor = [
                j for j, b in enumerate(assessments) if j != i and _scope(b) == (st, var, lot) and b.get("root_cause") == "sensor_t1"
            ]
            if coupled and not decoupled:
                # The quiescent current follows the reported temperature: the current path independently supports
                # real heating, so overtemperature IS evidenced even if the T1 sensor is also suspected (S06 pattern).
                # K3 may still mark the pair as a hint; K1 would be a false conflict here.
                pass
            elif decoupled or same_scope_sensor:
                why = []
                if decoupled:
                    why.append(f"describe_signal: iq_t1_relation=decoupled (Korrelation {decoupled[0].get('iq_t1_correlation')})")
                if same_scope_sensor:
                    why.append(f"Bewertung {same_scope_sensor[0] + 1} nennt sensor_t1 für denselben Geltungsbereich")
                flags.append(ConsistencyFlag("K1", KINDS["K1"], [i, *same_scope_sensor], TEXTS["K1"], "; ".join(why)))

        if cause in STATION_CAUSES and defect in DEFECT_CLAIMS:
            flags.append(ConsistencyFlag("K2", KINDS["K2"], [i], TEXTS["K2"], f"root_cause={cause} mit defect_indication={defect}"))

        if cause == "connector_lot" and defect in DEFECT_CLAIMS:
            codes = _codes_in_report(report)
            cross = [
                (inp, out)
                for inp, out in _ok_outputs(tool_calls, "cluster_failures")
                if inp.get("station") in (None, "", "null")
                and str(out.get("by") or inp.get("by") or "") == "lot"
                and _covers(inp.get("variant"), var)
                and (out.get("code") in (None, "") or str(out.get("code")) in codes)  # all failures, or a code the report talks about
                and _lot_in_output(out, lot)
            ]
            if not cross:
                flags.append(
                    ConsistencyFlag(
                        "K4",
                        KINDS["K4"],
                        [i],
                        TEXTS["K4"],
                        f"kein erfolgreicher cluster_failures-Aufruf ohne Stationsfilter (by=lot, Variante {var or 'alle'}, "
                        f"alle Codes oder ein im Report genannter Code), der Los {lot or '?'} ausweist",
                    )
                )

    # K3: identical scope tuple, one invalid_*, the other suspected/strong
    for i, a in enumerate(assessments):
        if not str(a.get("test_validity") or "").startswith("invalid"):
            continue
        for j, b in enumerate(assessments):
            if j == i or _scope(b) != _scope(a) or b.get("defect_indication") not in DEFECT_CLAIMS:
                continue
            flags.append(
                ConsistencyFlag(
                    "K3",
                    KINDS["K3"],
                    sorted([i, j]),
                    TEXTS["K3"],
                    f"Bewertung {i + 1}: {_triple(a)} · Bewertung {j + 1}: {_triple(b)}",
                )
            )
    # de-duplicate K3 pairs (i,j) and (j,i) can only arise if both are invalid and suspected - keep first
    seen, unique = set(), []
    for f in flags:
        key = (f.code, tuple(f.assessments))
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)
    return unique


def summarize(flags: list[ConsistencyFlag]) -> dict:
    return {
        "count": len(flags),
        "flags": [f.as_dict() for f in flags],
        "method": (
            "CONCEPT §11: K0/K4 Abdeckung, K1 Widerspruch, K2/K3 Prüfhinweis; "
            "nur gespeicherte Werkzeugaufrufe; Befund und Bewertungen unverändert"
        ),
    }
