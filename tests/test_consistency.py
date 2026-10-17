"""Consistency check (CONCEPT §11): marks, never corrections. Synthetic reports per rule plus counter-examples,
and a replay against the archived run 4 that pins the expectations written down in §11."""

import json
from pathlib import Path

import pytest

from ecu_copilot.copilot.agent import ToolCall, derive_finding
from ecu_copilot.copilot.consistency import check_consistency
from ecu_copilot.copilot.verify import verify_report

ARCHIVE = Path(__file__).resolve().parents[1] / "data/evals/bench-20261017-090812/runs.json"


def _a(station=2, variant="B", lot=None, validity="valid", defect="none", cause="none"):
    return {
        "scope": {"station": station, "variant": variant, "lot": lot},
        "test_validity": validity,
        "defect_indication": defect,
        "root_cause": cause,
    }


def _describe(relation="iq_follows_t1", station=2, variant="B"):
    out = {
        "scope": {"station": station, "variant": variant, "window_minutes": 20},
        "iq_t1_relation": relation,
        "iq_t1_correlation": 0.02 if relation == "decoupled" else 0.9,
    }
    return ToolCall(name="describe_signal", input={"station": station, "variant": variant, "minutes": 20}, output=json.dumps(out))


def _cluster(station=None, variant="B", lot="L2439-07", code="E-120", error=False):
    out = {"error": "boom"} if error else {"by": "lot", "code": code, "concentrated": True, "top": {"group": lot}}
    return ToolCall(
        name="cluster_failures",
        input={"station": station, "variant": variant, "by": "lot", "code": code, "minutes": 30},
        output=json.dumps(out),
    )


def codes(flags):
    return sorted(f.code for f in flags)


# --- S05 pattern: the documented failure --------------------------------------------------------
def test_s05_pattern_gives_k1_and_k3_and_leaves_finding_unchanged():
    report = {
        "assessments": [
            _a(validity="invalid_temperature", defect="none_assessable", cause="station_temperature"),
            _a(validity="unknown", defect="suspected", cause="sensor_t1"),
        ]
    }
    flags = check_consistency(report, [_describe("decoupled")])
    # K2 as well: the second assessment claims a station cause (sensor_t1) as a defect indication (suspected)
    assert codes(flags) == ["K1", "K2", "K3"]
    k1 = next(f for f in flags if f.code == "K1")
    assert k1.kind == "conflict" and k1.assessments == [0, 1] and "decoupled" in k1.detail
    assert derive_finding(report) == "mixed"  # unchanged: the check marks, it does not correct


def test_expected_s05_answer_has_no_flags():
    report = {"assessments": [_a(validity="unknown", defect="none", cause="sensor_t1")]}
    assert check_consistency(report, [_describe("decoupled")]) == []


# --- K0: coverage, not contradiction ---------------------------------------------------------------
def test_k0_when_describe_signal_was_not_run_and_not_when_it_errored_for_other_scope():
    report = {"assessments": [_a(validity="invalid_temperature", defect="none_assessable", cause="station_temperature")]}
    assert codes(check_consistency(report, [])) == ["K0"]
    # a describe_signal for another station does not cover station 2
    assert codes(check_consistency(report, [_describe("decoupled", station=1)])) == ["K0"]
    # a run for the station with coupled Iq/T1 covers it and raises nothing
    assert check_consistency(report, [_describe("iq_follows_t1")]) == []


def test_k1_from_decoupled_signal_alone_without_sensor_assessment():
    report = {"assessments": [_a(validity="invalid_temperature", defect="none_assessable", cause="station_temperature")]}
    flags = check_consistency(report, [_describe("decoupled")])
    assert codes(flags) == ["K1"] and flags[0].assessments == [0]


# --- K2 / K3: hints with careful wording ------------------------------------------------------------
def test_k2_station_cause_with_defect_claim():
    report = {"assessments": [_a(validity="valid", defect="suspected", cause="sensor_t1")]}
    flags = check_consistency(report, [_describe("decoupled")])
    assert codes(flags) == ["K2"] and flags[0].kind == "hint" and "getrennte Begründung" in flags[0].text


