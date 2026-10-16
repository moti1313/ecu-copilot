"""Scenario benchmark: B0 / B1 / V1 / V1S / V2 on scenarios with known truth, repeated runs.
    uv run python evals/bench.py [--scenarios S01,S08] [--systems b0,b1,v1,v1s,v2] [--repeats 3] [--model gpt-5]

Method (design/CONCEPT.md §5, corrected after review of run 1):
- Per scenario: inject the faults once, wait `settle_s`, check solvability, then take ONE SNAPSHOT of the
  twin (every result of the last 4 h, fixed reference time). All systems and all repeats run against that
  snapshot, so "same fault" also means "same data". The live twin keeps running but is not consulted.
- Scores per run: assessment / finding / root-cause correctness, abstention, required tools, citation
  validity, provenance and support rates (verify.py), must-cite, next-test keywords, latency, cost.
- Three separate rates per system: completion (a parseable report without error), diagnosis consistency
  (majority share among COMPLETED runs only), correctness (vs. truth). Six truncated answers never count
  as "consistent".
Writes data/evals/bench-<ts>.json and appends a section to design/RESULTS.md.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from collections import Counter, deque
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from ecu_copilot import config  # noqa: E402
from ecu_copilot.copilot import tools  # noqa: E402
from ecu_copilot.copilot.agent import make_copilot  # noqa: E402
from ecu_copilot.copilot.twin_client import TwinClient  # noqa: E402
from ecu_copilot.copilot.verify import verify_report  # noqa: E402
from ecu_copilot.engineering.change import detect_change  # noqa: E402
from ecu_copilot.engineering.cluster import cluster_failures  # noqa: E402
from ecu_copilot.engineering.describe import describe_signal  # noqa: E402
from ecu_copilot.engineering.spec import load_spec  # noqa: E402
from ecu_copilot.engineering.validity import check_validity  # noqa: E402
from ecu_copilot.rag.index import DocumentIndex  # noqa: E402
from ecu_copilot.twin.models import TestResult  # noqa: E402
from ecu_copilot.twin.simulator import Simulator  # noqa: E402
from evals.baselines import run_b0, run_b1  # noqa: E402

SCENARIO_DIR = Path(__file__).parent / "scenarios"
SYSTEM_ORDER = ["b0", "b1", "v1", "v1s", "v2"]


# --- frozen data ----------------------------------------------------------------------------------
class SnapshotTwin(TwinClient):
    """A TwinClient that answers from a frozen copy of the twin's results with a fixed reference time.
    Reuses the Simulator's query code (results / stats / series) over the copied results; never ticks."""

    def __init__(self, rows: list[dict], now: datetime):
        self._sim = Simulator()
        self._sim._results = deque(
            TestResult.model_validate(r) for r in sorted(rows, key=lambda r: r["timestamp"])
        )  # oldest first, as the simulator stores them
        self.now = now
        self.n = len(rows)
        self.rows = rows

    @classmethod
    def from_live(cls, twin: TwinClient, minutes: int = 240) -> SnapshotTwin:
        rows = twin.results(minutes=minutes, only_failed=False, limit=10000)
        rows = sorted(rows, key=lambda r: r["timestamp"])
        now = datetime.fromisoformat(rows[-1]["timestamp"]) if rows else datetime.now(UTC)
        return cls(rows, now)

    def health(self) -> dict:
        return {"status": "snapshot", "results": self.n, "reference_time": self.now.isoformat()}

    def results(self, *, station=None, variant=None, minutes=None, only_failed=False, limit=50):
        rows = self._sim.results(station=station, variant=variant, minutes=minutes, only_failed=only_failed, limit=limit, now=self.now)
        return [r.model_dump(mode="json") for r in rows]

    def stats(self, minutes: int = 10) -> dict:
        return self._sim.stats(minutes=minutes, now=self.now).model_dump(mode="json")

    def add_fault(self, fault):  # the snapshot is immutable
        raise RuntimeError("snapshot twin is read-only")

    def clear_faults(self):
        raise RuntimeError("snapshot twin is read-only")


