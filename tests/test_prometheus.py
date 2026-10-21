"""Prometheus exposition of the per-question metrics: counters from the appended records, a latency histogram,
health gauges. No client library, no network."""

from ecu_copilot.copilot.metrics import LATENCY_BUCKETS_S, MetricsStore, QuestionRecord, prometheus_text


def _rec(latency, cost=0.03, error=None, tools=("search_docs",), inp=1000, out=200, cached=500, cite_missing=False, created=0):
    return QuestionRecord(
        timestamp="2026-10-21T10:00:00+00:00",
        question="q",
        model="openai:gpt-5:v2",
        prompt_version="2026-10-16.3",
        latency_s=latency,
        iterations=2,
        tools=list(tools),
        usage={"input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": cached, "cache_creation_input_tokens": created},
        cost_usd=cost,
        citation_missing=cite_missing,
        error=error,
    )


def _value(text, name):
    return next(float(line.split()[-1]) for line in text.splitlines() if line.startswith(name + " ") or line.startswith(name + "{"))


def test_counters_histogram_and_gauges():
    recs = [_rec(4.0), _rec(25.0, error="boom", tools=("search_docs", "check_validity")), _rec(400.0, cite_missing=True)]
    text = prometheus_text(recs, {"twin_reachable": True, "index_ready": False, "provider": "openai", "model": "gpt-5"})
    assert _value(text, "ecu_copilot_questions_total") == 3
    assert _value(text, "ecu_copilot_errors_total") == 1
    assert _value(text, "ecu_copilot_citation_missing_total") == 1
    assert 'ecu_copilot_tokens_total{kind="input"} 3000' in text and 'ecu_copilot_tokens_total{kind="cache_read"} 1500' in text
    assert 'ecu_copilot_tool_calls_total{tool="search_docs"} 3' in text and 'ecu_copilot_tool_calls_total{tool="check_validity"} 1' in text
    # histogram: cumulative buckets, +Inf equals count, sum is the plain total
    assert 'ecu_copilot_latency_seconds_bucket{le="5"} 1' in text
    assert 'ecu_copilot_latency_seconds_bucket{le="30"} 2' in text
    assert 'ecu_copilot_latency_seconds_bucket{le="300"} 2' in text
    assert 'ecu_copilot_latency_seconds_bucket{le="+Inf"} 3' in text
    assert "ecu_copilot_latency_seconds_count 3" in text and "ecu_copilot_latency_seconds_sum 429" in text
    assert "ecu_copilot_twin_reachable 1" in text and "ecu_copilot_index_ready 0" in text
    assert 'ecu_copilot_build_info{provider="openai",model="gpt-5",prompt_version="' in text
    assert abs(_value(text, "ecu_copilot_cost_usd_total") - 0.09) < 1e-9
    assert text.endswith("\n") and "# TYPE ecu_copilot_latency_seconds histogram" in text
    assert len(LATENCY_BUCKETS_S) == 11 and LATENCY_BUCKETS_S[-1] == 1200
    assert 'ecu_copilot_latency_seconds_bucket{le="600"} 3' in text
    assert 'ecu_copilot_tokens_total{kind="cache_creation"} 0' in text


def test_empty_store_exposes_zeros_and_store_round_trip(tmp_path):
    store = MetricsStore(tmp_path / "m.jsonl")
    text = prometheus_text(store.records(), {})
    assert "ecu_copilot_questions_total 0" in text and 'ecu_copilot_latency_seconds_bucket{le="+Inf"} 0' in text
    assert "ecu_copilot_twin_reachable 0" in text
    store.record(_rec(12.5))
    again = MetricsStore(tmp_path / "m.jsonl")  # re-read from disk
    assert "ecu_copilot_questions_total 1" in prometheus_text(again.records(), {})


def test_cache_creation_tokens_are_exported():
    text = prometheus_text([_rec(1.0, created=700)], {})
    assert 'ecu_copilot_tokens_total{kind="cache_creation"} 700' in text


def test_label_values_are_escaped():
    text = prometheus_text([_rec(1.0, tools=('we"ird\\tool',))], {})
    assert 'tool="we\\"ird\\\\tool"' in text
