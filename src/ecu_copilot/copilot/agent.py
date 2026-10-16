"""The agent loop, production shape: system prompt + tools + guardrails + accounting,
behind one interface for two providers and two profiles.

Providers: `Copilot` (Anthropic tool runner, prompt caching, SDK spans) and `OpenAICopilot`
(chat completions + function calling, loop written by hand).

Profiles (for the benchmark, see design/CONCEPT.md):
- v1: the original five tools and a single `finding`.
- v2: + deterministic engineering tools (validity, change, clusters, descriptors), `assessments`
  per affected group (test validity separate from defect indication), structured evidence refs,
  and a verification pass (copilot/verify.py) that checks every evidence item after the model.

Compare with examples/hello_agent.py (the loop by hand). What is added here: domain rules in the
prompt; usage summed over all iterations -> cost per question; a trace of every tool call (args,
duration, output) for the UI, the verifier and the evals; output guardrails.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field

from opentelemetry import trace

from .. import config
from .metrics import MetricsStore, QuestionRecord, Usage, now_iso
from .telemetry import current_trace_id
from .tools import tools_for

tracer = trace.get_tracer("ecu-copilot.agent")

_DOMAIN = """You are the ECU Copilot, an assistant for test and electronics engineers on the end-of-line (EOL) test line for door control units DCU-A1 (variant A) and DCU-B2 (variant B). Three stations: EOL-1 tests A, EOL-2 tests A and B, EOL-3 tests B."""

_RULES_COMMON = """3. Distinguish pseudo failures (test environment out of specification: temperature window, background noise) from real failures (unit defective, often lot-related). State explicitly which one the evidence supports and how strong that evidence is. An INVALID test is not a statement about the unit: "pseudo failure" means "this result allows no reliable assessment of the unit - re-test under valid conditions", never "the unit is fine". A unit can be defective in addition. If evidence for both exists (e.g. invalid temperature AND failures concentrated on one lot), report both and do not explain one away with the other.
4. Cite every document fact with its citation in parentheses, e.g. (TS-DCU-EOL §4.2) or (FMEA-DCU-B2 item 7). Cite live data with the window and numbers, e.g. "station 2, variant B, last 10 min: 13.4 % (E-204: 28)".
5. If the documents do not contain the answer, say so. Do not invent limits, part numbers, dates or procedures.
6. Only create an 8D report when asked for one, and only after gathering evidence.
7. Answer in the language of the question (German or English). Be concise and structured. Numbers with units. No filler.
8. Stay within the domain (EOL test, electronics, components, quality). For anything else, say briefly that it is outside your scope."""

SYSTEM_PROMPT_V1 = f"""{_DOMAIN}

You have tools for live test data (get_station_stats, get_recent_results), the engineering documentation (search_docs: EOL test specification, datasheets, FMEA, PCN, work instructions), the bill of materials (lookup_part) and for drafting 8D reports (draft_8d_report).

How to work
1. For any question about the current state of the line ("why are units failing", "what is going on", rates, trends): first call get_station_stats, usually for two windows (e.g. 10 and 60 minutes) to see what changed. Then get_recent_results for the affected station/variant to look at lots and measurements.
2. Compare the measurements with the specification. Use search_docs to get limits, validity conditions and first checks - never quote a limit from memory. Write search queries in English; the documents are English.
{_RULES_COMMON}