# --- solvability -------------------------------------------------------------------------------------
def solvable(sc: dict, twin: TwinClient) -> tuple[bool, str, dict]:
    """(ok, message, info). Solvability checks DATA prerequisites (enough results, the injected condition is
    present in the window). They never use the detector under test to decide whether a normal case counts:
    a false alarm of detect_change on an unchanged line is a RESULT (recorded in `info`), not a reason to drop S04."""
    s = sc.get("solvability") or {}
    if not s:
        return True, "no check", {}
    rows = twin.results(station=s.get("station"), variant=s.get("variant"), minutes=10, only_failed=False, limit=10000)
    if s.get("check") == "data_ok":  # S04: enough data, normal rate - the detector's verdict is recorded, not gating
        rate = 100.0 * sum(1 for r in rows if r["verdict"] == "fail") / len(rows) if rows else 0.0
        chg = detect_change(
            twin.results(station=s.get("station"), variant=s.get("variant"), minutes=60, only_failed=False, limit=10000),
            metric="failure_rate",
        )
        ok = len(rows) >= s.get("min_results", 150) and rate <= s.get("max_rate_pct", 4.0)
        info = {
            "results_10min": len(rows),
            "rate_10min_pct": round(rate, 1),
            "detector_false_alarm": bool(chg.get("significant")),
            "detector_z": chg.get("z"),
        }
        return (
            ok,
            f"{len(rows)} results, rate 10 min {rate:.1f} %; detect_change significant={chg.get('significant')} (recorded, not gating)",
            info,
        )
    if s.get("check") == "decoupled":  # S05: reported T1 high in the RECENT window, current does not follow
        d = describe_signal(rows, load_spec())
        win = s.get("window_minutes", 3)
        recent = twin.results(station=s.get("station"), variant=s.get("variant"), minutes=win, only_failed=False, limit=10000)
        t_recent = sum(r["measurements"]["board_temp_c"] for r in recent) / len(recent) if recent else 0.0
        ok = d.get("iq_t1_relation") == "decoupled" and t_recent >= s.get("min_reported_temp_c", 32.0) and len(recent) >= 20
        info = {
            "relation": d.get("iq_t1_relation"),
            "reported_t1_recent_c": round(t_recent, 1),
            "recent_results": len(recent),
            "ratio": (d.get("iq_model") or {}).get("ratio"),
        }
        return ok, f"relation={d.get('iq_t1_relation')}, reported T1 last {win} min {t_recent:.1f} °C ({len(recent)} results)", info
    v = check_validity(rows, load_spec())
    code = v["codes"].get(s.get("code"), {})
    fails = code.get("fail_verdicts", 0)
    share = 100.0 * code.get("invalid_per_spec", 0) / fails if fails else 0.0
    ok = fails >= s.get("min_failures", 1) and share >= s.get("min_invalid_share_pct", 0)
    msg = f"{s.get('code')}: {fails} fails, {share:.0f} % invalid"
    if s.get("check") == "validity_and_lot":
        rows_lot = twin.results(station=None, variant=s.get("variant"), minutes=30, only_failed=False, limit=10000)
        c = cluster_failures(rows_lot, by="lot", code=s.get("lot_code"))
        top = c.get("top") or {}
        lot_ok = c["concentrated"] and top.get("group") == s.get("lot") and top.get("failed", 0) >= s.get("min_lot_failures", 1)
        msg += f"; lot {top.get('group')} {top.get('failed')} fails, concentrated={c['concentrated']}"
        ok = ok and lot_ok
    return ok, msg, {"code_fails": fails, "invalid_share_pct": round(share, 1)}


# --- scoring ------------------------------------------------------------------------------------------
def _scope_match(truth_scope: dict, scope: dict | None) -> bool:
    scope = scope or {}
    if truth_scope.get("lot"):
        return scope.get("lot") == truth_scope["lot"]
    return str(scope.get("station")) == str(truth_scope.get("station")) and (
        truth_scope.get("variant") is None or scope.get("variant") == truth_scope["variant"]
    )


