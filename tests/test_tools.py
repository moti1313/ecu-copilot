import json

from ecu_copilot.copilot import tools
from ecu_copilot.copilot.twin_client import TwinClient
from tests.conftest import DOCS_DIR


class FakeTwin(TwinClient):
    def __init__(self):  # no HTTP
        pass

    def stats(self, minutes=10):
        return {"window_minutes": minutes, "groups": [{"station": 2, "variant": "B", "failure_rate_pct": 12.5}]}

    def results(self, **kw):
        return [
            {"lot": "L2439-07", "failure_code": "E-120", "station": 3},
            {"lot": "L2439-07", "failure_code": "E-120", "station": 3},
            {"lot": "L2441-03", "failure_code": "E-310", "station": 3},
        ]


def test_lookup_part_by_number_position_and_keyword():
    tools.configure(bom_file=DOCS_DIR / "BOM-DCU.json")
    assert json.loads(tools.lookup_part.call({"query": "HB4821"}))[0]["status"] == "end_of_life"
    assert json.loads(tools.lookup_part.call({"query": "U7"}))[0]["pcn"] == "PCN-2026-017"
    assert len(json.loads(tools.lookup_part.call({"query": "motor driver"}))) == 2
    assert "error" in json.loads(tools.lookup_part.call({"query": "does-not-exist"}))


def test_search_docs_uses_index(bm25_index):
    tools.configure(index=bm25_index)
    hits = json.loads(tools.search_docs.call({"query": "quiescent current limit variant B", "k": 2}))
    assert len(hits) == 2
    assert "citation" in hits[0] and "score" not in hits[0]


def test_station_tools_summarise(monkeypatch):
    tools.configure(twin=FakeTwin())
    stats = json.loads(tools.get_station_stats.call({"minutes": 10}))
    assert stats["groups"][0]["failure_rate_pct"] == 12.5
    res = json.loads(tools.get_recent_results.call({"station": 3}))
    assert res["by_lot"] == {"L2439-07": 2, "L2441-03": 1}
    assert res["by_failure_code"] == {"E-120": 2, "E-310": 1}


def test_tool_errors_are_json_not_exceptions():
    class Broken(TwinClient):
        def __init__(self):
            pass

        def stats(self, minutes=10):
            raise ConnectionError("down")

    tools.configure(twin=Broken())
    assert "twin not reachable" in json.loads(tools.get_station_stats.call({}))["error"]


def test_tool_schemas_are_strict_objects():
    for t in tools.ALL_TOOLS:
        schema = t.to_dict()["input_schema"]
        assert schema["type"] == "object" and schema["additionalProperties"] is False