Output format
Your final message is a JSON object (the schema is enforced). Fields:
- answer_markdown: the complete answer for the engineer, structured as "Befund / Belege / Empfehlung" (or Finding / Evidence / Recommendation).
- finding: "pseudo_failure" | "real_failure" | "unclear" | "information" (information = a documentation or parts question without a line incident).
- hypotheses: the explanations you considered. support: "strong" = at least one live observation AND one document rule point the same way and no evidence contradicts; "moderate" = evidence points one way but a check is still open; "weak" = possible but not supported by the data; "rejected" = contradicted by the data. Never express support as a number. A hypothesis is "durch Evidenz gestützt" / "supported by evidence", never "bestätigt" / "confirmed" before the proposed test has run. For pure information questions the list may be empty.
- evidence: every fact you rely on: statement (with numbers), source_type "live" or "document", citation (document section like "TS-DCU-EOL §4.2", or the live window like "EOL-2 / B / 10 min"), supports (title of the hypothesis it supports, or "").
- next_test: the single next action for the engineer to approve (title, expectation if the leading hypothesis holds, duration, block_units true only if units must be blocked), or null for information questions.
- affected_components: codes of the components involved: U1 (MCU), U3 (LIN transceiver), U7 (H-bridge driver), U12 (antenna front-end), J3 (vehicle connector), T1 (station temperature sensor), MIC (acoustic cell microphone), MOTOR, GEAR, FIXTURE (motor load fixture), SERVICE_IF (flash/service interface). Empty if none."""

_RULES_REFS = """9. Every live evidence item must carry a ref: the tool call number (1 = first call of this run), the exact field in that call's output (e.g. "codes.E-204.invalid_per_spec", "groups[station=2,variant=B].failure_rate_pct", "top.rate_ratio"), the station/variant/window it refers to, and the value. A value from station 1 is no evidence about station 2. Every document evidence item must carry doc_id, revision if known, and the section number.
10. Propose a next test that DISCRIMINATES between your hypotheses (its result must come out differently if H1 is true vs H2), and say what you expect in each case.
11. One evidence item = one field = one value. Never pack several fields into one ref (no "{a, b, c}"); make separate items. Write the section as a plain number ("4.2", not "§4.2") and the revision as a plain letter ("D")."""

SYSTEM_PROMPT_V2 = f"""{_DOMAIN}

You have deterministic engineering tools that compute checked evidence from the live test data - check_validity (which FAIL verdicts are INVALID per specification), detect_change (when a metric changed and whether significantly), cluster_failures (is a code concentrated in a lot/firmware/station, with lift and rate ratio), describe_signal (statistics, trends, whether quiescent current follows station temperature) - plus get_station_stats (overview), get_recent_results (a few raw rows), the engineering documentation (search_docs: EOL test specification, datasheets, FMEA, PCN, work instructions), the bill of materials (lookup_part) and draft_8d_report.

How to work
1. For any question about the current state of the line: start with get_station_stats (10 min) for the overview, then detect_change for the affected station/variant BEFORE you say "since X minutes" or "rising", then check_validity BEFORE you say anything about validity or pseudo failures, cluster_failures (by lot, then by firmware) BEFORE you name a lot or version, and describe_signal when temperature or current are involved. Do not compute rates, trends or validity yourself from raw rows - the tools do that; you integrate and explain.
2. Compare the tool results with the specification. Use search_docs to get limits, validity conditions and first checks - never quote a limit from memory. Write search queries in English; the documents are English.
{_RULES_COMMON}
{_RULES_REFS}
13. This rule is about additional explanations for the LINE STATE: the line has a normal background failure rate (around 1-3 %, a few isolated units with mixed codes, no significant change, no concentration). Do not turn that background into a further assessment with defect_indication "suspected" and root_cause "unknown" - an assessment is a claim about a group and must be backed by a change, a concentration or an invalidity. Individual real failures inside the background rate remain visible and investigable: list them in the text (serial, code) so the engineer can look at them; just do not present them as a line-level cause.
12. If check_validity, detect_change, cluster_failures or describe_signal return an error, do NOT replace them with your own calculation from stats or raw rows: set test_validity to "unknown", say which check could not be run, and recommend re-running it. A conclusion without the engineering checks is not allowed.

