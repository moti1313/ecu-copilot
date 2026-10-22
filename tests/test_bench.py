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


def test_must_cite_tolerates_section_sign(bm25_index):
    """The V2 prompt asks for plain section numbers ("4.2"); the truth may say "§4.2" - both must match."""
    from ecu_copilot.copilot.agent import AskResult, parse_report

    s08 = json.loads((SCENARIO_DIR / "S08-drift-and-bad-lot.json").read_text())
    ev = {
        "statement": "x",
        "source_type": "document",
        "ref": {
            "tool_call": None,
            "field": None,
            "station": None,
            "variant": None,
            "window_minutes": None,
            "value": None,
            "doc_id": "TS-DCU-EOL",
            "revision": "D",
            "section": "4.2",
        },
        "citation": "TS-DCU-EOL 4.2",
        "supports": "",
    }
    r = AskResult(answer="x")
    r.report = parse_report(
        json.dumps(
            {
                "answer_markdown": "x",
                "assessments": [],
                "hypotheses": [],
                "evidence": [ev],
                "next_test": None,
                "affected_components": [],
                "routing": [],
            }
        )
    )
    assert score(s08, r, bm25_index._chunks, load_spec())["must_cite_ok"]


def test_sensor_offset_decouples_reported_temperature_from_current(sim, now):
    """S05: the station REPORTS +9 K, physics is unchanged - Iq stays normal, so E-204 does not rise."""
    from ecu_copilot.engineering.describe import describe_signal
    from ecu_copilot.twin.models import SensorOffset

    end = _drive(sim, now, [], n=200)
    end2 = _drive(sim, end, [SensorOffset(station=2, offset_c=9.0)], n=300)
    rows = [r.model_dump(mode="json") for r in sim.results(station=2, variant="B", minutes=15, limit=10000, now=end2)]
    d = describe_signal(rows)
    assert d["stats"]["board_temp_c"]["trend"] == "up" and d["stats"]["board_temp_c"]["second_half"] > 32
    assert d["iq_t1_relation"] == "decoupled"
    e204 = sum(1 for r in rows if r["failure_code"] == "E-204")
    assert e204 <= 3  # no real current rise


def test_b0_abstains_on_s04_and_names_sensor_on_s05(sim, now, bm25_index):
    from ecu_copilot.twin.models import SensorOffset
    from evals.bench import solvable

    s04 = json.loads((SCENARIO_DIR / "S04-no-fault.json").read_text())
    s05 = json.loads((SCENARIO_DIR / "S05-sensor-offset.json").read_text())
    spec = load_spec()
    twin = SimTwin(sim, now)
    tools.configure(index=bm25_index, twin=twin)
    ok, msg, _ = solvable(s04, twin)
    assert ok, msg
    r = run_b0(s04["question"], station=2, variant="B")
    s = score(s04, r, bm25_index._chunks, spec)
    assert s["finding_ok"] and s["assessments_exact"] and s["abstain_ok"], s

    end = _drive(sim, now, [SensorOffset(station=2, offset_c=9.0)], n=400)
    twin = SimTwin(sim, end)
    tools.configure(index=bm25_index, twin=twin)
    ok, msg, _ = solvable(s05, twin)
    assert ok, msg
    r = run_b0(s05["question"], station=2, variant="B")
    s = score(s05, r, bm25_index._chunks, spec)
    assert s["assessments_exact"] and s["abstain_ok"], (s, r.report["assessments"])


def test_b0_validity_without_cause_claim_on_a_single_invalid_measurement(sim, now, bm25_index):
    """One INVALID E-204 at normal temperature statistics: validity is a finding, the cause is not."""
    from ecu_copilot.copilot.agent import parse_report  # noqa: F401

    tools.configure(index=bm25_index, twin=SimTwin(sim, now))
    rows = sim.results(station=2, variant="B", minutes=10, limit=10000, now=now)
    # fabricate: mark one failed unit as E-204 measured hot (reported), everything else untouched
    victim = next(r for r in rows if r.verdict == "fail")
    victim.failure_code = "E-204"
    victim.measurements.board_temp_c = 33.5
    r = run_b0("?", station=2, variant="B")
    a = next(a for a in r.report["assessments"] if a["scope"]["station"] == 2)
    assert a["test_validity"] == "invalid_temperature" and a["root_cause"] == "unknown"


