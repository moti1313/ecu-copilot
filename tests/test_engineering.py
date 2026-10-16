"""Deterministic engineering layer: spec consistency with the markdown, validity, change, clusters, descriptors."""

import re
from datetime import timedelta

from ecu_copilot.engineering.change import detect_change
from ecu_copilot.engineering.cluster import cluster_failures
from ecu_copilot.engineering.describe import describe_signal
from ecu_copilot.engineering.spec import load_spec
from ecu_copilot.engineering.validity import check_validity, classify_result
from ecu_copilot.twin.models import AcousticNoise, BadLot, TemperatureDrift
from tests.conftest import DOCS_DIR


def _rows(sim, station, minutes, now):
    return [r.model_dump(mode="json") for r in sim.results(station=station, minutes=minutes, limit=10000, now=now)]


def _run(sim, station, start, n=400):
    for i in range(1, n + 1):
        sim.tick(station, now=start + timedelta(seconds=1.5 * i))
    return start + timedelta(seconds=1.5 * n)


def test_spec_json_matches_markdown_limit_table():
    """The JSON is the machine-readable copy; the markdown is the source of truth."""
    spec = load_spec()
    md = (DOCS_DIR / "TS-DCU-EOL.md").read_text(encoding="utf-8")
    row = next(line for line in md.splitlines() if line.startswith("| Quiescent current"))
    nums = [float(x) for x in re.findall(r"≤ (\d+) µA", row)]
    assert nums == [spec["limits"]["A"]["quiescent_max_ua"], spec["limits"]["B"]["quiescent_max_ua"]]
    row = next(line for line in md.splitlines() if line.startswith("| Flash + verify time"))
    assert [float(x) for x in re.findall(r"≤ (\d+) s", row)] == [spec["limits"]["A"]["flash_max_s"], spec["limits"]["B"]["flash_max_s"]]
    assert re.search(r"between \*\*18 °C and 32 °C\*\*", md) and spec["validity"]["board_temp_c"] == {
        **spec["validity"]["board_temp_c"],
        "min": 18.0,
        "max": 32.0,
    }
    assert "**≤ 45 dB(A)**" in md and spec["validity"]["ambient_noise_db"]["max"] == 45.0
    assert re.search(r"revision: D", md) and spec["revision"] == "D"
    assert set(spec["codes"]) == {"E-120", "E-204", "E-205", "E-310", "E-401"}


def test_validity_marks_hot_e204_as_invalid_not_fail(sim, now):
    sim.add_fault(TemperatureDrift(station=2, ramp_s=0), now=now)
    end = _run(sim, 2, now)
    rows = _rows(sim, 2, 10, end)
    v = check_validity(rows)
    assert v["codes"]["E-204"]["invalid_per_spec"] >= 5
    assert v["codes"]["E-204"]["fail_after_validity"] == 0  # every hot E-204 is INVALID, none is a real FAIL
    assert v["invalid_examples"][0]["rule"] == "TS-DCU-EOL §4.2"
    assert "does not mean the unit is good" in v["note"]
    # a cold E-120 stays a real FAIL
    e120 = next(r for r in rows if r["failure_code"] == "E-120")
    assert classify_result(e120, load_spec())[0] == "fail"


def test_validity_noise(sim, now):
    sim.add_fault(AcousticNoise(station=3, noise_db=57), now=now)
    end = _run(sim, 3, now)
    v = check_validity(_rows(sim, 3, 10, end))
    assert v["codes"]["E-310"]["invalid_per_spec"] >= 10 and v["invalid_examples"][0]["rule"] == "TS-DCU-EOL §6.1"


def test_detect_change_finds_onset_of_drift(sim, now):
    end = _run(sim, 2, now, n=400)  # 10 min normal
    sim.add_fault(TemperatureDrift(station=2, ramp_s=0), now=end)
    end2 = _run(sim, 2, end, n=400)  # 10 min hot
    rows = _rows(sim, 2, 30, end2)
    temp = detect_change(rows, metric="board_temp_c", bucket_s=60, now=end2)
    assert temp["significant"] and temp["direction"] == "up" and temp["level_after"] - temp["level_before"] > 7
    onset_delta = abs((__import__("datetime").datetime.fromisoformat(temp["onset"]) - end).total_seconds())
    assert onset_delta <= 120  # within two buckets of the true onset
    rate = detect_change(rows, metric="failure_rate", bucket_s=60, now=end2)
    assert rate["direction"] == "up"


def test_detect_change_is_quiet_on_normal_data(sim, now):
    rows = _rows(sim, 1, 20, now)
    out = detect_change(rows, metric="failure_rate", bucket_s=60, now=now)
    assert out["significant"] is False or abs(out["relative_change_pct"] or 0) < 300


def test_cluster_lift_reflects_exposure(sim, now):
    sim.add_fault(BadLot(lot="L2439-07", fail_rate=0.3), now=now)
    end = _run(sim, 3, now)
    c = cluster_failures(_rows(sim, 3, 10, end), by="lot", code="E-120")
    assert c["concentrated"] and c["top"]["group"] == "L2439-07" and c["top"]["rate_ratio"] >= 3
    # the same lot's share of tested units is < 60 %, so the lift is not an artefact of exposure
    assert c["top"]["share_of_tested_pct"] < 60
    nothing = cluster_failures(_rows(sim, 1, 20, now), by="lot")
    assert nothing["concentrated"] is False


def test_describe_signal_flags_and_relation(sim, now):
    end = _run(sim, 2, now, n=200)
    sim.add_fault(TemperatureDrift(station=2, ramp_s=0), now=end)
    end2 = _run(sim, 2, end, n=200)
    d = describe_signal(_rows(sim, 2, 20, end2))
    assert d["iq_t1_relation"] == "iq_follows_t1"
    assert any("outside 18.0–32.0" in f for f in d["flags"])
    assert d["stats"]["board_temp_c"]["trend"] == "up"