def score(sc: dict, r, chunks, spec) -> dict:
    truth = sc["truth"]
    rep = r.report or {}
    assessments = rep.get("assessments") or []
    matched = 0
    for ta in truth["assessments"]:
        hit = next((a for a in assessments if _scope_match(ta["scope"], a.get("scope"))), None)
        if (
            hit
            and hit.get("test_validity") == ta["test_validity"]
            and hit.get("defect_indication") == ta["defect_indication"]
            and hit.get("root_cause") == ta["root_cause"]
        ):
            matched += 1
    n_truth = len(truth["assessments"])
    # extra claims: assessments that match no truth entry and assert a cause (a plain "valid / none / none"
    # for an unaffected group is not a claim) - reviewer request after run 2
    extra = [
        a
        for a in assessments
        if not any(_scope_match(ta["scope"], a.get("scope")) and a.get("root_cause") == ta["root_cause"] for ta in truth["assessments"])
        and a.get("root_cause") != "none"
        and not (a.get("test_validity") == "valid" and a.get("defect_indication") == "none")
    ]
    finding = rep.get("finding")
    cause_ok = (
        all(any(a.get("root_cause") == ta["root_cause"] for a in assessments) for ta in truth["assessments"]) if assessments else False
    )
    tools_called = [c.name for c in r.tool_calls]
    required_ok = all(t in tools_called for t in truth.get("required_tools", []))
    citations = [e.get("citation", "") for e in rep.get("evidence", []) if e.get("source_type") == "document"]
    must = truth.get("must_cite_any", [])
    norm = lambda t: re.sub(r"\s*(§|item|section|abschnitt)\s*", " ", str(t), flags=re.I).replace("  ", " ").strip().lower()  # noqa: E731
    must_cite = any(any(norm(m) in norm(c) for c in citations) or (norm(m) in norm(r.answer or "")) for m in must) if must else True
    nt = rep.get("next_test") or {}
    nt_text = json.dumps(nt, ensure_ascii=False)
    next_ok = (
        any(k.lower() in nt_text.lower() for k in truth.get("next_test_keywords_any", [])) if truth.get("next_test_keywords_any") else True
    )
    block_ok = True if truth.get("block_units") is None else (bool(nt.get("block_units")) == truth["block_units"]) if nt else False
    comps_ok = (
        any(c in (rep.get("affected_components") or []) for c in truth.get("components_any", [])) if truth.get("components_any") else True
    )
    empty = {"ok": 0, "total": 0}
    ver = (
        verify_report(rep, r.tool_calls, chunks, spec).summary()
        if rep
        else {"provenance": {"live": empty, "docs": empty}, "support": {"live": empty, "docs": empty}}
    )
    has_refs = any("ref" in e for e in rep.get("evidence", []))
    abstained = finding in ("unclear", "information")
    completed = bool(rep) and not r.error
    return {
        "completed": completed,
        "finding": finding,
        "finding_ok": finding == truth["finding"],
        "assessments_matched": f"{matched}/{n_truth}",
        "assessments_ok": matched == n_truth,
        "extra_assessments": len(extra),
        "extra_claims": [f"{a.get('scope')} {a.get('test_validity')}/{a.get('defect_indication')}/{a.get('root_cause')}" for a in extra],
        "assessments_exact": matched == n_truth and not extra,
        "root_cause_ok": cause_ok,
        "abstain_ok": (abstained == truth.get("abstain_expected", False)),
        "required_tools_ok": required_ok,
        "must_cite_ok": must_cite,
        "next_test_ok": next_ok,
        "block_units_ok": block_ok,
        "components_ok": comps_ok,
        "prov_live": ver["provenance"]["live"] if has_refs else empty,  # n/a for the V1 schema, not zero
        "prov_docs": ver["provenance"]["docs"],
        "supp_docs": ver["support"]["docs"],
        "n_evidence": len(rep.get("evidence", [])),
        "tools": tools_called,
        "latency_s": r.latency_s,
        "cost_usd": r.cost_usd,
        "error": r.error,
    }


# --- systems ------------------------------------------------------------------------------------------
def make_systems(names: list[str], model: str | None):
    systems = {}
    for n in names:
        if n == "b0":
            systems[n] = lambda q, sc: run_b0(q, _scope(sc).get("station"), _scope(sc).get("variant"))
        elif n == "b1":
            systems[n] = lambda q, sc: run_b1(q, model=model)
        elif n in ("v1", "v1s", "v2"):
            systems[n] = (lambda prof: lambda q, sc: make_copilot(profile=prof, model=model).ask(q))(n)
        else:
            raise SystemExit(f"unknown system {n}")
    return systems


