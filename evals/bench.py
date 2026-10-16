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
from ecu_copilot.engineering.cluster import cluster_failures  # noqa: E402
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
def solvable(sc: dict, twin: TwinClient) -> tuple[bool, str]:
    s = sc.get("solvability") or {}
    if not s:
        return True, "no check"
    rows = twin.results(station=s.get("station"), variant=s.get("variant"), minutes=10, only_failed=False, limit=10000)
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
    return ok, msg


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
    finding = rep.get("finding")
    cause_ok = (
        all(any(a.get("root_cause") == ta["root_cause"] for a in assessments) for ta in truth["assessments"]) if assessments else False
    )
    tools_called = [c.name for c in r.tool_calls]
    required_ok = all(t in tools_called for t in truth.get("required_tools", []))
    citations = [e.get("citation", "") for e in rep.get("evidence", []) if e.get("source_type") == "document"]
    must = truth.get("must_cite_any", [])
    must_cite = any(any(m in c for c in citations) or (m in (r.answer or "")) for m in must) if must else True
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

    runs = []
    for sc in scenarios:
        live.clear_faults()
        for f in sc["setup"]:
            live.add_fault(f)
        settle = args.settle if args.settle is not None else sc.get("settle_s", 120)
        print(f"[bench] {sc['id']}: faults injected, settling {settle}s …")
        time.sleep(settle)
        snap = SnapshotTwin.from_live(live)
        tools.configure(index=index, twin=snap)  # every system reads the same frozen data
        ok, msg = solvable(sc, snap)
        print(
            f"[bench] {sc['id']}: snapshot {snap.n} results, reference {snap.now:%H:%M:%S} · solvability {'OK' if ok else 'NOT MET'} ({msg})"
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
                        "reference_time": snap.now.isoformat(),
                        "answer": r.answer,
                        "report": r.report,
                    }
                )
                runs.append(s)
                print(
                    f"  {name:3} r{rep_i}  {'ok ' if s['completed'] else 'ERR'} finding={str(s['finding']):15} assess={s['assessments_matched']} cause={'Y' if s['root_cause_ok'] else 'n'} "
                    f"tools={'Y' if s['required_tools_ok'] else 'n'} cite={'Y' if s['must_cite_ok'] else 'n'} prov={s['prov_live']['ok']}/{s['prov_live']['total']}+{s['prov_docs']['ok']}/{s['prov_docs']['total']} "
                    f"{s['latency_s']:5.1f}s {s['cost_usd']:.3f}$ {s['error'] or ''}"
                )
        live.clear_faults()

    out_dir = config.DATA_DIR / "evals"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC)
    out = out_dir / f"bench-{ts:%Y%m%d-%H%M%S}.json"
    out.write_text(
        json.dumps(
            {
                "model": model,
                "provider": config.LLM_PROVIDER,
                "prompt_version": config.PROMPT_VERSION,
                "repeats": args.repeats,
                "max_tokens": config.AGENT_MAX_TOKENS,
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


def summarize(runs: list[dict], model: str, ts: datetime) -> str:
    systems = sorted({r["system"] for r in runs}, key=lambda s: SYSTEM_ORDER.index(s) if s in SYSTEM_ORDER else 9)
    scenarios = sorted({r["scenario"] for r in runs})
    lines = [
        f"## {ts:%Y-%m-%d %H:%M} UTC · Modell {model} · max_tokens {config.AGENT_MAX_TOKENS} · Szenarien {', '.join(scenarios)} · {len(runs)} Läufe · eingefrorener Datenstand je Szenario",
        "",
        "| System | Abschluss | Befund korrekt | Bewertungen korrekt | Ursache | Zurückhaltung ok | Pflicht-Tools | Zitat vorh. | Herkunft live | Herkunft Dok | Stützung Dok | Nächster Test | Diagnose-Konsistenz | Ø s | Ø $ |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
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
            f"{_pct([r['abstain_ok'] for r in rs])} | {_pct([r['required_tools_ok'] for r in rs])} | {_pct([r['must_cite_ok'] for r in rs])} | {_rate(done, 'prov_live')} | {_rate(done, 'prov_docs')} | {_rate(done, 'supp_docs')} | "
            f"{_pct([r['next_test_ok'] for r in rs])} | {cons_txt} | {statistics.fmean(r['latency_s'] for r in rs):.1f} | {statistics.fmean(r['cost_usd'] for r in rs):.3f} |"
        )
    lines += [
        "",
        "Je Szenario: abgeschlossen / Befund korrekt / Bewertungen korrekt (über Wiederholungen):",
        "",
        "| Szenario | " + " | ".join(s.upper() for s in systems) + " |",
        "|---|" + "---|" * len(systems),
    ]
    for sc in scenarios:
        cells = []
        for s in systems:
            rs = [r for r in runs if r["system"] == s and r["scenario"] == sc]
            cells.append(
                f"{sum(1 for r in rs if r['completed'])} / {sum(1 for r in rs if r['finding_ok'])} / {sum(1 for r in rs if r['assessments_ok'])} von {len(rs)}"
            )
        lines.append(f"| {sc} | " + " | ".join(cells) + " |")
    errs = [r for r in runs if r["error"]]
    if errs:
        lines += ["", f"Fehler: {len(errs)} Läufe – " + "; ".join(f"{r['system']}/{r['scenario']}: {r['error'][:80]}" for r in errs[:6])]
    lines += [
        "",
        "Lesehilfe: *Abschluss* = auswertbarer Report ohne Fehler; *Diagnose-Konsistenz* = Mehrheitsanteil nur über abgeschlossene Läufe; *Zurückhaltung ok* = 'unklar' genau dann, wenn die Wahrheit es verlangt; *Herkunft live* n/a für Systeme ohne Referenzen (V1-Schema). B0 kennt die Szenario-Scope-Angabe (Station/Variante) aus der Szenariodefinition, nicht aus der Frage.",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