Output format
Your final message is a JSON object (the schema is enforced). Fields:
- answer_markdown: the complete answer for the engineer, "Befund / Belege / Empfehlung" (or Finding / Evidence / Recommendation).
- assessments: one entry per affected group (scope: station, variant, lot or null). test_validity: "valid" | "invalid_temperature" | "invalid_noise" | "invalid_fixture" | "unknown". defect_indication: "none_assessable" (test invalid, unit cannot be assessed) | "none" | "suspected" | "strong". root_cause: one of station_temperature, cell_noise, fixture, sensor_t1, firmware, connector_lot, component_u1, component_u7, component_u12, unknown, none. Concurrent causes are separate entries (e.g. invalid_temperature for station 2/B AND a connector_lot entry for the lot). For pure information questions the list is empty.
- hypotheses: title, support ("strong" | "moderate" | "weak" | "rejected" - never a number; "supported by evidence", never "confirmed" before the test ran), rationale, and test: {{title, discriminates: [hypothesis titles], prediction_if_true, prediction_if_false}} or null.
- evidence: statement (with numbers), source_type "live" | "document", ref (see rule 9), citation (human-readable, e.g. "TS-DCU-EOL §4.2" or "EOL-2 / B / 10 min"), supports (hypothesis title or "").
- next_test: {{title, expectation, duration, units: [serials if specific], block_units}} or null.
- affected_components: U1, U3, U7, U12, J3, T1, MIC, MOTOR, GEAR, FIXTURE, SERVICE_IF.
- routing: which paths you used: "live", "docs", "parts"."""

_HYPOTHESIS_V2 = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "support": {"type": "string", "enum": ["strong", "moderate", "weak", "rejected"]},
        "rationale": {"type": "string"},
        "test": {
            "anyOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "discriminates": {"type": "array", "items": {"type": "string"}},
                        "prediction_if_true": {"type": "string"},
                        "prediction_if_false": {"type": "string"},
                    },
                    "required": ["title", "discriminates", "prediction_if_true", "prediction_if_false"],
                },
                {"type": "null"},
            ]
        },
    },
    "required": ["title", "support", "rationale", "test"],
}

_EVIDENCE_REF_V2 = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "tool_call": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
        "field": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "station": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
        "variant": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "window_minutes": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
        "value": {"anyOf": [{"type": "number"}, {"type": "string"}, {"type": "boolean"}, {"type": "null"}]},
        "doc_id": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "revision": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "section": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    },
    "required": ["tool_call", "field", "station", "variant", "window_minutes", "value", "doc_id", "revision", "section"],
}

COMPONENTS = ["U1", "U3", "U7", "U12", "J3", "T1", "MIC", "MOTOR", "GEAR", "FIXTURE", "SERVICE_IF"]
ROOT_CAUSES = [
    "station_temperature",
    "cell_noise",
    "fixture",
    "sensor_t1",
    "firmware",
    "connector_lot",
    "component_u1",
    "component_u7",
    "component_u12",
    "unknown",
    "none",
]

REPORT_SCHEMA_V2 = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "answer_markdown": {"type": "string"},
        "assessments": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "scope": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "station": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                            "variant": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                            "lot": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                        },
                        "required": ["station", "variant", "lot"],
                    },
                    "test_validity": {
                        "type": "string",
                        "enum": ["valid", "invalid_temperature", "invalid_noise", "invalid_fixture", "unknown"],
                    },
                    "defect_indication": {"type": "string", "enum": ["none_assessable", "none", "suspected", "strong"]},
                    "root_cause": {"type": "string", "enum": ROOT_CAUSES},
                },
                "required": ["scope", "test_validity", "defect_indication", "root_cause"],
            },
        },
        "hypotheses": {"type": "array", "items": _HYPOTHESIS_V2},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "statement": {"type": "string"},
                    "source_type": {"type": "string", "enum": ["live", "document"]},
                    "ref": _EVIDENCE_REF_V2,
                    "citation": {"type": "string"},
                    "supports": {"type": "string"},
                },
                "required": ["statement", "source_type", "ref", "citation", "supports"],
            },
        },
        "next_test": {
            "anyOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "expectation": {"type": "string"},
                        "duration": {"type": "string"},
                        "units": {"type": "array", "items": {"type": "string"}},
                        "block_units": {"type": "boolean"},
                    },
                    "required": ["title", "expectation", "duration", "units", "block_units"],
                },
                {"type": "null"},
            ]
        },
        "affected_components": {"type": "array", "items": {"type": "string", "enum": COMPONENTS}},
        "routing": {"type": "array", "items": {"type": "string", "enum": ["live", "docs", "parts"]}},
    },
    "required": ["answer_markdown", "assessments", "hypotheses", "evidence", "next_test", "affected_components", "routing"],
}

REPORT_SCHEMA_V1 = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "answer_markdown": {"type": "string"},
        "finding": {"type": "string", "enum": ["pseudo_failure", "real_failure", "unclear", "information"]},
        "hypotheses": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "support": {"type": "string", "enum": ["strong", "moderate", "weak", "rejected"]},
                    "rationale": {"type": "string"},
                },
                "required": ["title", "support", "rationale"],
            },
        },
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "statement": {"type": "string"},
                    "source_type": {"type": "string", "enum": ["live", "document"]},
                    "citation": {"type": "string"},
                    "supports": {"type": "string"},
                },
                "required": ["statement", "source_type", "citation", "supports"],
            },
        },
        "next_test": {
            "anyOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "expectation": {"type": "string"},
                        "duration": {"type": "string"},
                        "block_units": {"type": "boolean"},
                    },
                    "required": ["title", "expectation", "duration", "block_units"],
                },
                {"type": "null"},
            ]
        },
        "affected_components": {"type": "array", "items": {"type": "string", "enum": COMPONENTS}},
    },
    "required": ["answer_markdown", "finding", "hypotheses", "evidence", "next_test", "affected_components"],
}

# v1s = the V1 tools with the V2 report format: separates the effect of the engineering tools from the
# effect of the richer schema (reviewer request, design/RESULTS.md run 1).
SYSTEM_PROMPT_V1S = (
    SYSTEM_PROMPT_V1.split("Output format")[0] + _RULES_REFS + "\n\nOutput format" + SYSTEM_PROMPT_V2.split("Output format")[1]
)

PROFILES = {
    "v1": (SYSTEM_PROMPT_V1, REPORT_SCHEMA_V1),
    "v1s": (SYSTEM_PROMPT_V1S, REPORT_SCHEMA_V2),
    "v2": (SYSTEM_PROMPT_V2, REPORT_SCHEMA_V2),
}
REPORT_SCHEMA = REPORT_SCHEMA_V2
SYSTEM_PROMPT = SYSTEM_PROMPT_V2

MAX_QUESTION_CHARS = 2000
_CITATION = re.compile(r"(TS-DCU-EOL|DS-MCU-XM32F7|DS-DRV-HB4821|FMEA-DCU-B2|PCN-2026-017|WI-EOL-PSEUDO)\b")


@dataclass
class ToolCall:
    name: str
    input: dict
    result_preview: str = ""
    summary: str = ""  # one line for the UI: "3 Treffer: TS-DCU-EOL §4.2, §5 …"
    duration_ms: int = 0
    output: str = ""  # full output, kept for the verifier; stripped from the API payload


@dataclass
class AskResult:
    answer: str = ""
    report: dict | None = None  # parsed report (v1 or v2 schema), None when the model returned plain text
    verification: dict | None = None  # copilot/verify.py summary (v2)
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    cost_usd: float = 0.0
    latency_s: float = 0.0
    iterations: int = 0
    stop_reason: str | None = None
    citation_missing: bool = False
    trace_id: str | None = None
    provider: str = config.LLM_PROVIDER
    model: str = config.AGENT_MODEL
    profile: str = config.AGENT_PROFILE
    prompt_version: str = config.PROMPT_VERSION
    error: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        for c in d["tool_calls"]:
            c.pop("output", None)
        return d


def summarize_tool_output(name: str, output: str) -> str:
    """What the UI shows next to a tool call. Never raises."""
    try:
        data = json.loads(output)
    except (TypeError, ValueError):
        return str(output)[:120]
    if isinstance(data, dict) and "error" in data:
        return f"Fehler: {data['error']}"
    if name == "search_docs" and isinstance(data, list):
        return f"{len(data)} Treffer: " + ", ".join(h.get("citation", "?") for h in data[:5])
    if name == "get_station_stats" and isinstance(data, dict):
        groups = data.get("groups", [])
        parts = [f"EOL-{g['station']}/{g['variant']} {g['failure_rate_pct']} %" for g in groups]
        return f"{data.get('window_minutes')} min · " + " · ".join(parts)
    if name == "get_recent_results" and isinstance(data, dict):
        codes = ", ".join(f"{k} ×{v}" for k, v in data.get("by_failure_code", {}).items())
        lots = ", ".join(f"{k} ×{v}" for k, v in data.get("by_lot", {}).items())
        return f"{data.get('count')} Ergebnisse · {codes or 'keine Fehler'} · Lose: {lots or '–'}"
    if name == "lookup_part" and isinstance(data, list):
        return ", ".join(f"{p['part_number']} ({p['status']})" for p in data[:4])
    if name == "draft_8d_report" and isinstance(data, dict):
        return f"gespeichert: {data.get('saved_to', '?')}"
    if name == "check_validity" and isinstance(data, dict):
        codes = ", ".join(f"{c}: {v['invalid_per_spec']}/{v['fail_verdicts']} INVALID" for c, v in data.get("codes", {}).items())
        return f"{data.get('fail_verdicts')} FAIL, {data.get('invalid_per_spec')} davon INVALID per Spec · {codes or '–'}"
    if name == "detect_change" and isinstance(data, dict):
        if data.get("reason"):
            return f"{data.get('metric')}: {data['reason']}"
        return (
            f"{data.get('metric')}: {data.get('level_before')} → {data.get('level_after')} ab {str(data.get('onset', ''))[11:16]} "
            f"(z={data.get('z')}, {'signifikant' if data.get('significant') else 'nicht signifikant'})"
        )
    if name == "cluster_failures" and isinstance(data, dict):
        top = data.get("top") or {}
        return (
            f"nach {data.get('by')}: {'konzentriert' if data.get('concentrated') else 'nicht konzentriert'} · "
            f"top {top.get('group')} ({top.get('failed')} Fehler, Rate ×{top.get('rate_ratio')}, Lift {top.get('lift')})"
        )
    if name == "describe_signal" and isinstance(data, dict):
        return f"{data.get('iq_t1_relation')} · " + ("; ".join(data.get("flags", [])[:2]) or "keine Auffälligkeit")
    return str(output)[:120]


def derive_finding(report: dict) -> str:
    """v2 reports carry assessments; the UI, metrics and golden set still use a single finding label."""
    if "finding" in report:
        return report["finding"]
    assessments = report.get("assessments") or []
    if not assessments:
        return "information"
    invalid = any(a.get("test_validity", "").startswith("invalid") for a in assessments)
    defect = any(a.get("defect_indication") in ("suspected", "strong") for a in assessments)
    if invalid and defect:
        return "mixed"
    if invalid:
        return "pseudo_failure"
    if defect:
        return "real_failure"
    return "unclear"


def parse_report(text: str) -> dict | None:
    """The final message should be the JSON report; tolerate a fenced block or stray text around it."""
    if not text:
        return None
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.S)
    try:
        data = json.loads(candidate)
    except ValueError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(candidate[start : end + 1])
        except ValueError:
            return None
    if not isinstance(data, dict) or "answer_markdown" not in data:
        return None
    data.setdefault("hypotheses", [])
    data.setdefault("evidence", [])
    data.setdefault("next_test", None)
    data.setdefault("affected_components", [])
    if "assessments" not in data and "finding" not in data:
        data["finding"] = "information"
    data.setdefault("assessments", [])
    data.setdefault("routing", [])
    data["finding"] = derive_finding(data)
    return data


class Copilot:
    """Anthropic implementation. Subclasses override `_run` (the loop) and `_describe_error`."""

    provider = "anthropic"

    def __init__(
        self,
        client=None,
        model: str | None = None,
        metrics: MetricsStore | None = None,
        max_iterations: int = 12,
        profile: str | None = None,
        verifier=None,
    ) -> None:
        self.client = client
        self.model = model or config.AGENT_MODEL
        self.metrics = metrics
        self.max_iterations = max_iterations
        self.profile = profile or config.AGENT_PROFILE
        self.system_prompt, self.schema = PROFILES[self.profile]
        self.tools = tools_for(self.profile)
        self.verifier = verifier  # callable(report, tool_calls) -> dict | None; default built lazily

    # --- shared: guardrails, accounting, logging -------------------------------------
    def ask(self, question: str, history: list[dict] | None = None) -> AskResult:
        t0 = time.perf_counter()
        question = (question or "").strip()
        result = AskResult(provider=self.provider, model=self.model, profile=self.profile)
        if not question:
            result.error = "empty question"
            return self._finish(result, question, t0)
        if len(question) > MAX_QUESTION_CHARS:  # input guardrail
            result.error = f"question longer than {MAX_QUESTION_CHARS} characters"
            return self._finish(result, question, t0)

        messages = list(history or []) + [{"role": "user", "content": question}]
        usage = Usage()
        try:
            self._run(messages, result, usage)
        except Exception as e:  # noqa: BLE001 - every failure becomes a logged, visible error, never a 500
            result.error = self._describe_error(e)

        # the model's final text is the JSON report; the human answer lives inside it
        result.report = parse_report(result.answer)
        if result.report is not None:
            result.answer = result.report["answer_markdown"]
            if self.profile == "v2":
                result.verification = self._verify(result)

        result.usage = asdict(usage)
        result.cost_usd = round(usage.cost_usd(self.model), 5)
        used_docs = any(c.name == "search_docs" for c in result.tool_calls)
        result.citation_missing = bool(result.answer) and used_docs and not _CITATION.search(result.answer)
        return self._finish(result, question, t0)

    def _verify(self, result: AskResult) -> dict | None:
        try:
            if self.verifier is not None:
                return self.verifier(result.report, result.tool_calls)
            from ..engineering.spec import load_spec
            from . import tools as _tools
            from .verify import verify_report

            chunks = _tools._get_index()._chunks
            return verify_report(result.report, result.tool_calls, chunks, load_spec()).summary()
        except Exception as e:  # noqa: BLE001 - verification must never break the answer; its absence is visible
            return {"error": f"verification unavailable: {e}"}

    def _finish(self, result: AskResult, question: str, t0: float) -> AskResult:
        result.latency_s = round(time.perf_counter() - t0, 2)
        result.trace_id = current_trace_id()
        if self.metrics is not None:
            self.metrics.record(
                QuestionRecord(
                    timestamp=now_iso(),
                    question=question[:500],
                    model=f"{result.provider}:{result.model}:{result.profile}",
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

    # --- Anthropic loop ------------------------------------------------------------------
    def _client(self):
        if self.client is None:
            import anthropic

            self.client = anthropic.Anthropic()
        return self.client

    def _run(self, messages: list[dict], result: AskResult, usage: Usage) -> None:
        runner = self._client().beta.messages.tool_runner(
            model=self.model,
            max_tokens=config.AGENT_MAX_TOKENS,
            system=[{"type": "text", "text": self.system_prompt, "cache_control": {"type": "ephemeral"}}],
            tools=self.tools,
            messages=messages,
            output_config={"effort": config.AGENT_EFFORT, "format": {"type": "json_schema", "schema": self.schema}},
            max_iterations=self.max_iterations,
        )
        last = None
        for message in runner:
            last = message
            result.iterations += 1
            usage.add(message.usage)
            calls = {b.id: ToolCall(name=b.name, input=dict(b.input)) for b in message.content if b.type == "tool_use"}
            t_tools = time.perf_counter()
            tool_response = runner.generate_tool_call_response()  # runs the tools (cached by the runner)
            batch_ms = int((time.perf_counter() - t_tools) * 1000)
            if tool_response is not None:
                for block in tool_response["content"]:
                    call = calls.get(block["tool_use_id"])
                    if call is not None:
                        output = str(block["content"])
                        call.output = output
                        call.result_preview = output[:300]
                        call.summary = summarize_tool_output(call.name, output)
                        call.duration_ms = batch_ms // max(1, len(calls))  # the runner times the batch, not each tool
            result.tool_calls.extend(calls.values())
        if last is not None:
            result.stop_reason = last.stop_reason
            result.answer = "".join(b.text for b in last.content if b.type == "text")
            if last.stop_reason == "max_tokens":
                result.error = "answer truncated (max_tokens)"
            elif last.stop_reason == "refusal":
                result.error = "model refused"

    def _describe_error(self, e: Exception) -> str:
        import anthropic

        if isinstance(e, anthropic.AuthenticationError):
            return f"authentication failed: {e.message}"
        if isinstance(e, anthropic.RateLimitError):
            return "rate limited - retry later"
        if isinstance(e, anthropic.APIStatusError):
            return f"API error {e.status_code}: {e.message}"
        if isinstance(e, anthropic.APIConnectionError):
            return f"connection error: {e}"
        return f"{type(e).__name__}: {str(e)[:300]}"  # e.g. TypeError when no credentials are configured


class OpenAICopilot(Copilot):
    """OpenAI implementation: chat completions + function calling, loop written by hand
    (there is no tool runner in that SDK). Same tools, same prompt, same guardrails."""

    provider = "openai"

    def _client(self):
        if self.client is None:
            import openai

            self.client = openai.OpenAI()
        return self.client

    def _tool_specs(self) -> list[dict]:
        specs = []
        for t in self.tools:
            d = t.to_dict()
            specs.append(
                {"type": "function", "function": {"name": d["name"], "description": d["description"], "parameters": d["input_schema"]}}
            )
        return specs

    def _run(self, messages: list[dict], result: AskResult, usage: Usage) -> None:
        tools_by_name = {t.to_dict()["name"]: t for t in self.tools}
        convo = [{"role": "system", "content": self.system_prompt}, *messages]
        params: dict = {
            "model": self.model,
            "tools": self._tool_specs(),
            "max_completion_tokens": config.AGENT_MAX_TOKENS,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "investigation_report", "strict": True, "schema": self.schema},
            },
        }
        if self.model.startswith(("gpt-5", "o")):
            params["reasoning_effort"] = config.AGENT_EFFORT

        for _ in range(self.max_iterations):
            with tracer.start_as_current_span("openai.chat.completions") as span:
                resp = self._client().chat.completions.create(messages=convo, **params)
                u = resp.usage
                cached = getattr(getattr(u, "prompt_tokens_details", None), "cached_tokens", 0) or 0
                usage.input_tokens += (u.prompt_tokens or 0) - cached
                usage.cache_read_input_tokens += cached
                usage.output_tokens += u.completion_tokens or 0
                span.set_attribute("gen_ai.request.model", self.model)
                span.set_attribute("gen_ai.usage.input_tokens", u.prompt_tokens or 0)
                span.set_attribute("gen_ai.usage.output_tokens", u.completion_tokens or 0)
            result.iterations += 1
            choice = resp.choices[0]
            msg = choice.message
            result.stop_reason = choice.finish_reason
            convo.append({"role": "assistant", "content": msg.content, "tool_calls": [tc.model_dump() for tc in msg.tool_calls or []]})

            if not msg.tool_calls:
                result.answer = msg.content or ""
                if choice.finish_reason == "length":
                    result.error = "answer truncated (max_completion_tokens)"
                elif choice.finish_reason == "content_filter":
                    result.error = "model refused (content filter)"
                return

            for tc in msg.tool_calls:  # run every call, return every result (one tool message each)
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                call = ToolCall(name=tc.function.name, input=args)
                tool = tools_by_name.get(tc.function.name)
                t_tool = time.perf_counter()
                with tracer.start_as_current_span(f"tool.{tc.function.name}"):
                    output = tool.call(args) if tool else json.dumps({"error": f"unknown tool {tc.function.name}"})
                call.duration_ms = int((time.perf_counter() - t_tool) * 1000)
                call.output = str(output)
                call.result_preview = str(output)[:300]
                call.summary = summarize_tool_output(call.name, str(output))
                result.tool_calls.append(call)
                convo.append({"role": "tool", "tool_call_id": tc.id, "content": str(output)})
        result.error = f"stopped after {self.max_iterations} iterations"

    def _describe_error(self, e: Exception) -> str:
        import openai

        if isinstance(e, openai.AuthenticationError):
            return "authentication failed: check OPENAI_API_KEY"
        if isinstance(e, openai.RateLimitError):
            return f"rate limited or out of credits: {str(e)[:200]}"
        if isinstance(e, openai.APIStatusError):
            return f"API error {e.status_code}: {str(e)[:200]}"
        if isinstance(e, openai.APIConnectionError):
            return f"connection error: {e}"
        return f"{type(e).__name__}: {str(e)[:300]}"


def make_copilot(
    metrics: MetricsStore | None = None, tracer_provider=None, profile: str | None = None, model: str | None = None
) -> Copilot:
    """Factory: pick the provider from LLM_PROVIDER, the profile from AGENT_PROFILE (or the argument)."""
    if config.LLM_PROVIDER == "openai":
        return OpenAICopilot(metrics=metrics, profile=profile, model=model)
    import anthropic

    client = anthropic.Anthropic(open_telemetry={"tracer_provider": tracer_provider}) if tracer_provider else anthropic.Anthropic()
    return Copilot(client=client, metrics=metrics, profile=profile, model=model)