def _scope(sc: dict) -> dict:
    """The investigation scope B0 is given (it cannot read the question). Explicit `scope` in the scenario wins;
    deriving it from the injected faults is only a fallback - S04 has no fault and still has a scope."""
    if sc.get("scope"):
        return dict(sc["scope"])
    for f in sc.get("setup", []):
        if "station" in f:
            variant = next(
                (a["scope"].get("variant") for a in sc["truth"]["assessments"] if a["scope"].get("station") == f["station"]), None
            )
            return {"station": f["station"], "variant": variant}
    return {}


# --- main ---------------------------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", default="all")
    ap.add_argument("--systems", default=",".join(SYSTEM_ORDER))
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--model", default=None)
    ap.add_argument("--settle", type=int, default=None, help="override settle seconds")
    args = ap.parse_args()

    files = sorted(SCENARIO_DIR.glob("*.json"))
    if args.scenarios != "all":
        wanted = args.scenarios.split(",")
        files = [f for f in files if any(f.name.startswith(w) for w in wanted)]
    scenarios = [json.loads(f.read_text(encoding="utf-8")) for f in files]

    live = TwinClient()
    live.health()
    index = DocumentIndex().load()
    spec = load_spec()
    systems = make_systems(args.systems.split(","), args.model)
    model = args.model or config.AGENT_MODEL
    print(
        f"[bench] provider={config.LLM_PROVIDER} model={model} systems={list(systems)} repeats={args.repeats} scenarios={[s['id'] for s in scenarios]}"
    )

    ts = datetime.now(UTC)
    out_dir = config.DATA_DIR / "evals"
    archive = out_dir / f"bench-{ts:%Y%m%d-%H%M%S}"
    archive.mkdir(parents=True, exist_ok=True)
    version = git_version()
    print(
        f"[bench] code {version['commit'][:10]}{' (dirty)' if version['dirty'] else ''} · prompt {config.PROMPT_VERSION} · archive {archive}"
    )
    runs = []
    for i_sc, sc in enumerate(scenarios):
        live.reset(seed=1000 + i_sc, history_minutes=30)  # isolation: nothing from the previous scenario lingers
        for f in sc["setup"]:
            live.add_fault(f)
        settle = args.settle if args.settle is not None else sc.get("settle_s", 120)
        print(f"[bench] {sc['id']}: faults injected, settling {settle}s …")
        time.sleep(settle)
        snap = SnapshotTwin.from_live(live)
        tools.configure(index=index, twin=snap)  # every system reads the same frozen data
        (archive / f"snapshot-{sc['id']}.json").write_text(
            json.dumps({"scenario": sc, "reference_time": snap.now.isoformat(), "rows": snap.rows}, ensure_ascii=False, default=str)
        )
        ok, msg, info = solvable(sc, snap)
        exploratory = bool(sc.get("exploratory")) or not ok
        print(
            f"[bench] {sc['id']}: snapshot {snap.n} results, reference {snap.now:%H:%M:%S} · solvability {'OK' if ok else 'NOT MET'} ({msg})"
            + (" · EXPLORATIV" if exploratory else "")
        )
        for name, fn in systems.items():
            for rep_i in range(args.repeats):
                r = fn(sc["question"], sc)
                s = score(sc, r, index._chunks, spec)
                s.update(
                    {
                        "scenario": sc["id"],
                        "system": name,
                        "repeat": rep_i,
                        "solvable": ok,
                        "solvability_info": info,
                        "exploratory": exploratory,
                        "reference_time": snap.now.isoformat(),
                        "answer": r.answer,
                        "report": r.report,
                        "tool_calls": [
                            {"name": c.name, "input": c.input, "duration_ms": c.duration_ms, "output": c.output} for c in r.tool_calls
                        ],
                    }
                )
                runs.append(s)
                print(
                    f"  {name:3} r{rep_i}  {'ok ' if s['completed'] else 'ERR'} finding={str(s['finding']):15} assess={s['assessments_matched']} cause={'Y' if s['root_cause_ok'] else 'n'} "
                    f"tools={'Y' if s['required_tools_ok'] else 'n'} cite={'Y' if s['must_cite_ok'] else 'n'} prov={s['prov_live']['ok']}/{s['prov_live']['total']}+{s['prov_docs']['ok']}/{s['prov_docs']['total']} "
                    f"{s['latency_s']:5.1f}s {s['cost_usd']:.3f}$ {s['error'] or ''}"
                )
        live.clear_faults()

    out = archive / "runs.json"
    out.write_text(
        json.dumps(
            {
                "model": model,
                "provider": config.LLM_PROVIDER,
                "prompt_version": config.PROMPT_VERSION,
                "repeats": args.repeats,
                "max_tokens": config.AGENT_MAX_TOKENS,
                "effort": config.AGENT_EFFORT,
                "code": version,
                "runs": runs,
            },
            ensure_ascii=False,
            indent=1,
            default=str,
        )
    )
    table = summarize(runs, model, ts)
    print("\n" + table)
    results_md = ROOT / "design" / "RESULTS.md"
    header = "# Benchmark-Ergebnisse\n\nJeder Abschnitt ist ein Lauf von `evals/bench.py`. Details in `data/evals/bench-*.json`.\n"
    prev = results_md.read_text(encoding="utf-8") if results_md.exists() else header
    results_md.write_text(prev.rstrip("\n") + "\n\n" + table + "\n", encoding="utf-8")
    print(f"[bench] report: {out} · design/RESULTS.md updated")
    return 0


