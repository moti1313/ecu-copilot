"""CONCEPT §13 Stufe b: revision trial plumbing - feedback from marks, frozen numbered evidence, classification.
No network."""

import json
from pathlib import Path

import pytest

from ecu_copilot.copilot.agent import ToolCall
from evals.revision_trial import CASES, NEUTRAL_FEEDBACK, TRIGGER, build_messages, classify, feedback_for

ARCHIVE = Path(__file__).resolve().parents[1] / "data/evals/bench-20261017-090812/runs.json"


def _a(validity, defect, cause, lot=None):
    return {
        "scope": {"station": 2, "variant": "B", "lot": lot},
        "test_validity": validity,
        "defect_indication": defect,
        "root_cause": cause,
    }


def _describe(relation):
    out = {"scope": {"station": 2, "variant": "B"}, "tested": 480, "iq_t1_relation": relation, "iq_t1_correlation": 0.02}
    return ToolCall(name="describe_signal", input={"station": 2, "variant": "B", "minutes": 20}, output=json.dumps(out))


def test_feedback_triggers_only_on_k1():
    s05 = {"assessments": [_a("invalid_temperature", "none_assessable", "station_temperature"), _a("unknown", "suspected", "sensor_t1")]}
    text, flags, triggered = feedback_for(s05, [_describe("decoupled")])
    assert triggered and TRIGGER in text and "independent measurement" in text
    assert {f["code"] for f in flags} >= {"K1", "K2", "K3"}
    # a legitimate S08-like report (K4 only) does not trigger a revision in Stufe b
    s08 = {
        "assessments": [
            _a("invalid_temperature", "none_assessable", "station_temperature"),
            _a("valid", "strong", "connector_lot", lot="L2439-07"),
        ]
    }
    text, flags, triggered = feedback_for(s08, [_describe("iq_follows_t1")])
    assert not triggered and text == NEUTRAL_FEEDBACK and [f["code"] for f in flags] == ["K4"]


def test_messages_keep_tool_numbering_and_contain_original_report():
    calls = [ToolCall(name="get_station_stats", input={"minutes": 10}, output='{"a":1}'), _describe("decoupled")]
    report = {"assessments": [], "evidence": [{"ref": {"tool_call": 2}}]}
    msgs = build_messages("Frage?", calls, report, "FEEDBACK")
    assert msgs[0]["role"] == "system" and "REVISION STEP" in msgs[0]["content"] and "no tools in this step" in msgs[0]["content"]
    user = msgs[1]["content"]
    assert "[tool_call 1] get_station_stats" in user and "[tool_call 2] describe_signal" in user
    assert user.index("[tool_call 1]") < user.index("[tool_call 2]")
    assert '"tool_call": 2' in user and "FEEDBACK" in user and "Frage?" in user


def test_classification_matrix():
    ok, bad = {"assessments_exact": True}, {"assessments_exact": False}
    assert classify(bad, ok) == "fixed"
    assert classify(ok, bad) == "degraded"
    assert classify(ok, ok) == "unchanged_correct"
    assert classify(bad, bad) == "unchanged_wrong"


def test_preregistered_case_list():
    assert len(CASES) == 11
    assert [c for c in CASES if c[2] == "k1"] == [("S05-sensor-offset", i, "k1") for i in range(3)]
    assert sum(1 for c in CASES if c[2] == "control") == 8


@pytest.mark.skipif(not ARCHIVE.exists(), reason="run-4 archive not present")
def test_archive_cases_trigger_as_preregistered():
    from evals.revision_trial import calls_of, load_runs

    runs = load_runs(ARCHIVE)
    for scenario, rep, kind in CASES:
        run = runs[(scenario, "v2", rep)]
        _, _, triggered = feedback_for(run["report"], calls_of(run))
        assert triggered == (kind == "k1"), (scenario, rep, kind)


# --- Review-Korrekturen (Reviewer, 20.10.) --------------------------------------------------------------------
class _Resp:
    def __init__(self, content, finish_reason="stop", prompt_tokens=100, completion_tokens=50):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})(), "finish_reason": finish_reason})()]
        self.usage = type("U", (), {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens})()


