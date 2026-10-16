"""Benchmark pieces that need no model: B0 on simulator data, scoring, solvability shape."""

import sys
from datetime import timedelta
from pathlib import Path

from ecu_copilot.copilot import tools
from ecu_copilot.copilot.twin_client import TwinClient
from ecu_copilot.copilot.verify import verify_report
from ecu_copilot.engineering.spec import load_spec
from ecu_copilot.twin.models import BadLot, TemperatureDrift

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json  # noqa: E402

from evals.baselines import run_b0  # noqa: E402
from evals.bench import SCENARIO_DIR, score  # noqa: E402


class SimTwin(TwinClient):
    """TwinClient over an in-process Simulator (no HTTP)."""

    def __init__(self, sim, now):
        self.sim, self.now = sim, now

    def results(self, *, station=None, variant=None, minutes=None, only_failed=False, limit=50):
        rows = self.sim.results(station=station, variant=variant, minutes=minutes, only_failed=only_failed, limit=limit, now=self.now)
        return [r.model_dump(mode="json") for r in rows]

    def stats(self, minutes=10):
        return self.sim.stats(minutes=minutes, now=self.now).model_dump(mode="json")


def _drive(sim, now, faults, n=400, station=2):
    for f in faults:
        sim.add_fault(f, now=now)
    for i in range(1, n + 1):
        for st in (1, 2, 3):
            sim.tick(st, now=now + timedelta(seconds=1.5 * i))
    return now + timedelta(seconds=1.5 * n)


def test_b0_solves_s01_and_s08_with_verified_provenance(sim, now, bm25_index):
    s01 = json.loads((SCENARIO_DIR / "S01-temperature-drift.json").read_text())
    s08 = json.loads((SCENARIO_DIR / "S08-drift-and-bad-lot.json").read_text())
    spec = load_spec()

    end = _drive(sim, now, [TemperatureDrift(station=2, ramp_s=0)])
    tools.configure(index=bm25_index, twin=SimTwin(sim, end))
    r = run_b0(s01["question"], station=2, variant="B")
    s = score(s01, r, bm25_index._chunks, spec)
    assert s["finding_ok"] and s["assessments_ok"] and s["required_tools_ok"] and s["next_test_ok"], s
    ver = verify_report(r.report, r.tool_calls, bm25_index._chunks, spec).summary()
    assert ver["provenance"]["live"]["ok"] == ver["provenance"]["live"]["total"] >= 1  # refs built by construction
    assert ver["provenance"]["docs"]["ok"] == ver["provenance"]["docs"]["total"] >= 1

    end2 = _drive(sim, end, [BadLot(variant="B", lot="L2439-07", fail_rate=0.3)], n=500)
    tools.configure(index=bm25_index, twin=SimTwin(sim, end2))
    r = run_b0(s08["question"], station=2, variant="B")
    s = score(s08, r, bm25_index._chunks, spec)
    assert s["finding"] == "mixed" and s["assessments_ok"], s
    assert any(a["root_cause"] == "connector_lot" for a in r.report["assessments"])


def test_b0_abstains_on_normal_line(sim, now, bm25_index):
    tools.configure(index=bm25_index, twin=SimTwin(sim, now))
    r = run_b0("Was ist los?", station=1, variant="A")
    a = r.report["assessments"][0]
    assert a["root_cause"] == "none" and a["defect_indication"] == "none" and r.report["finding"] == "unclear"


def test_score_penalises_single_finding_on_concurrent_scenario(bm25_index):
    """A V1-style report (single finding, no assessments) cannot be right on S08."""
    s08 = json.loads((SCENARIO_DIR / "S08-drift-and-bad-lot.json").read_text())
    from ecu_copilot.copilot.agent import AskResult, parse_report

    r = AskResult(answer="x")
    r.report = parse_report(
        json.dumps(
            {
                "answer_markdown": "x",
                "finding": "pseudo_failure",
                "hypotheses": [],
                "evidence": [],
                "next_test": None,
                "affected_components": ["T1"],
            }
        )
    )
    s = score(s08, r, bm25_index._chunks, load_spec())
    assert not s["finding_ok"] and s["assessments_matched"] == "0/2"


