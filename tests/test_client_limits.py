"""Model clients get explicit timeouts and retry limits (review: SDK defaults are 600 s and 2 silent retries)."""

from ecu_copilot import config
from ecu_copilot.copilot.agent import OpenAICopilot, make_copilot


def test_openai_client_gets_timeout_and_retry_limit(monkeypatch):
    import openai

    seen = {}

    class _Fake:
        def __init__(self, **kw):
            seen.update(kw)

    monkeypatch.setattr(openai, "OpenAI", _Fake)
    c = OpenAICopilot.__new__(OpenAICopilot)
    c.client = None
    c._client()
    assert seen == {"timeout": config.MODEL_TIMEOUT_S, "max_retries": config.MODEL_MAX_RETRIES}
    assert config.MODEL_TIMEOUT_S <= 300 and config.MODEL_MAX_RETRIES <= 1


def test_anthropic_client_gets_timeout_and_retry_limit(monkeypatch):
    import anthropic

    seen = {}

    class _Fake:
        def __init__(self, **kw):
            seen.update(kw)

    monkeypatch.setattr(anthropic, "Anthropic", _Fake)
    monkeypatch.setattr(config, "LLM_PROVIDER", "anthropic")
    make_copilot(metrics=None, tracer_provider=None)
    assert seen["timeout"] == config.MODEL_TIMEOUT_S and seen["max_retries"] == config.MODEL_MAX_RETRIES