class _FakeClient:
    def __init__(self, resp=None, exc=None):
        self._resp, self._exc, self.calls = resp, exc, []
        self.chat = type("Chat", (), {"completions": self})()

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._exc:
            raise self._exc
        return self._resp


def test_truncated_revision_is_never_scored_even_if_parsable():
    from evals.revision_trial import revise

    parsable = json.dumps({"assessments": [], "finding": "unclear"})
    out = revise(_FakeClient(_Resp(parsable, finish_reason="length")), [{"role": "user", "content": "x"}], "gpt-5")
    assert out["report"] is None and "truncated" in out["error"]


def test_api_error_is_logged_per_case_not_raised():
    from evals.revision_trial import revise

    out = revise(_FakeClient(exc=RuntimeError("boom")), [{"role": "user", "content": "x"}], "gpt-5")
    assert out["report"] is None and out["error"].startswith("api_error: RuntimeError")


def test_call_params_are_complete_and_client_budget_is_explicit():
    from evals.revision_trial import RETRIES, TIMEOUT_S, call_params

    p = call_params("gpt-5")
    assert p["max_completion_tokens"] == 24000 and p["reasoning_effort"] == "medium"
    assert p["response_format"]["json_schema"]["strict"] is True and "properties" in p["response_format"]["json_schema"]["schema"]
    assert RETRIES == 0 and TIMEOUT_S == 240.0


@pytest.mark.skipif(not ARCHIVE.exists(), reason="run-4 archive not present")
def test_precheck_passes_on_archive_and_fails_when_a_k1_case_loses_its_mark():
    import copy

    from ecu_copilot.engineering.spec import load_spec
    from evals.revision_trial import load_runs, load_scenarios, precheck

    runs, scen, spec = load_runs(ARCHIVE), load_scenarios(), load_spec()
    assert precheck(runs, scen, [], spec) == []
    broken = copy.deepcopy(runs)
    r = broken[("S05-sensor-offset", 0, "v2")] if ("S05-sensor-offset", 0, "v2") in broken else broken[("S05-sensor-offset", "v2", 0)]
    r["tool_calls"] = [c for c in r["tool_calls"] if c["name"] != "describe_signal"]
    r["report"]["assessments"] = [a for a in r["report"]["assessments"] if a["root_cause"] != "sensor_t1"]
    problems = precheck(broken, scen, [], spec)
    assert any("K1-Fall ohne K1-Marke" in p for p in problems)


@pytest.mark.skipif(not ARCHIVE.exists(), reason="run-4 archive not present")
def test_run_case_record_carries_code_version_params_and_result(tmp_path):
    from ecu_copilot.engineering.spec import load_spec
    from evals.revision_trial import load_runs, load_scenarios, run_case

    runs, scen, spec = load_runs(ARCHIVE), load_scenarios(), load_spec()
    run = runs[("S05-sensor-offset", "v2", 0)]
    fixed = dict(run["report"])
    fixed["assessments"] = [
        {
            "scope": {"station": 2, "variant": "B", "lot": None},
            "test_validity": "unknown",
            "defect_indication": "none",
            "root_cause": "sensor_t1",
        }
    ]
    client = _FakeClient(_Resp(json.dumps(fixed)))
    rec = run_case(client, ("S05-sensor-offset", 0, "k1"), runs, scen, [], spec, "gpt-5")
    assert rec["result"] == "fixed" and rec["after"]["assessments_exact"] and rec["after"]["flags"] == []
    assert set(rec["code"]) == {"commit", "dirty"} and rec["params"]["max_completion_tokens"] == 24000
    assert rec["client"] == {"max_retries": 0, "timeout_s": 240.0} and rec["cost_usd"] > 0
    assert client.calls[0]["max_completion_tokens"] == 24000 and "[tool_call 1]" in client.calls[0]["messages"][1]["content"]