def test_k3_only_on_identical_scope_not_on_nested_lot_scope():
    # S08 pattern: invalid temperature for station 2/B (all lots) plus a lot-scoped defect - legitimate, no K3
    s08 = {
        "assessments": [
            _a(validity="invalid_temperature", defect="none_assessable", cause="station_temperature"),
            _a(lot="L2439-07", validity="valid", defect="strong", cause="connector_lot"),
        ]
    }
    assert "K3" not in codes(check_consistency(s08, [_describe(), _cluster()]))
    # identical scope with a competing defect claim -> K3 (hint, may be a justified multi-fault)
    same = {
        "assessments": [
            _a(validity="invalid_temperature", defect="none_assessable", cause="station_temperature"),
            _a(validity="valid", defect="suspected", cause="component_u7"),
        ]
    }
    flags = check_consistency(same, [_describe()])
    assert codes(flags) == ["K3"] and flags[0].assessments == [0, 1] and "Mehrfachfehler" in flags[0].text


# --- K4: coverage of the lot comparison -----------------------------------------------------------------
def test_k4_requires_successful_matching_cross_station_call():
    report = {"assessments": [_a(lot="L2439-07", validity="valid", defect="strong", cause="connector_lot")]}
    assert codes(check_consistency(report, [_cluster(station=2)])) == ["K4"]  # station-filtered only
    assert codes(check_consistency(report, [_cluster(station=None, error=True)])) == ["K4"]  # failed call does not count
    assert codes(check_consistency(report, [_cluster(station=None, lot="L2441-03")])) == ["K4"]  # other lot on top
    assert codes(check_consistency(report, [_cluster(station=None, variant="A")])) == ["K4"]  # other variant
    assert check_consistency(report, [_cluster(station=None)]) == []
    assert check_consistency(report, [_cluster(station=None, variant=None)]) == []  # all variants covers B


def test_no_assessments_or_v1_schema_gives_nothing():
    assert check_consistency({"finding": "pseudo_failure"}, []) == []
    assert check_consistency(None, []) == []


def test_verification_summary_carries_consistency(bm25_index):
    report = {"assessments": [_a(validity="invalid_temperature", defect="none_assessable", cause="station_temperature")], "evidence": []}
    s = verify_report(report, [], [], None).summary()
    assert s["consistency"]["count"] == 1 and s["consistency"]["flags"][0]["code"] == "K0"
    assert s["provenance"]["live"] == {"ok": 0, "total": 0}  # untouched


# --- Replay against run 4 (development cases, CONCEPT §11) ---------------------------------------------
@pytest.mark.skipif(not ARCHIVE.exists(), reason="run-4 archive not present")
def test_replay_run4_matches_concept_11_expectations():
    from evals.consistency_replay import load_runs, replay

    rows = {(r["scenario"], r["system"], r["repeat"]): set(r["codes"]) for r in replay(load_runs(ARCHIVE))}
    s05 = "S05-sensor-offset"
    for rep in range(3):
        assert rows[(s05, "v2", rep)] == {"K1", "K2", "K3"}, rows[(s05, "v2", rep)]  # K2: replay finding, see CONCEPT §11
        assert rows[(s05, "v1s", rep)] == {"K0"}, rows[(s05, "v1s", rep)]
        assert rows[(s05, "b0", rep)] == set()
        assert rows[(s05, "b1", rep)] == set()
    # no false marks on the known-good patterns (V1S has no describe_signal tool, so it carries K0 on S01 - coverage, not error)
    for scen in ("S01-temperature-drift", "S04-no-fault"):
        for sysname in ("b0", "v2"):
            for rep in range(3):
                assert rows[(scen, sysname, rep)] == set(), (scen, sysname, rep, rows[(scen, sysname, rep)])
    # S08: B0 compared lots across stations -> nothing; V2 never did (all three repeats) -> K4 only, no K1-K3
    for rep in range(3):
        assert rows[("S08-drift-and-bad-lot", "b0", rep)] == set()
        assert rows[("S08-drift-and-bad-lot", "v2", rep)] == {"K4"}, rows[("S08-drift-and-bad-lot", "v2", rep)]
    # the exploratory S08w/V2 r2 did compare lots across stations -> nothing
    assert rows[("S08w-drift-and-bad-lot-weak", "v2", 2)] == set()
