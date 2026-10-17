"""Jev shadow adapter (CONCEPT §12): request shape, response parsing, scoring and protocol - with a mock transport.
No network, no key."""

import json
from pathlib import Path

import httpx
import pytest

from ecu_copilot.copilot.agent import ToolCall
from ecu_copilot.copilot.jev import (
    EXPECTED,
    MODEL,
    QUESTIONS,
    JevClient,
    build_state,
    choice_confidence,
    log_line,
    noul_verdict,
    score_against_expected,
)

ARCHIVE = Path(__file__).resolve().parents[1] / "data/evals/bench-20261017-090812/runs.json"


def _fake_api(captured: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        probs = {k: 0.0 for k in QUESTIONS["next_check"]["criteria"]}
        probs["reference_thermometer"], probs["retest_valid_temperature"] = 0.8, 0.2
        return httpx.Response(
            200,
            json={
                "model": "jev-1.13.0",
                "usage": {"input_tokens": 6500, "output_tokens": 0},
                "answers": {
                    "next_check": {
                        "type": "choice",
                        "choice": "reference_thermometer",
                        "probabilities": probs,
                        "confidence": choice_confidence(probs),
                    },
                    "t1_unreliable": {"type": "noul", "noul": 0.93},
                    "product_defect": {"type": "noul", "noul": 0.12},
                },
            },
            headers={"x-typesafe-request-id": "req-test-1"},
        )

    return httpx.MockTransport(handler)


def test_request_shape_pins_model_and_sends_questions():
    captured = {}
    client = JevClient(api_key="test-key", transport=_fake_api(captured))
    resp = client.system_one({"engineer_question": "q"}, QUESTIONS)
    assert captured["url"] == "https://api.typesafe.ai/v1/systemone"
    assert captured["auth"] == "Bearer test-key"
    assert captured["body"]["model"] == MODEL == "jev-1.13.0"
    assert set(captured["body"]["questions"]) == {"next_check", "t1_unreliable", "product_defect"}
    assert captured["body"]["questions"]["next_check"]["type"] == "choice"
    assert len(captured["body"]["questions"]["next_check"]["criteria"]) == 5
    assert resp.model == "jev-1.13.0" and resp.request_id == "req-test-1" and resp.usage["input_tokens"] == 6500


def test_missing_key_refuses_without_network():
    client = JevClient(api_key="", transport=_fake_api({}))
    with pytest.raises(RuntimeError, match="TYPESAFE_API_KEY"):
        client.system_one({"x": 1})


def test_confidence_formula_and_noul_thresholds():
    assert choice_confidence({"a": 1.0, "b": 0.0, "c": 0.0}) == pytest.approx(1.0)
    assert choice_confidence({"a": 1 / 3, "b": 1 / 3, "c": 1 / 3}) == pytest.approx(0.0, abs=1e-9)
    assert choice_confidence({"a": 0.8, "b": 0.2}) == pytest.approx(0.6)
    assert noul_verdict(0.93) == "yes" and noul_verdict(0.12) == "no" and noul_verdict(0.5) == "undecided"


def test_scoring_against_preregistered_expectations():
    client = JevClient(api_key="k", transport=_fake_api({}))
    verdicts = client.system_one({"s": 1}).verdicts()
    s05 = score_against_expected("S05-sensor-offset", verdicts)
    assert s05["next_check_ok"] and s05["t1_unreliable_ok"] and s05["product_defect_ok"] and not s05["unnecessary_check"]
    s04 = score_against_expected("S04-no-fault", verdicts)
    assert not s04["next_check_ok"] and s04["unnecessary_check"]  # the fake answer would be an unnecessary check on a clean line
    assert score_against_expected("unknown", verdicts) == {"scored": False}
    assert set(EXPECTED) == {
        "S01-temperature-drift",
        "S04-no-fault",
        "S05-sensor-offset",
        "S08-drift-and-bad-lot",
        "S08w-drift-and-bad-lot-weak",
    }


def test_build_state_contains_tool_outputs_but_never_the_report():
    calls = [
        ToolCall(
            name="describe_signal", input={"station": 2, "variant": "B", "minutes": 20}, output=json.dumps({"iq_t1_relation": "decoupled"})
        ),
        ToolCall(name="search_docs", input={"query": "x"}, output=json.dumps([{"citation": "TS-DCU-EOL §4.2", "text": "T" * 2000}])),
        ToolCall(name="get_recent_results", input={}, output="[]"),
    ]
    state = build_state("Frage?", calls, {"limits": {"B": {"quiescent_max_ua": 450}}, "validity": {"board_temp_c": {"min": 18, "max": 32}}})
    assert state["engineer_question"] == "Frage?"
    assert [t["tool"] for t in state["tool_outputs"]] == ["describe_signal"]  # raw result lists are not engineering evidence
    assert len(state["document_excerpts"][0]["text"]) == 600
    assert state["specification"]["validity"]["board_temp_c"]["max"] == 32
    dumped = json.dumps(state)
    for forbidden in ("assessments", "hypotheses", "answer_markdown", "root_cause"):
        assert forbidden not in dumped


@pytest.mark.skipif(not ARCHIVE.exists(), reason="run-4 archive not present")
def test_state_from_archived_s05_run_fits_context_and_excludes_v2_conclusions():
    runs = json.loads(ARCHIVE.read_text(encoding="utf-8"))["runs"]
    r = next(x for x in runs if x["scenario"] == "S05-sensor-offset" and x["system"] == "v2")
    calls = [ToolCall(name=c["name"], input=c.get("input") or {}, output=c.get("output") or "") for c in r["tool_calls"]]
    state = build_state("T1 über 32 °C - Ruhestromprüfungen ungültig?", calls, None)
    text = json.dumps(state, ensure_ascii=False)
    assert len(text) // 4 < 32_000  # per-question context limit (docs.typesafe.ai/models)
    assert '"iq_t1_relation": "decoupled"' in text
    assert "station_temperature" not in text and "sensor_t1" not in text  # V2's assessments never enter the state


def test_log_line_writes_protocol_without_state_text(tmp_path):
    client = JevClient(api_key="k", transport=_fake_api({}))
    resp = client.system_one({"engineer_question": "GEHEIM-TEXT"})
    path = tmp_path / "jev.jsonl"
    log_line(
        path,
        {"scenario": "S05-sensor-offset", "system": "v2", "repeat": 0},
        resp,
        score_against_expected("S05-sensor-offset", resp.verdicts()),
    )
    rec = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert (
        rec["model_requested"] == "jev-1.13.0" and rec["scoring"]["next_check_ok"] and rec["verdicts"]["t1_unreliable"]["verdict"] == "yes"
    )
    assert "GEHEIM-TEXT" not in path.read_text(encoding="utf-8") and len(rec["state_sha256"]) == 64
