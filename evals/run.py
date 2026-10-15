"""Run the golden set against the live agent.   uv run python evals/run.py [--only ID] [--no-judge]

Three layers of checking per case, cheapest first:
1. tools   - were the expected tools called?            (deterministic)
2. facts   - does the answer contain the key facts?     (deterministic, substring)
3. judge   - does a second model agree with the rubric? (LLM-as-judge, claude-haiku-5-5)

A case passes when all three pass. The script prints a table, writes data/evals/<ts>.json
and exits non-zero when the pass rate is below EVAL_MIN_PASS (default 0.8) - that is the CI gate.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ecu_copilot import config  # noqa: E402
from ecu_copilot.copilot import tools  # noqa: E402
from ecu_copilot.copilot.agent import make_copilot  # noqa: E402
from ecu_copilot.copilot.twin_client import TwinClient  # noqa: E402
from ecu_copilot.rag.index import DocumentIndex  # noqa: E402

GOLDEN = Path(__file__).parent / "golden.json"


class Verdict(BaseModel):
    passed: bool = Field(description="True if the answer satisfies the rubric")
    score: float = Field(ge=0, le=1, description="0 = wrong or missing, 1 = fully correct and well cited")
    reason: str = Field(description="One or two sentences")


JUDGE_PROMPT = """You are grading an answer of an engineering assistant against a rubric.
Be strict on facts and citations, lenient on wording and language (German or English both fine).

Question:
{question}

Rubric (what a correct answer must contain):
{rubric}

Answer to grade:
{answer}
"""


def judge(case: dict, answer: str) -> Verdict:
    """LLM-as-judge with a structured verdict, on whichever provider is configured."""
    prompt = JUDGE_PROMPT.format(question=case["question"], rubric=case["rubric"], answer=answer)
    if config.LLM_PROVIDER == "openai":
        import openai

        resp = openai.OpenAI().chat.completions.parse(
            model=config.JUDGE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format=Verdict,
        )
        return resp.choices[0].message.parsed

    import anthropic

    resp = anthropic.Anthropic().messages.parse(
        model=config.JUDGE_MODEL,
        max_tokens=1000,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}],
        output_format=Verdict,
    )
    return resp.parsed_output


def check_facts(case: dict, answer: str) -> tuple[list[str], list[str]]:
    missing = [" / ".join(alts) for alts in case["facts"] if not any(a in answer for a in alts)]
    forbidden = [f for f in case["forbidden"] if f in answer]
    return missing, forbidden


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="run a single case id")
    ap.add_argument("--no-judge", action="store_true", help="skip the LLM judge (deterministic checks only)")
    ap.add_argument("--min-pass", type=float, default=float(os.environ.get("EVAL_MIN_PASS", "0.8")))
    args = ap.parse_args()

    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))["cases"]
    if args.only:
        cases = [c for c in cases if c["id"] == args.only]

    twin = TwinClient()
    try:
        twin.health()
        twin_ok = True
    except Exception as e:  # noqa: BLE001
        twin_ok = False
        print(f"[evals] twin not reachable ({e}) - live cases will be skipped")

    tools.configure(index=DocumentIndex().load(), twin=twin)
    agent = make_copilot()
    print(f"[evals] provider={config.LLM_PROVIDER} agent={config.AGENT_MODEL} judge={config.JUDGE_MODEL}")

    rows, total_cost = [], 0.0
    for case in cases:
        if case["setup"] and not twin_ok:
            rows.append({"id": case["id"], "status": "skipped", "reason": "twin not reachable"})
            continue
        if case["setup"]:
            twin.clear_faults()
            for f in case["setup"]:
                twin.add_fault(f)
            settle = case.get("settle_seconds", 60)
            print(f"[evals] {case['id']}: faults injected, settling {settle}s ...")
            time.sleep(settle)

        r = agent.ask(case["question"])
        total_cost += r.cost_usd
        if case["setup"]:
            twin.clear_faults()

        tools_called = [c.name for c in r.tool_calls]
        tools_missing = [t for t in case["expected_tools"] if t not in tools_called]
        facts_missing, forbidden_hit = check_facts(case, r.answer)
        verdict = None if args.no_judge or r.error else judge(case, r.answer)
        passed = not r.error and not tools_missing and not facts_missing and not forbidden_hit and (verdict is None or verdict.passed)
        rows.append(
            {
                "id": case["id"],
                "status": "pass" if passed else "fail",
                "error": r.error,
                "tools_called": tools_called,
                "tools_missing": tools_missing,
                "facts_missing": facts_missing,
                "forbidden_hit": forbidden_hit,
                "judge": verdict.model_dump() if verdict else None,
                "cost_usd": r.cost_usd,
                "latency_s": r.latency_s,
                "citation_missing": r.citation_missing,
                "answer": r.answer,
            }
        )
        mark = "PASS" if passed else "FAIL"
        detail = r.error or ", ".join(
            filter(
                None,
                [
                    f"tools missing {tools_missing}" if tools_missing else "",
                    f"facts missing {facts_missing}" if facts_missing else "",
                    f"forbidden {forbidden_hit}" if forbidden_hit else "",
                    f"judge: {verdict.reason}" if verdict and not verdict.passed else "",
                ],
            )
        )
        print(f"  {mark:4} {case['id']:28} {r.latency_s:5.1f}s  {r.cost_usd:.4f}$  {detail}")

    scored = [r for r in rows if r["status"] != "skipped"]
    passed = sum(1 for r in scored if r["status"] == "pass")
    rate = passed / len(scored) if scored else 0.0
    print(
        f"\n[evals] {passed}/{len(scored)} passed ({rate:.0%}), {len(rows) - len(scored)} skipped, cost {total_cost:.3f} $, model {config.AGENT_MODEL}, prompt {config.PROMPT_VERSION}"
    )

    out_dir = config.DATA_DIR / "evals"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{datetime.now(UTC):%Y%m%d-%H%M%S}.json"
    out.write_text(
        json.dumps(
            {"model": config.AGENT_MODEL, "prompt_version": config.PROMPT_VERSION, "pass_rate": rate, "cost_usd": total_cost, "rows": rows},
            ensure_ascii=False,
            indent=1,
        )
    )
    print(f"[evals] report: {out}")
    return 0 if rate >= args.min_pass else 1


if __name__ == "__main__":
    sys.exit(main())
