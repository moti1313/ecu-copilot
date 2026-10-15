"""The agent loop, production shape: SDK tool runner + system prompt + guardrails + accounting.

Compare with hello_agent.py (the same loop by hand). What is added here:
- a system prompt with the domain rules (cite, compare live data with the spec, say "unknown")
- prompt caching on the system prompt (the stable prefix is paid once, then ~10 %)
- usage summed over all iterations -> cost per question
- a trace of every tool call for the UI and the evals
- output guardrail: a documentation answer without a citation is flagged
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field

import anthropic

from .. import config
from .metrics import MetricsStore, QuestionRecord, Usage, now_iso
from .telemetry import current_trace_id
from .tools import ALL_TOOLS

SYSTEM_PROMPT = """You are the ECU Copilot, an assistant for test and electronics engineers on the end-of-line (EOL) test line for door control units DCU-A1 (variant A) and DCU-B2 (variant B). Three stations: EOL-1 tests A, EOL-2 tests A and B, EOL-3 tests B.

You have tools for live test data (get_station_stats, get_recent_results), the engineering documentation (search_docs: EOL test specification, datasheets, FMEA, PCN, work instructions), the bill of materials (lookup_part) and for drafting 8D reports (draft_8d_report).

How to work
1. For any question about the current state of the line ("why are units failing", "what is going on", rates, trends): first call get_station_stats, usually for two windows (e.g. 10 and 60 minutes) to see what changed. Then get_recent_results for the affected station/variant to look at lots and measurements.
2. Compare the measurements with the specification. Use search_docs to get limits, validity conditions and first checks - never quote a limit from memory. Write search queries in English; the documents are English.
3. Distinguish pseudo failures (test environment out of specification: temperature window, background noise) from real failures (unit defective, often lot-related). State explicitly which one the evidence supports and how confident you are.
4. Cite every document fact with its citation in parentheses, e.g. (TS-DCU-EOL §4.2) or (FMEA-DCU-B2 item 7). Cite live data with the window and numbers, e.g. "station 2, variant B, last 10 min: 13.4 % (E-204: 28)".
5. If the documents do not contain the answer, say so. Do not invent limits, part numbers, dates or procedures.
6. Only create an 8D report when asked for one, and only after gathering evidence.
7. Answer in the language of the question (German or English). Be concise and structured: Befund / Belege / Empfehlung (or Finding / Evidence / Recommendation). Numbers with units. No filler.
8. Stay within the domain (EOL test, electronics, components, quality). For anything else, say briefly that it is outside your scope."""

MAX_QUESTION_CHARS = 2000
_CITATION = re.compile(r"(TS-DCU-EOL|DS-MCU-XM32F7|DS-DRV-HB4821|FMEA-DCU-B2|PCN-2026-017|WI-EOL-PSEUDO)\b")


@dataclass
class ToolCall:
    name: str
    input: dict
    result_preview: str = ""


@dataclass
class AskResult:
    answer: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    cost_usd: float = 0.0
    latency_s: float = 0.0
    iterations: int = 0
    stop_reason: str | None = None
    citation_missing: bool = False
    trace_id: str | None = None
    model: str = config.AGENT_MODEL
    prompt_version: str = config.PROMPT_VERSION
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class Copilot:
    def __init__(
        self,
        client: anthropic.Anthropic | None = None,
        model: str | None = None,
        metrics: MetricsStore | None = None,
        max_iterations: int = 10,
    ) -> None:
        self.client = client or anthropic.Anthropic()
        self.model = model or config.AGENT_MODEL
        self.metrics = metrics
        self.max_iterations = max_iterations

    def ask(self, question: str, history: list[dict] | None = None) -> AskResult:
        t0 = time.perf_counter()
        question = (question or "").strip()
        if not question:
            return self._finish(AskResult(answer="", error="empty question"), question, t0)
        if len(question) > MAX_QUESTION_CHARS:  # input guardrail
            return self._finish(AskResult(answer="", error=f"question longer than {MAX_QUESTION_CHARS} characters"), question, t0)

        messages = list(history or []) + [{"role": "user", "content": question}]
        result = AskResult(model=self.model)
        usage = Usage()
        try:
            runner = self.client.beta.messages.tool_runner(
                model=self.model,
                max_tokens=config.AGENT_MAX_TOKENS,
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                tools=ALL_TOOLS,
                messages=messages,
                output_config={"effort": config.AGENT_EFFORT},
                max_iterations=self.max_iterations,
            )
            last = None
            for message in runner:
                last = message
                result.iterations += 1
                usage.add(message.usage)
                calls = {b.id: ToolCall(name=b.name, input=dict(b.input)) for b in message.content if b.type == "tool_use"}
                tool_response = runner.generate_tool_call_response()  # runs the tools (cached by the runner)
                if tool_response is not None:
                    for block in tool_response["content"]:
                        call = calls.get(block["tool_use_id"])
                        if call is not None:
                            call.result_preview = str(block["content"])[:300]
                result.tool_calls.extend(calls.values())
            if last is not None:
                result.stop_reason = last.stop_reason
                result.answer = "".join(b.text for b in last.content if b.type == "text")
                if last.stop_reason == "max_tokens":
                    result.error = "answer truncated (max_tokens)"
                elif last.stop_reason == "refusal":
                    result.error = "model refused"
        except anthropic.AuthenticationError as e:
            result.error = f"authentication failed: {e.message}"
        except anthropic.RateLimitError:
            result.error = "rate limited - retry later"
        except anthropic.APIStatusError as e:
            result.error = f"API error {e.status_code}: {e.message}"
        except anthropic.APIConnectionError as e:
            result.error = f"connection error: {e}"
        except Exception as e:  # noqa: BLE001 - e.g. the SDK raises TypeError when no credentials are configured
            result.error = f"{type(e).__name__}: {str(e)[:300]}"

        result.usage = asdict(usage)
        result.cost_usd = round(usage.cost_usd(self.model), 5)
        used_docs = any(c.name == "search_docs" for c in result.tool_calls)
        result.citation_missing = bool(result.answer) and used_docs and not _CITATION.search(result.answer)
        return self._finish(result, question, t0)

    def _finish(self, result: AskResult, question: str, t0: float) -> AskResult:
        result.latency_s = round(time.perf_counter() - t0, 2)
        result.trace_id = current_trace_id()
        if self.metrics is not None:
            self.metrics.record(
                QuestionRecord(
                    timestamp=now_iso(),
                    question=question[:500],
                    model=result.model,
                    prompt_version=result.prompt_version,
                    latency_s=result.latency_s,
                    iterations=result.iterations,
                    tools=[c.name for c in result.tool_calls],
                    usage=result.usage,
                    cost_usd=result.cost_usd,
                    citation_missing=result.citation_missing,
                    error=result.error,
                    trace_id=result.trace_id,
                )
            )
        return result
