"""OpenAICopilot with a fake OpenAI client: the hand-written loop, accounting and errors."""

import json
from types import SimpleNamespace

from ecu_copilot.copilot import tools
from ecu_copilot.copilot.agent import OpenAICopilot
from tests.conftest import DOCS_DIR


def _resp(finish_reason, content=None, tool_calls=None, prompt=1000, completion=100, cached=0):
    tcs = [
        SimpleNamespace(id=i, type="function", function=SimpleNamespace(name=n, arguments=json.dumps(a)), model_dump=lambda: {"id": "x"})
        for i, n, a in (tool_calls or [])
    ]
    return SimpleNamespace(
        choices=[SimpleNamespace(finish_reason=finish_reason, message=SimpleNamespace(content=content, tool_calls=tcs))],
        usage=SimpleNamespace(
            prompt_tokens=prompt, completion_tokens=completion, prompt_tokens_details=SimpleNamespace(cached_tokens=cached)
        ),
    )


class FakeOpenAI:
    def __init__(self, responses):
        self.calls = []
        it = iter(responses)

        def create(**kw):
            self.calls.append({**kw, "messages": list(kw["messages"])})  # snapshot: the agent mutates the list
            return next(it)

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


def test_openai_loop_runs_tools_and_accounts():
    tools.configure(bom_file=DOCS_DIR / "BOM-DCU.json")
    fake = FakeOpenAI(
        [
            _resp("tool_calls", tool_calls=[("c1", "lookup_part", {"query": "HB4821"})], prompt=1200, completion=40),
            _resp("stop", content="HB4821 ist abgekündigt (PCN-2026-017).", prompt=1500, completion=120, cached=1000),
        ]
    )
    r = OpenAICopilot(client=fake, model="gpt-5").ask("U7?")
    assert r.provider == "openai" and r.iterations == 2 and r.error is None
    assert [c.name for c in r.tool_calls] == ["lookup_part"]
    assert "end_of_life" in r.tool_calls[0].result_preview
    assert r.usage["input_tokens"] == 1700 and r.usage["cache_read_input_tokens"] == 1000 and r.usage["output_tokens"] == 160
    assert r.cost_usd == round((1700 * 1.25 + 160 * 10 + 1000 * 0.125) / 1e6, 5)
    # the tool result went back as a `tool` message, and reasoning_effort was sent for gpt-5
    second_call = fake.calls[1]
    assert second_call["messages"][-1]["role"] == "tool" and second_call["messages"][-1]["tool_call_id"] == "c1"
    assert second_call["reasoning_effort"] == "medium"
    assert {t["function"]["name"] for t in second_call["tools"]} == {t.to_dict()["name"] for t in tools.ALL_TOOLS}


def test_openai_unknown_tool_and_truncation():
    fake = FakeOpenAI(
        [
            _resp("tool_calls", tool_calls=[("c1", "nope", {})]),
            _resp("length", content="abgeschnitten"),
        ]
    )
    r = OpenAICopilot(client=fake).ask("?")
    assert "unknown tool" in r.tool_calls[0].result_preview
    assert r.error and "truncated" in r.error


def test_openai_iteration_cap():
    fake = FakeOpenAI([_resp("tool_calls", tool_calls=[("c", "get_station_stats", {"minutes": 5})])] * 3)
    tools.configure(twin=type("T", (), {"stats": lambda self, minutes=10: {"groups": []}})())
    r = OpenAICopilot(client=fake, max_iterations=2).ask("?")
    assert r.iterations == 2 and "stopped after 2" in r.error
