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
