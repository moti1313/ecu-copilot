"""Scenario benchmark: B0 / B1 / V1 / V2 on scenarios with known truth, repeated runs.
    uv run python evals/bench.py [--scenarios S01,S08] [--systems b0,b1,v1,v2] [--repeats 3] [--model gpt-5]

Per scenario: inject the faults once, wait `settle_s`, check solvability, then run every system
`repeats` times on the same live state (fairness: identical conditions), then clear the faults.
Metrics per run (design/CONCEPT.md §5): assessment accuracy, finding accuracy, root-cause accuracy,
abstention, required tools called, citation validity, provenance / support rates (verify.py),
must-cite, next-test keywords, latency, cost. Consistency = share of runs with the majority finding.
Writes data/evals/bench-<ts>.json and design/RESULTS.md (appended section).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
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
from evals.baselines import run_b0, run_b1  # noqa: E402

SCENARIO_DIR = Path(__file__).parent / "scenarios"


# --- solvability ---------------------------------------------------------------------------------
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


# --- scoring -------------------------------------------------------------------------------------
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
    # assessments: every truth entry must be matched by a report entry with the same scope and fields
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
    must_cite = (
        any(any(m in c for c in citations) or any(m in (r.answer or "") for m in [m]) for m in truth.get("must_cite_any", []))
        if truth.get("must_cite_any")
        else True
    )
    nt = rep.get("next_test") or {}
    nt_text = json.dumps(nt, ensure_ascii=False)
    next_ok = (
        any(k.lower() in nt_text.lower() for k in truth.get("next_test_keywords_any", [])) if truth.get("next_test_keywords_any") else True
    )
    block_ok = True if truth.get("block_units") is None else (bool(nt.get("block_units")) == truth["block_units"]) if nt else False
    comps_ok = (
        any(c in (rep.get("affected_components") or []) for c in truth.get("components_any", [])) if truth.get("components_any") else True
    )
    ver = (
        verify_report(rep, r.tool_calls, chunks, spec).summary()
        if rep
        else {
            "provenance": {"live": {"ok": 0, "total": 0}, "docs": {"ok": 0, "total": 0}},
            "support": {"live": {"ok": 0, "total": 0}, "docs": {"ok": 0, "total": 0}},
        }
    )
    abstained = finding in ("unclear", "information")
    return {
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
        # systems on the V1 schema carry no refs: live provenance is not applicable, not zero
        "prov_live": ver["provenance"]["live"] if any("ref" in e for e in rep.get("evidence", [])) else {"ok": 0, "total": 0},
        "prov_docs": ver["provenance"]["docs"],
        "supp_docs": ver["support"]["docs"],
        "n_evidence": len(rep.get("evidence", [])),
        "tools": tools_called,
        "latency_s": r.latency_s,
        "cost_usd": r.cost_usd,
        "error": r.error,
    }


# --- systems -------------------------------------------------------------------------------------
def make_systems(names: list[str], model: str | None):
    systems = {}
    for n in names:
        if n == "b0":
            systems[n] = lambda q, sc: run_b0(q, _scope(sc).get("station"), _scope(sc).get("variant"))
        elif n == "b1":
            systems[n] = lambda q, sc: run_b1(q, model=model)
        elif n in ("v1", "v2"):
            systems[n] = (lambda prof: lambda q, sc: make_copilot(profile=prof, model=model).ask(q))(n)
        else:
            raise SystemExit(f"unknown system {n}")
    return systems


def _scope(sc: dict) -> dict:
    for f in sc.get("setup", []):
        if "station" in f:
            return {
                "station": f["station"],
                "variant": next(
                    (a["scope"].get("variant") for a in sc["truth"]["assessments"] if a["scope"].get("station") == f["station"]), None
                ),
            }
    return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", default="all")
    ap.add_argument("--systems", default="b0,b1,v1,v2")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--model", default=None)
    ap.add_argument("--settle", type=int, default=None, help="override settle seconds")
    args = ap.parse_args()

    files = sorted(SCENARIO_DIR.glob("*.json"))
    if args.scenarios != "all":
        wanted = args.scenarios.split(",")
        files = [f for f in files if any(f.name.startswith(w) for w in wanted)]
    scenarios = [json.loads(f.read_text(encoding="utf-8")) for f in files]

    twin = TwinClient()
    twin.health()
    index = DocumentIndex().load()
    tools.configure(index=index, twin=twin)
    spec = load_spec()
    systems = make_systems(args.systems.split(","), args.model)
    model = args.model or config.AGENT_MODEL
    print(
        f"[bench] provider={config.LLM_PROVIDER} model={model} systems={list(systems)} repeats={args.repeats} scenarios={[s['id'] for s in scenarios]}"
    )

    runs = []
    for sc in scenarios:
        twin.clear_faults()
        for f in sc["setup"]:
            twin.add_fault(f)
        settle = args.settle if args.settle is not None else sc.get("settle_s", 120)
        print(f"[bench] {sc['id']}: faults injected, settling {settle}s …")
        time.sleep(settle)
        ok, msg = solvable(sc, twin)
        print(f"[bench] {sc['id']}: solvability {'OK' if ok else 'NOT MET'} ({msg})")
        for name, fn in systems.items():
            for rep_i in range(args.repeats):
                r = fn(sc["question"], sc)
                s = score(sc, r, index._chunks, spec)
                s.update({"scenario": sc["id"], "system": name, "repeat": rep_i, "solvable": ok, "answer": r.answer, "report": r.report})
                runs.append(s)
                print(
                    f"  {name:3} r{rep_i}  finding={str(s['finding']):15} assess={s['assessments_matched']} cause={'Y' if s['root_cause_ok'] else 'n'} tools={'Y' if s['required_tools_ok'] else 'n'} cite={'Y' if s['must_cite_ok'] else 'n'} prov={s['prov_live']['ok']}/{s['prov_live']['total']}+{s['prov_docs']['ok']}/{s['prov_docs']['total']} {s['latency_s']:5.1f}s {s['cost_usd']:.3f}$ {s['error'] or ''}"
                )
        twin.clear_faults()

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
    header = "# Benchmark-Ergebnisse\n\nJeder Abschnitt ist ein Lauf von `evals/bench.py`. Zahlen sind Mittelwerte über Szenarien × Wiederholungen; Details in `data/evals/bench-*.json`.\n"
    prev = results_md.read_text(encoding="utf-8") if results_md.exists() else header
    results_md.write_text(prev + "\n" + table + "\n", encoding="utf-8")
    print(f"[bench] report: {out} · design/RESULTS.md updated")
    return 0


def summarize(runs: list[dict], model: str, ts: datetime) -> str:
    systems = sorted({r["system"] for r in runs}, key=lambda s: ["b0", "b1", "v1", "v2"].index(s) if s in ("b0", "b1", "v1", "v2") else 9)
    scenarios = sorted({r["scenario"] for r in runs})
    lines = [f"## {ts:%Y-%m-%d %H:%M} UTC · Modell {model} · Szenarien {', '.join(scenarios)} · {len(runs)} Läufe", ""]
    lines.append(
        "| System | Befund | Bewertungen (alle Gruppen) | Ursache | Pflicht-Tools | Zitat vorh. | Herkunft live | Herkunft Dok | Stützung Dok | Nächster Test | Konsistenz | Ø s | Ø $ |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")

    def pct(xs):
        return f"{100 * sum(1 for x in xs if x) / len(xs):.0f} %" if xs else "–"

    def rate(xs, key):
        ok = sum(x[key]["ok"] for x in xs)
        tot = sum(x[key]["total"] for x in xs)
        return f"{100 * ok / tot:.0f} % ({ok}/{tot})" if tot else "–"

    for s in systems:
        rs = [r for r in runs if r["system"] == s]
        cons = []
        for sc in scenarios:
            fs = [r["finding"] for r in rs if r["scenario"] == sc]
            if fs:
                cons.append(Counter(fs).most_common(1)[0][1] / len(fs))
        lines.append(
            f"| {s.upper()} | {pct([r['finding_ok'] for r in rs])} | {pct([r['assessments_ok'] for r in rs])} | {pct([r['root_cause_ok'] for r in rs])} | "
            f"{pct([r['required_tools_ok'] for r in rs])} | {pct([r['must_cite_ok'] for r in rs])} | {rate(rs, 'prov_live')} | {rate(rs, 'prov_docs')} | {rate(rs, 'supp_docs')} | "
            f"{pct([r['next_test_ok'] for r in rs])} | {100 * statistics.fmean(cons):.0f} % | {statistics.fmean(r['latency_s'] for r in rs):.1f} | {statistics.fmean(r['cost_usd'] for r in rs):.3f} |"
        )
    lines.append("")
    lines.append("Je Szenario (Befund korrekt / Bewertungen korrekt, über Wiederholungen):")
    lines.append("")
    lines.append("| Szenario | " + " | ".join(s.upper() for s in systems) + " |")
    lines.append("|---|" + "---|" * len(systems))
    for sc in scenarios:
        cells = []
        for s in systems:
            rs = [r for r in runs if r["system"] == s and r["scenario"] == sc]
            cells.append(f"{sum(1 for r in rs if r['finding_ok'])}/{len(rs)} · {sum(1 for r in rs if r['assessments_ok'])}/{len(rs)}")
        lines.append(f"| {sc} | " + " | ".join(cells) + " |")
    errs = [r for r in runs if r["error"]]
    if errs:
        lines.append("")
        lines.append(f"Fehler: {len(errs)} Läufe – " + "; ".join(f"{r['system']}/{r['scenario']}: {r['error'][:80]}" for r in errs[:5]))
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
