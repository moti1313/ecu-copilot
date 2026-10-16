"""Re-score a saved benchmark from its stored reports - no model calls.
    uv run python evals/rescore.py data/evals/bench-<ts>.json   (or .../bench-<ts>/runs.json)

Recomputes, per run, the assessment metrics including *extra claims* (assessments that match no truth
entry and assert a cause) from the saved `report`, and prints a per-system table. Provenance numbers are
taken from the saved run (they need the tool outputs, which older runs did not archive).
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from evals.bench import SCENARIO_DIR, SYSTEM_ORDER, _scope_match  # noqa: E402


def extra_claims(truth: dict, report: dict | None) -> list[str]:
    assessments = (report or {}).get("assessments") or []
    extra = [
        a
        for a in assessments
        if not any(_scope_match(ta["scope"], a.get("scope")) and a.get("root_cause") == ta["root_cause"] for ta in truth["assessments"])
        and a.get("root_cause") != "none"
        and not (a.get("test_validity") == "valid" and a.get("defect_indication") == "none")
    ]
    return [f"{a.get('scope')} {a.get('test_validity')}/{a.get('defect_indication')}/{a.get('root_cause')}" for a in extra]


def main(path: str) -> int:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    truths = {json.loads(f.read_text())["id"]: json.loads(f.read_text())["truth"] for f in SCENARIO_DIR.glob("*.json")}
    rows = []
    for r in data["runs"]:
        truth = truths[r["scenario"]]
        ex = extra_claims(truth, r.get("report"))
        rows.append({**r, "extra_assessments": len(ex), "extra_claims": ex, "assessments_exact": r["assessments_ok"] and not ex})
    systems = sorted({r["system"] for r in rows}, key=lambda s: SYSTEM_ORDER.index(s) if s in SYSTEM_ORDER else 9)
    print(f"Re-score of {path} · model {data.get('model')} · {len(rows)} runs\n")
    print("| System | Bewertungen gefunden | Zusatz-Behaupt. Ø | Läufe mit Zusatzbehauptung | Bewertungen exakt | Befund korrekt |")
    print("|---|---|---|---|---|---|")
    for s in systems:
        rs = [r for r in rows if r["system"] == s]
        pct = lambda xs: f"{100 * sum(1 for x in xs if x) / len(xs):.0f} %"  # noqa: E731
        print(
            f"| {s.upper()} | {pct([r['assessments_ok'] for r in rs])} | {statistics.fmean(r['extra_assessments'] for r in rs):.2f} | "
            f"{sum(1 for r in rs if r['extra_assessments'])}/{len(rs)} | {pct([r['assessments_exact'] for r in rs])} | {pct([r['finding_ok'] for r in rs])} |"
        )
    claims = [(r["system"], r["scenario"], r["repeat"], c) for r in rows for c in r["extra_claims"]]
    if claims:
        print("\nZusatzbehauptungen im Detail:")
        for sysname, sc, rep_i, c in claims:
            print(f"- {sysname}/{sc}/r{rep_i}: {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
