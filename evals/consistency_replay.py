"""Replay the consistency check (CONCEPT §11) over an archived benchmark - offline, no model calls.
    uv run python evals/consistency_replay.py data/evals/bench-20261017-090812/runs.json

Prints one line per run (scenario, system, repeat, flags) and a per-system/scenario summary. Reports,
findings and the archived scores are not touched; this only adds visibility.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecu_copilot.copilot.agent import ToolCall  # noqa: E402
from ecu_copilot.copilot.consistency import check_consistency  # noqa: E402


def load_runs(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["runs"] if isinstance(data, dict) else data


def calls_of(run: dict) -> list[ToolCall]:
    return [ToolCall(name=c["name"], input=c.get("input") or {}, output=c.get("output") or "") for c in run.get("tool_calls") or []]


def replay(runs: list[dict]) -> list[dict]:
    rows = []
    for r in runs:
        flags = check_consistency(r.get("report"), calls_of(r))
        rows.append(
            {
                "scenario": r["scenario"],
                "system": r["system"],
                "repeat": r.get("repeat"),
                "exploratory": bool(r.get("exploratory")) or not r.get("solvable", True),
                "codes": sorted(f.code for f in flags),
                "flags": [f.as_dict() for f in flags],
            }
        )
    return rows


def main(path: str) -> int:
    rows = replay(load_runs(path))
    print(f"{'Szenario':<32} {'System':<5} {'Wdh':<3} {'Marken'}")
    for row in sorted(rows, key=lambda x: (x["scenario"], x["system"], x["repeat"] or 0)):
        tag = " (E)" if row["exploratory"] else ""
        print(f"{row['scenario'] + tag:<32} {row['system']:<5} r{row['repeat']:<2} {', '.join(row['codes']) or '-'}")
    print()
    per = defaultdict(Counter)
    for row in rows:
        for c in set(row["codes"]):
            per[(row["system"], row["scenario"])][c] += 1
    print("Läufe mit Marke je System/Szenario (von 3):")
    for (system, scenario), cnt in sorted(per.items()):
        print(f"  {system:<5} {scenario:<32} " + "  ".join(f"{k}:{v}" for k, v in sorted(cnt.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "data/evals/bench-20261017-090812/runs.json"))
