"""The agent with a fake Anthropic client: accounting, guardrails and metrics are testable
without an API key. The real model is covered by the evals (evals/run.py)."""

from types import SimpleNamespace

from ecu_copilot.copilot.agent import Copilot
from ecu_copilot.copilot.metrics import MetricsStore


def _msg(stop_reason, content, usage=(1000, 200, 0, 0)):
    i, o, cr, cw = usage
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=content,
        usage=SimpleNamespace(input_tokens=i, output_tokens=o, cache_read_input_tokens=cr, cache_creation_input_tokens=cw),
    )


def _text(t):
    return SimpleNamespace(type="text", text=t)


def _tool_use(id_, name, inp):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=inp)


class FakeRunner:
    def __init__(self, messages):
        self._messages = messages
        self._i = 0

    def __iter__(self):
        for m in self._messages:
            self._current = m
            yield m

    def generate_tool_call_response(self):
        uses = [b for b in self._current.content if b.type == "tool_use"]
        if not uses:
            return None
        return {"role": "user", "content": [{"type": "tool_result", "tool_use_id": u.id, "content": '{"ok": true}'} for u in uses]}


class FakeClient:
    def __init__(self, messages):
        self.beta = SimpleNamespace(messages=SimpleNamespace(tool_runner=lambda **kw: FakeRunner(messages)))
        self.kwargs = None


def test_two_iterations_with_tool_call_are_accounted(tmp_path):
    msgs = [
        _msg("tool_use", [_tool_use("t1", "search_docs", {"query": "limit"})], usage=(1200, 50, 0, 900)),
        _msg("end_turn", [_text("Limit ist 450 µA (TS-DCU-EOL §5).")], usage=(300, 120, 900, 0)),
    ]
    metrics = MetricsStore(tmp_path / "m.jsonl")
    r = Copilot(client=FakeClient(msgs), model="claude-opus-5-5", metrics=metrics).ask("Grenze Variante B?")
    assert r.iterations == 2
    assert [c.name for c in r.tool_calls] == ["search_docs"]
    assert r.tool_calls[0].result_preview == '{"ok": true}'
    assert r.usage == {"input_tokens": 1500, "output_tokens": 170, "cache_read_input_tokens": 900, "cache_creation_input_tokens": 900}
    assert r.cost_usd == round((1500 * 4 + 170 * 20 + 900 * 5 + 900 * 0.2) / 1e6, 5)
    assert r.citation_missing is False
    assert metrics.summary()["questions"] == 1 and metrics.summary()["tool_calls"] == {"search_docs": 1}


def test_citation_guardrail_flags_doc_answers_without_source():
    msgs = [
        _msg("tool_use", [_tool_use("t1", "search_docs", {"query": "x"})]),
        _msg("end_turn", [_text("Die Grenze ist 450 µA.")]),
    ]
    assert Copilot(client=FakeClient(msgs)).ask("?").citation_missing is True


def test_no_docs_tool_means_no_citation_requirement():
    msgs = [_msg("end_turn", [_text("Station 2: 12 % Ausfall.")])]
    assert Copilot(client=FakeClient(msgs)).ask("Lage?").citation_missing is False


def test_input_guardrails():
    c = Copilot(client=FakeClient([]))
    assert c.ask("   ").error == "empty question"
    assert "longer than" in c.ask("x" * 3000).error


def test_truncation_is_reported():
    msgs = [_msg("max_tokens", [_text("Lange Antwort ...")])]
    r = Copilot(client=FakeClient(msgs)).ask("?")
    assert r.error and "max_tokens" in r.error