def test_b0_gets_its_scope_from_the_scenario_not_from_faults(sim, now, bm25_index):
    """S04 injects nothing; B0 must still investigate station 2 / B via make_systems() (reviewer point 1 before run 4)."""
    from evals.bench import make_systems

    s04 = json.loads((SCENARIO_DIR / "S04-no-fault.json").read_text())
    assert s04.get("scope") == {"station": 2, "variant": "B"} and s04["setup"] == []
    tools.configure(index=bm25_index, twin=SimTwin(sim, now))
    r = make_systems(["b0"], None)["b0"](s04["question"], s04)
    a = r.report["assessments"]
    assert a and a[0]["scope"]["station"] == 2 and a[0]["scope"]["variant"] == "B" and a[0]["root_cause"] == "none"


def test_summary_separates_regular_and_exploratory_runs():
    from datetime import UTC, datetime

    from evals.bench import split_runs, summarize

    base = {
        "completed": True,
        "finding": "pseudo_failure",
        "finding_ok": True,
        "assessments_ok": True,
        "assessments_exact": True,
        "root_cause_ok": True,
        "abstain_ok": True,
        "required_tools_ok": True,
        "must_cite_ok": True,
        "next_test_ok": True,
        "latency_s": 1.0,
        "cost_usd": 0.0,
        "error": None,
        "prov_live": {"ok": 1, "total": 1},
        "prov_docs": {"ok": 1, "total": 1},
        "supp_docs": {"ok": 0, "total": 1},
        "extra_assessments": 0,
        "system": "b0",
        "repeat": 0,
    }
    runs = [
        {**base, "scenario": "S01", "solvable": True, "exploratory": False},
        {**base, "scenario": "S08w", "solvable": True, "exploratory": True, "finding_ok": False, "assessments_exact": False},
        {**base, "scenario": "S05", "solvable": False, "exploratory": True, "finding_ok": False, "assessments_exact": False},
    ]
    regular, exploratory = split_runs(runs)
    assert [r["scenario"] for r in regular] == ["S01"] and len(exploratory) == 2
    text = summarize(runs, "m", datetime.now(UTC))
    assert "1 regulär, 2 explorativ" in text and "Explorative Läufe" in text
    head = text.split("Explorative Läufe")[0]
    assert "| B0 | 100 % | 100 % |" in head  # the regular table is unaffected by the two failed exploratory runs
    assert "| S08w (E)" in text and "| S05 (E)" in text  # per-scenario table is a real table, one row per scenario
    assert "\n|\n" not in text  # regression: _per_scenario once returned a string and the table came out one char per line


def _report_with(assessments, finding="pseudo_failure"):
    from ecu_copilot.copilot.agent import AskResult, parse_report

    r = AskResult(answer="x")
    r.report = parse_report(
        json.dumps(
            {
                "answer_markdown": "x",
                "finding": finding,
                "hypotheses": [],
                "evidence": [],
                "next_test": None,
                "affected_components": ["T1"],
                "assessments": assessments,
            }
        )
    )
    return r


def test_scorer_matches_two_causes_in_the_same_scope(bm25_index):
    """Review R1: with two expected causes in one scope the old scorer compared both to the first answer row (max 1/2)."""
    s06 = json.loads((SCENARIO_DIR / "S06-sensor-and-heat.json").read_text())
    truth = s06["truth"]["assessments"]
    a_temp = {
        "scope": {"station": 2, "variant": "B", "lot": None},
        **{k: truth[0][k] for k in ("test_validity", "defect_indication", "root_cause")},
    }
    a_sens = {
        "scope": {"station": 2, "variant": "B", "lot": None},
        **{k: truth[1][k] for k in ("test_validity", "defect_indication", "root_cause")},
    }
    spec = load_spec()
    for order in ([a_temp, a_sens], [a_sens, a_temp]):
        s = score(s06, _report_with(order), bm25_index._chunks, spec)
        assert s["assessments_matched"] == "2/2" and s["assessments_exact"], order
    # missing second cause -> 1/2 in BOTH directions; a duplicate of the first row does not substitute for the missing one
    assert score(s06, _report_with([a_temp]), bm25_index._chunks, spec)["assessments_matched"] == "1/2"
    assert score(s06, _report_with([a_sens]), bm25_index._chunks, spec)["assessments_matched"] == "1/2"  # review round 2
    assert score(s06, _report_with([a_temp, dict(a_temp)]), bm25_index._chunks, spec)["assessments_matched"] == "1/2"
    # a wrong extra cause blocks exactness even when both expected rows are present
    extra = {
        "scope": {"station": 2, "variant": "B", "lot": None},
        "test_validity": "valid",
        "defect_indication": "suspected",
        "root_cause": "component_u1",
    }
    s = score(s06, _report_with([a_temp, a_sens, extra]), bm25_index._chunks, spec)
    assert s["assessments_matched"] == "2/2" and not s["assessments_exact"] and s["extra_assessments"] == 1
