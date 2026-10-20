"""CONCEPT §13 Stufe b - smallest archive-based trial of ONE targeted revision from consistency marks.

Default is --dry-run: builds every revision request from the archived run 4, prints sizes and the feedback text,
sends NOTHING. Only --send (OPENAI_API_KEY from .env) calls the model - once per case, no tools, no twin.

Cases (pre-registered in CONCEPT §13): the three S05/V2 reports that carry K1 (the documented failure) and eight
originally correct V2 reports as controls (S01 r0-r2, S04 r0-r2, S08 r0 and r2). Controls get the same revision
offer with a neutral feedback, so we can measure whether the loop DEGRADES correct answers.

Measured before and after, with the benchmark's own scorer (evals/bench.py::score): assessments_exact, finding_ok,
live/doc provenance, consistency marks. Classification per case: fixed / degraded / unchanged_correct / unchanged_wrong.
The original tool outputs are passed numbered exactly as stored, so evidence refs (tool_call 1..n) stay valid.

    uv run python evals/revision_trial.py            # dry run
    uv run python evals/revision_trial.py --send     # real calls, only after Morteza's go
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from ecu_copilot import config  # noqa: E402
from ecu_copilot.copilot.agent import REPORT_SCHEMA_V2, SYSTEM_PROMPT_V2, AskResult, ToolCall, derive_finding, parse_report  # noqa: E402
from ecu_copilot.copilot.consistency import check_consistency  # noqa: E402
from ecu_copilot.copilot.jev import code_version  # noqa: E402
from ecu_copilot.copilot.metrics import Usage  # noqa: E402
from ecu_copilot.engineering.spec import load_spec  # noqa: E402
from evals.bench import SCENARIO_DIR, score  # noqa: E402

ARCHIVE = ROOT / "data/evals/bench-20261017-090812/runs.json"
OUT_DIR = ROOT / "data/evals/revision"
TRIGGER = "K1"
MAX_CALLS = 1  # one model call per case, no tool calls in Stufe b (K1 needs no new data)
RETRIES = 0  # no silent SDK retries: a failed call is a logged api_error, not a hidden second attempt
TIMEOUT_S = 240.0  # per-call time budget (CONCEPT §13)

# Pre-registered case list (CONCEPT §13 Stufe b)
CASES = [
    ("S05-sensor-offset", 0, "k1"),
    ("S05-sensor-offset", 1, "k1"),
    ("S05-sensor-offset", 2, "k1"),
    ("S01-temperature-drift", 0, "control"),
    ("S01-temperature-drift", 1, "control"),
    ("S01-temperature-drift", 2, "control"),
    ("S04-no-fault", 0, "control"),
    ("S04-no-fault", 1, "control"),
    ("S04-no-fault", 2, "control"),
    ("S08-drift-and-bad-lot", 0, "control"),
    ("S08-drift-and-bad-lot", 2, "control"),
]

REVISION_RULES = (
    "REVISION STEP. You previously produced the report below from the numbered tool outputs. A deterministic consistency "
    "check has reviewed the structured assessments and gives you the feedback below. Revise the report ONCE.\n"
    "Rules for the revision:\n"
    "- Change only what the feedback shows to be unsupported or contradictory. Keep everything that is backed by the tool outputs.\n"
    "- The structured `assessments` are what counts: an assessment is a commitment per group. Alternative explanations are NOT "
    "two simultaneous findings. If the temperature measurement path itself is in doubt, the real temperature is unknown until an "
    "independent measurement exists: do not commit to station overtemperature without independent evidence.\n"
    "- Do not invent new data. You have no tools in this step; the numbered tool outputs are the complete evidence. "
    "Evidence refs must keep pointing at the same tool_call numbers.\n"
    "- If, after checking, everything is supported, return the report unchanged.\n"
    "- Answer with the full report in the same JSON schema."
)

NEUTRAL_FEEDBACK = (
    "The consistency check found no contradiction mark that triggers a revision for this report. Review your structured "
    "assessments once against the tool outputs anyway. If every commitment is supported, return the report unchanged."
)


def load_runs(path: Path = ARCHIVE) -> dict[tuple[str, str, int], dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {(r["scenario"], r["system"], r["repeat"]): r for r in data["runs"]}


def load_scenarios() -> dict[str, dict]:
    return {json.loads(f.read_text())["id"]: json.loads(f.read_text()) for f in SCENARIO_DIR.glob("*.json")}


def calls_of(run: dict) -> list[ToolCall]:
    return [ToolCall(name=c["name"], input=c.get("input") or {}, output=c.get("output") or "") for c in run.get("tool_calls") or []]


def feedback_for(report: dict, calls: list[ToolCall]) -> tuple[str, list[dict], bool]:
    """Feedback text from the marks. Only TRIGGER (K1) triggers a revision; other marks are listed for context."""
    flags = check_consistency(report, calls)
    trig = [f for f in flags if f.code == TRIGGER]
    if not trig:
        return NEUTRAL_FEEDBACK, [f.as_dict() for f in flags], False
    lines = ["Consistency marks on your structured assessments:"]
    for f in flags:
        who = ", ".join(str(i + 1) for i in f.assessments)
        lines.append(f"- {f.code} (assessment {who}): {f.text}. Detail: {f.detail}")
    lines.append(
        "You state station overtemperature for a group and at the same time doubt that station's temperature sensor. "
        "Check which of these commitments is actually supported by the tool outputs. Separate alternative explanations "
        "from simultaneously evidenced causes. The real temperature stays open until an independent measurement."
    )
    return "\n".join(lines), [f.as_dict() for f in flags], True


def build_messages(question: str, calls: list[ToolCall], report: dict, feedback: str) -> list[dict]:
    tool_block = "\n\n".join(
        f"[tool_call {i + 1}] {c.name}({json.dumps(c.input, ensure_ascii=False)})\n{c.output}" for i, c in enumerate(calls)
    )
    user = (
        f"Engineer question:\n{question}\n\n"
        f"Numbered tool outputs of the original run (complete evidence, frozen snapshot):\n{tool_block}\n\n"
        f"Your original report (JSON):\n{json.dumps(report, ensure_ascii=False)}\n\n"
        f"Feedback from the consistency check:\n{feedback}"
    )
    return [{"role": "system", "content": SYSTEM_PROMPT_V2 + "\n\n" + REVISION_RULES}, {"role": "user", "content": user}]


def classify(before: dict, after: dict) -> str:
    b, a = bool(before["assessments_exact"]), bool(after["assessments_exact"])
    if not b and a:
        return "fixed"
    if b and not a:
        return "degraded"
    return "unchanged_correct" if b else "unchanged_wrong"


def score_report(sc: dict, report: dict | None, calls: list[ToolCall], chunks, spec, answer: str = "") -> dict:
    r = AskResult(answer=answer, report=report, tool_calls=calls)
    s = score(sc, r, chunks, spec)
    s["flags"] = sorted(f.code for f in check_consistency(report, calls))
    return s


def call_params(model: str) -> dict:
    """Every parameter of the model call - stored with each record so the run can be reproduced."""
    params: dict = {
        "model": model,
        "max_completion_tokens": config.AGENT_MAX_TOKENS,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "investigation_report", "strict": True, "schema": REPORT_SCHEMA_V2},
        },
    }
    if model.startswith(("gpt-5", "o")):
        params["reasoning_effort"] = config.AGENT_EFFORT
    return params


def revise(client, messages: list[dict], model: str) -> dict:
    """One model call. Truncated or failed calls yield no report - they are never scored (CONCEPT §13: no_report)."""
    params = call_params(model)
    t0 = time.perf_counter()
    try:
        resp = client.chat.completions.create(messages=messages, **params)
    except Exception as e:  # noqa: BLE001 - logged per case, the trial continues with the next case
        return {
            "report": None,
            "text": "",
            "usage": Usage().__dict__,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "error": f"api_error: {type(e).__name__}: {str(e)[:300]}",
            "params": params,
        }
    ms = int((time.perf_counter() - t0) * 1000)
    u = Usage()
    u.input_tokens = getattr(resp.usage, "prompt_tokens", 0) or 0
    u.output_tokens = getattr(resp.usage, "completion_tokens", 0) or 0
    choice = resp.choices[0]
    text = choice.message.content or ""
    if choice.finish_reason == "length":
        return {
            "report": None,
            "text": text,
            "usage": u.__dict__,
            "latency_ms": ms,
            "error": "revision truncated (max_completion_tokens) - not scored",
            "params": params,
        }
    if choice.finish_reason == "content_filter":
        return {
            "report": None,
            "text": text,
            "usage": u.__dict__,
            "latency_ms": ms,
            "error": "model refused (content filter)",
            "params": params,
        }
    return {"report": parse_report(text), "text": text, "usage": u.__dict__, "latency_ms": ms, "error": None, "params": params}


def precheck(runs: dict, scen: dict, chunks, spec) -> list[str]:
    """Trial preconditions, checked BEFORE any paid call. Any violation invalidates the trial."""
    problems = []
    for scenario, rep_i, kind in CASES:
        run = runs.get((scenario, "v2", rep_i))
        if not run or not run.get("report"):
            problems.append(f"{scenario} r{rep_i}: kein Report im Archiv")
            continue
        calls = calls_of(run)
        before = score_report(scen[scenario], run["report"], calls, chunks, spec, run.get("answer") or "")
        _, _, triggered = feedback_for(run["report"], calls)
        if kind == "k1":
            if not triggered:
                problems.append(f"{scenario} r{rep_i}: K1-Fall ohne K1-Marke")
            if before["assessments_exact"]:
                problems.append(f"{scenario} r{rep_i}: K1-Fall ist bereits exakt")
        else:
            if triggered:
                problems.append(f"{scenario} r{rep_i}: Kontrollfall trägt K1")
            if not before["assessments_exact"]:
                problems.append(f"{scenario} r{rep_i}: Kontrollfall ist nicht exakt")
    return problems


def run_case(client, case: tuple, runs: dict, scen: dict, chunks, spec, model: str) -> dict:
    scenario, rep_i, kind = case
    run = runs[(scenario, "v2", rep_i)]
    calls, report, sc = calls_of(run), run["report"], scen[scenario]
    before = score_report(sc, report, calls, chunks, spec, run.get("answer") or "")
    feedback, flags, _ = feedback_for(report, calls)
    messages = build_messages(sc["question"], calls, report, feedback)
    out = revise(client, messages, model)
    new_report = out["report"]
    after = score_report(sc, new_report, calls, chunks, spec, (new_report or {}).get("answer_markdown", "")) if new_report else None
    result = classify(before, after) if after else ("api_error" if (out["error"] or "").startswith("api_error") else "no_report")
    u = Usage()
    u.input_tokens, u.output_tokens = out["usage"]["input_tokens"], out["usage"]["output_tokens"]
    return {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "scenario": scenario,
        "system": "v2",
        "repeat": rep_i,
        "kind": kind,
        "trigger": TRIGGER,
        "prompt_version": config.PROMPT_VERSION,
        "params": out["params"],
        "client": {"max_retries": RETRIES, "timeout_s": TIMEOUT_S},
        "code": code_version(),
        "request": messages,
        "feedback_flags": flags,
        "response_text": out["text"],
        "revised_report": new_report,
        "original_report": report,
        "before": before,
        "after": after,
        "result": result,
        "finding_before": derive_finding(report),
        "finding_after": derive_finding(new_report) if new_report else None,
        "usage": out["usage"],
        "cost_usd": round(u.cost_usd(model), 5),
        "latency_ms": out["latency_ms"],
        "error": out["error"],
        "prompt_chars": sum(len(m["content"]) for m in messages),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--model", default=None, help="default: gpt-5 as in run 4")
    ap.add_argument("--resume", default=None, help="existing protocol file: skip cases already recorded there and append")
    args = ap.parse_args()
    model = args.model or "gpt-5"

    runs, scen = load_runs(), load_scenarios()
    spec = load_spec()
    chunks = []
    try:
        from ecu_copilot.rag.index import DocumentIndex

        idx = DocumentIndex().load()
        chunks = getattr(idx, "chunks", None) or getattr(idx, "_chunks", []) or []
    except Exception as e:  # noqa: BLE001 - doc provenance then reads as not_found; say so
        print(f"(Dokumentindex nicht geladen: {e}; Dokument-Herkunft wird nicht bewertet)")

    problems = precheck(runs, scen, chunks, spec)
    if problems:
        print("Versuch ungültig - Voraussetzungen verletzt, nichts gesendet:")
        for p in problems:
            print("  -", p)
        return 2

    client = None
    if args.send:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
        import openai

        client = openai.OpenAI(max_retries=RETRIES, timeout=TIMEOUT_S)
    log = OUT_DIR / f"revision-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.jsonl"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    done: set[tuple[str, int]] = set()
    if args.resume:
        log = Path(args.resume)
        for line in log.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            done.add((rec["scenario"], rec["repeat"]))
        print(f"Fortsetzung: {len(done)} Fälle bereits in {log.name}, werden übersprungen")

    print(f"{'Fall':<26}{'Art':<9}{'vorher':<8}{'Marken':<12}{'~Token':<8}{'nachher':<9}{'Marken':<12}{'Ergebnis'}")
    tally: dict[str, int] = {}
    total_cost = 0.0
    for case in CASES:
        scenario, rep_i, kind = case
        label = f"{scenario[:22]} r{rep_i}"
        if (scenario, rep_i) in done:
            continue
        if not args.send:
            run = runs[(scenario, "v2", rep_i)]
            calls = calls_of(run)
            before = score_report(scen[scenario], run["report"], calls, chunks, spec, run.get("answer") or "")
            feedback, _, _ = feedback_for(run["report"], calls)
            size = sum(len(m["content"]) for m in build_messages(scen[scenario]["question"], calls, run["report"], feedback))
            print(
                f"{label:<26}{kind:<9}{'exakt' if before['assessments_exact'] else 'nicht':<8}{','.join(before['flags']) or '-':<12}{size // 4:<8}{'(dry)':<9}{'':<12}-"
            )
            continue
        rec = run_case(client, case, runs, scen, chunks, spec, model)
        tally[rec["result"]] = tally.get(rec["result"], 0) + 1
        total_cost += rec["cost_usd"]
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        after = rec["after"]
        print(
            f"{label:<26}{kind:<9}{'exakt' if rec['before']['assessments_exact'] else 'nicht':<8}{','.join(rec['before']['flags']) or '-':<12}{rec['prompt_chars'] // 4:<8}"
            f"{('exakt' if after and after['assessments_exact'] else 'nicht'):<9}{(','.join(after['flags']) if after else '?') or '-':<12}{rec['result']} · {rec['cost_usd']:.3f}$ · {rec['latency_ms']} ms{' · ' + rec['error'] if rec['error'] else ''}"
        )
    if args.send:
        print(f"\nErgebnis: {tally} · Kosten {total_cost:.3f} USD · Protokoll {log}")
    else:
        print("\nNichts gesendet. Echte Aufrufe nur mit --send nach Freigabe (CONCEPT §13 Stufe b).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
