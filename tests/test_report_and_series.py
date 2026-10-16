"""Structured report parsing, tool summaries, the twin's series endpoint and the decision log."""

import json
from datetime import timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient

from ecu_copilot.copilot.agent import parse_report, summarize_tool_output
from ecu_copilot.twin.models import TemperatureDrift


def test_parse_report_accepts_plain_and_fenced_json():
    report = {
        "answer_markdown": "Befund …",
        "finding": "pseudo_failure",
        "hypotheses": [],
        "evidence": [],
        "next_test": None,
        "affected_components": ["U1"],
    }
    assert parse_report(json.dumps(report))["finding"] == "pseudo_failure"
    assert parse_report("```json\n" + json.dumps(report) + "\n```")["affected_components"] == ["U1"]
    assert parse_report("Hier: " + json.dumps(report) + " Ende")["answer_markdown"] == "Befund …"


def test_parse_report_rejects_plain_text_and_fills_defaults():
    assert parse_report("Limit ist 450 µA (TS-DCU-EOL §5).") is None
    assert parse_report("") is None
    minimal = parse_report(json.dumps({"answer_markdown": "x"}))
    assert minimal["hypotheses"] == [] and minimal["next_test"] is None and minimal["finding"] == "information"


def test_tool_summaries():
    hits = json.dumps([{"citation": "TS-DCU-EOL §4.2"}, {"citation": "FMEA-DCU-B2 §4"}])
    assert summarize_tool_output("search_docs", hits) == "2 Treffer: TS-DCU-EOL §4.2, FMEA-DCU-B2 §4"
    stats = json.dumps({"window_minutes": 10, "groups": [{"station": 2, "variant": "B", "failure_rate_pct": 13.4}]})
    assert summarize_tool_output("get_station_stats", stats) == "10 min · EOL-2/B 13.4 %"
    res = json.dumps({"count": 7, "by_failure_code": {"E-204": 7}, "by_lot": {"L2441-04": 4, "L2441-03": 3}})
    assert "7 Ergebnisse · E-204 ×7" in summarize_tool_output("get_recent_results", res)
    assert summarize_tool_output("search_docs", json.dumps({"error": "index missing"})) == "Fehler: index missing"
    assert summarize_tool_output("search_docs", "not json").startswith("not json")


def test_series_buckets_and_fail_markers(sim, now):
    sim.add_fault(TemperatureDrift(station=2, ramp_s=0), now=now)
    for i in range(1, 201):
        sim.tick(2, now=now + timedelta(seconds=1.5 * i))
    s = sim.series(station=2, variant=None, minutes=10, bucket_s=60, now=now + timedelta(seconds=300))
    assert s["limits"]["quiescent_max_ua"] == {"A": 350.0, "B": 450.0}
    assert s["limits"]["temp_valid_c"] == [18.0, 32.0]
    assert 5 <= len(s["buckets"]) <= 11 and all(b["n"] > 0 for b in s["buckets"])
    assert s["fails"] and all(f["code"] for f in s["fails"])
    assert s["fails"] == sorted(s["fails"], key=lambda f: f["t"])


def test_series_endpoint(twin_client):
    body = twin_client.get("/series", params={"station": 3, "variant": "B", "minutes": 20, "bucket_s": 60}).json()
    assert body["station"] == 3 and body["variant"] == "B" and body["buckets"]
    assert twin_client.get("/series", params={"station": 9}).status_code == 422


def test_copilot_bom_and_decisions(tmp_path, monkeypatch):
    from ecu_copilot.copilot import api

    monkeypatch.setattr(api, "DECISIONS_FILE", tmp_path / "decisions.jsonl")
    monkeypatch.setattr(api, "INVESTIGATIONS_FILE", tmp_path / "investigations.jsonl")
    api.state.update({"metrics": None, "index": None, "copilot": None, "investigations": {}})
    client = TestClient(api.app)  # no lifespan: endpoints that don't need the agent
    assert any(p["part_number"] == "HB4821-QHTS28" for p in client.get("/bom").json()["parts"])
    fake = SimpleNamespace(trace_id="abc", provider="openai", model="m", prompt_version="p", error=None, report=None)
    inv_id = api._store_investigation("q", fake)
    r = client.post("/decisions", json={"investigation_id": inv_id, "decision": "approve_test", "engineer": "M. Molaei"})
    assert r.status_code == 201 and r.json()["decision"] == "approve_test" and r.json()["trace_id"] == "abc"
    assert client.get("/decisions").json()[0]["investigation_id"] == inv_id
    assert client.post("/decisions", json={"investigation_id": inv_id, "decision": "launch_rocket"}).status_code == 422