def git_version() -> dict:
    import subprocess

    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=ROOT).stdout.strip())
    except Exception:  # noqa: BLE001
        commit, dirty = "unknown", True
    return {"commit": commit, "dirty": dirty, "prompt_version": config.PROMPT_VERSION}


def _pct(xs) -> str:
    return f"{100 * sum(1 for x in xs if x) / len(xs):.0f} %" if xs else "–"


def _rate(xs, key) -> str:
    ok = sum(x[key]["ok"] for x in xs)
    tot = sum(x[key]["total"] for x in xs)
    return f"{100 * ok / tot:.0f} % ({ok}/{tot})" if tot else "n/a"


def consistency(findings: list) -> float | None:
    """Majority share among completed runs only (None/truncated runs are excluded, never counted as agreement)."""
    valid = [f for f in findings if f is not None]
    if len(valid) < 2:
        return None
    return Counter(valid).most_common(1)[0][1] / len(valid)


def split_runs(runs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Regular = scenario not marked exploratory AND its solvability criterion met. Everything else is reported
    separately and never enters the headline rates (CONCEPT §10)."""
    regular = [r for r in runs if not r.get("exploratory") and r.get("solvable", True)]
    exploratory = [r for r in runs if r not in regular]
    return regular, exploratory


def summarize(runs: list[dict], model: str, ts: datetime) -> str:
    regular, exploratory = split_runs(runs)
    scenarios_all = sorted({r["scenario"] for r in runs})
    lines = [
        f"## {ts:%Y-%m-%d %H:%M} UTC · Modell {model} · max_tokens {config.AGENT_MAX_TOKENS} · Szenarien {', '.join(scenarios_all)} · {len(runs)} Läufe ({len(regular)} regulär, {len(exploratory)} explorativ) · eingefrorener Datenstand je Szenario",
        "",
    ]
    lines += _table(regular, "Reguläre Szenarien (Lösbarkeit erfüllt, nicht explorativ) – Gesamtquoten")
    if exploratory:
        lines += [""] + _table(
            exploratory, "Explorative Läufe (als explorativ markiert oder Lösbarkeit nicht erfüllt) – separat, nicht in der Gesamtquote"
        )
    lines += _per_scenario(runs)
    return "\n".join(lines)


def _table(runs: list[dict], title: str) -> list[str]:
    if not runs:
        return [f"**{title}:** keine Läufe"]
    systems = sorted({r["system"] for r in runs}, key=lambda s: SYSTEM_ORDER.index(s) if s in SYSTEM_ORDER else 9)
    scenarios = sorted({r["scenario"] for r in runs})
    lines = [
        f"**{title}** ({', '.join(scenarios)}, {len(runs)} Läufe)",
        "",
        "| System | Abschluss | Befund korrekt | Bewertungen korrekt | Ursache | Zusatz-Behaupt. Ø | Bewertungen exakt | Zurückhaltung ok | Pflicht-Tools | Zitat vorh. | Herkunft live | Herkunft Dok | Stützung Dok | Nächster Test | Diagnose-Konsistenz | Ø s | Ø $ |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in systems:
        rs = [r for r in runs if r["system"] == s]
        done = [r for r in rs if r["completed"]]
        cons = [
            c
            for c in (consistency([r["finding"] for r in rs if r["scenario"] == sc and r["completed"]]) for sc in scenarios)
            if c is not None
        ]
        cons_txt = f"{100 * statistics.fmean(cons):.0f} %" if cons else "n/a"
        lines.append(
            f"| {s.upper()} | {_pct([r['completed'] for r in rs])} | {_pct([r['finding_ok'] for r in rs])} | {_pct([r['assessments_ok'] for r in rs])} | {_pct([r['root_cause_ok'] for r in rs])} | "
            f"{statistics.fmean(r.get('extra_assessments', 0) for r in rs):.2f} | {_pct([r.get('assessments_exact', False) for r in rs])} | {_pct([r['abstain_ok'] for r in rs])} | {_pct([r['required_tools_ok'] for r in rs])} | {_pct([r['must_cite_ok'] for r in rs])} | {_rate(done, 'prov_live')} | {_rate(done, 'prov_docs')} | {_rate(done, 'supp_docs')} | "
            f"{_pct([r['next_test_ok'] for r in rs])} | {cons_txt} | {statistics.fmean(r['latency_s'] for r in rs):.1f} | {statistics.fmean(r['cost_usd'] for r in rs):.3f} |"
        )
    return lines


def _per_scenario(runs: list[dict]) -> list[str]:
    systems = sorted({r["system"] for r in runs}, key=lambda s: SYSTEM_ORDER.index(s) if s in SYSTEM_ORDER else 9)
    scenarios = sorted({r["scenario"] for r in runs})
    lines = [
        "",
        "Je Szenario: abgeschlossen / Befund korrekt / Bewertungen exakt (über Wiederholungen); (E) = explorativ:",
        "",
        "| Szenario | " + " | ".join(s.upper() for s in systems) + " |",
        "|---|" + "---|" * len(systems),
    ]
    for sc in scenarios:
        cells = []
        for s in systems:
            rs = [r for r in runs if r["system"] == s and r["scenario"] == sc]
            cells.append(
                f"{sum(1 for r in rs if r['completed'])} / {sum(1 for r in rs if r['finding_ok'])} / {sum(1 for r in rs if r.get('assessments_exact'))} von {len(rs)}"
            )
        flag = " (E)" if any(r.get("exploratory") for r in runs if r["scenario"] == sc) else ""
        info = next((r.get("solvability_info") for r in runs if r["scenario"] == sc and r.get("solvability_info")), None)
        extra = (
            f" · Detektor-Fehlalarm auf unveränderter Linie: {'ja' if info.get('detector_false_alarm') else 'nein'}"
            if info and "detector_false_alarm" in info
            else ""
        )
        lines.append(f"| {sc}{flag}{extra} | " + " | ".join(cells) + " |")
    errs = [r for r in runs if r["error"]]
    if errs:
        lines += ["", f"Fehler: {len(errs)} Läufe – " + "; ".join(f"{r['system']}/{r['scenario']}: {r['error'][:80]}" for r in errs[:6])]
    lines += [
        "",
        "Lesehilfe: *regulär* = Lösbarkeit erfüllt und nicht explorativ; nur diese Läufe bilden die Gesamtquoten. *Abschluss* = auswertbarer Report ohne Fehler; *Diagnose-Konsistenz* = Mehrheitsanteil nur über abgeschlossene Läufe; *Zurückhaltung ok* = 'unklar' genau dann, wenn die Wahrheit es verlangt; *Herkunft live* n/a für Systeme ohne Referenzen (V1-Schema). *Herkunft* heißt: Die automatische Prüfung konnte die angegebene Quelle bzw. den referenzierten Wert nachvollziehen – nicht, dass die Aussage oder Diagnose richtig ist. *Stützung Dok* ist eine Schlüsselwort-Heuristik. *Zusatz-Behaupt.* = Bewertungen, die keiner Wahrheits-Gruppe entsprechen und eine Ursache behaupten; *Bewertungen exakt* = alle erwarteten gefunden und keine Zusatzbehauptung. B0 kennt die Szenario-Scope-Angabe (Station/Variante) aus der Szenariodefinition, nicht aus der Frage.",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