def test_snapshot_twin_matches_simulator_and_is_frozen(sim, now):
    from datetime import timedelta as _td

    from evals.bench import SnapshotTwin, consistency

    rows = [r.model_dump(mode="json") for r in sim.results(minutes=20, limit=10000, now=now)]
    snap = SnapshotTwin(rows, now)
    assert snap.n == len(rows) and snap.health()["status"] == "snapshot"
    live = sim.stats(minutes=10, now=now).model_dump(mode="json")
    assert snap.stats(minutes=10)["groups"] == live["groups"]
    # the live simulator moves on; the snapshot does not
    for i in range(1, 50):
        sim.tick(2, now=now + _td(seconds=1.5 * i))
    assert snap.stats(minutes=10)["groups"] == live["groups"]
    assert len(snap.results(station=2, variant="B", minutes=10, limit=10000)) == len(
        [r for r in rows if r["station"] == 2 and r["variant"] == "B" and r["timestamp"] >= (now - _td(minutes=10)).isoformat()]
    )
    # consistency ignores failed runs instead of counting them as agreement
    assert consistency([None, None, None]) is None
    assert consistency(["pseudo_failure", "pseudo_failure", None]) == 1.0
    assert consistency(["pseudo_failure", "unclear", "pseudo_failure"]) == 2 / 3


def test_v1s_profile_has_v1_tools_and_v2_schema():
    from ecu_copilot.copilot.agent import PROFILES, REPORT_SCHEMA_V2, SYSTEM_PROMPT_V1S
    from ecu_copilot.copilot.tools import TOOLS_V1, tools_for

    assert tools_for("v1s") is TOOLS_V1
    assert PROFILES["v1s"][1] is REPORT_SCHEMA_V2
    assert "check_validity" not in SYSTEM_PROMPT_V1S and "assessments" in SYSTEM_PROMPT_V1S and "tool call number" in SYSTEM_PROMPT_V1S
    assert "{a, b, c}" in SYSTEM_PROMPT_V1S  # braces survived the f-string


def test_extra_assessments_are_counted(bm25_index):
    """Expected groups found AND an extra false claim -> not exact (reviewer point 1 after run 2)."""
    from ecu_copilot.copilot.agent import AskResult, parse_report

    s01 = json.loads((SCENARIO_DIR / "S01-temperature-drift.json").read_text())
    base = {"answer_markdown": "x", "hypotheses": [], "evidence": [], "next_test": None, "affected_components": [], "routing": []}
    good = {
        "scope": {"station": 2, "variant": "B", "lot": None},
        "test_validity": "invalid_temperature",
        "defect_indication": "none_assessable",
        "root_cause": "station_temperature",
    }
    benign = {
        "scope": {"station": 2, "variant": "A", "lot": None},
        "test_validity": "valid",
        "defect_indication": "none",
        "root_cause": "none",
    }
    false_claim = {
        "scope": {"station": None, "variant": "B", "lot": "L2441-03"},
        "test_validity": "valid",
        "defect_indication": "strong",
        "root_cause": "connector_lot",
    }
    r = AskResult(answer="x")
    r.report = parse_report(json.dumps({**base, "assessments": [good, benign]}))
    s = score(s01, r, bm25_index._chunks, load_spec())
    assert s["assessments_ok"] and s["extra_assessments"] == 0 and s["assessments_exact"]
    r.report = parse_report(json.dumps({**base, "assessments": [good, false_claim]}))
    s = score(s01, r, bm25_index._chunks, load_spec())
    assert s["assessments_ok"] and s["extra_assessments"] == 1 and not s["assessments_exact"] and "connector_lot" in s["extra_claims"][0]
