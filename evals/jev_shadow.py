"""Jev shadow run over an archived benchmark (CONCEPT §12). Default is --dry-run: builds the states, prints sizes,
sends NOTHING. Only --send (plus TYPESAFE_API_KEY in .env) calls the API; every call is logged to data/evals/jev/.

    uv run python evals/jev_shadow.py                       # dry run over run 4, V2 runs
    uv run python evals/jev_shadow.py --system b0           # states from B0's tool calls instead
    uv run python evals/jev_shadow.py --send                # real calls - only after Morteza's go
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv  # noqa: E402

from ecu_copilot.copilot.agent import ToolCall  # noqa: E402
from ecu_copilot.copilot.jev import MODEL, QUESTIONS, JevClient, build_state, log_line, score_against_expected, state_digest  # noqa: E402
from ecu_copilot.engineering.spec import load_spec  # noqa: E402

DEFAULT_ARCHIVE = ROOT / "data/evals/bench-20261017-090812/runs.json"
SCENARIO_DIR = ROOT / "evals/scenarios"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("archive", nargs="?", default=str(DEFAULT_ARCHIVE))
    ap.add_argument("--system", default="v2")
    ap.add_argument("--send", action="store_true", help="actually call the API (default: dry run)")
    args = ap.parse_args()

    data = json.loads(Path(args.archive).read_text(encoding="utf-8"))
    runs = [r for r in data["runs"] if r["system"] == args.system]
    questions = {json.loads(f.read_text())["id"]: json.loads(f.read_text())["question"] for f in SCENARIO_DIR.glob("*.json")}
    spec = load_spec()

    client = None
    if args.send:
        load_dotenv(ROOT / ".env")
        client = JevClient(model=MODEL)
        if not client.api_key:
            print("TYPESAFE_API_KEY fehlt in .env - nichts gesendet.")
            return 2
    log = ROOT / "data/evals/jev" / f"jev-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.jsonl"

    print(f"{'Szenario':<30} {'Wdh':<3} {'Zeichen':>8} {'~Token':>7}  {'Modus' if not args.send else 'Antwort'}")
    for r in sorted(runs, key=lambda x: (x["scenario"], x.get("repeat") or 0)):
        calls = [ToolCall(name=c["name"], input=c.get("input") or {}, output=c.get("output") or "") for c in r.get("tool_calls") or []]
        state = build_state(questions.get(r["scenario"], ""), calls, spec)
        size = len(json.dumps(state, ensure_ascii=False))
        if not args.send:
            print(f"{r['scenario']:<30} r{r.get('repeat', 0):<2} {size:>8} {size // 4:>7}  dry-run · {state_digest(state)[:12]}")
            continue
        resp = client.system_one(state, QUESTIONS)
        verdicts = resp.verdicts()
        scoring = score_against_expected(r["scenario"], verdicts)
        log_line(log, {"scenario": r["scenario"], "system": r["system"], "repeat": r.get("repeat")}, resp, scoring)
        q1 = verdicts.get("next_check", {})
        print(
            f"{r['scenario']:<30} r{r.get('repeat', 0):<2} {size:>8} {size // 4:>7}  {q1.get('choice')} (conf {q1.get('confidence')}) · "
            f"T1 {verdicts.get('t1_unreliable', {}).get('verdict')} · Defekt {verdicts.get('product_defect', {}).get('verdict')} · {resp.model} · {resp.latency_ms} ms"
        )
    if args.send:
        print(f"\nProtokoll: {log}")
    else:
        print("\nNichts gesendet. Echte Aufrufe nur mit --send nach Freigabe (CONCEPT §12).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
