from collections import Counter
from datetime import timedelta

from ecu_copilot.twin.models import AcousticNoise, BadLot, TemperatureDrift, Variant
from ecu_copilot.twin.simulator import LIMITS, Simulator


def _run(sim: Simulator, station: int, start, n: int = 400):
    for i in range(1, n + 1):
        sim.tick(station, now=start + timedelta(seconds=1.5 * i))
    return start + timedelta(seconds=1.5 * n)


def test_baseline_failure_rate_is_low(sim, now):
    for g in sim.stats(minutes=20, now=now).groups:
        assert g.tested > 200
        assert g.failure_rate_pct < 4.0, g


def test_temperature_drift_raises_e204_mostly_on_variant_b(sim, now):
    sim.add_fault(TemperatureDrift(station=2, ramp_s=0), now=now)  # default delta
    end = _run(sim, 2, now)
    groups = {g.variant: g for g in sim.stats(minutes=10, now=end).groups if g.station == 2}
    assert groups[Variant.B].failure_rate_pct > 5.0
    assert groups[Variant.B].failure_codes.get("E-204", 0) > groups[Variant.A].failure_codes.get("E-204", 0)
    assert groups[Variant.B].mean_board_temp_c > 32.0  # outside the spec's validity window


def test_station_firmware_does_not_know_the_validity_window(sim, now):
    """The deliberate gap: a hot station reports FAIL (E-204), the spec says INVALID."""
    sim.add_fault(TemperatureDrift(station=2, ramp_s=0), now=now)
    end = _run(sim, 2, now)
    failed = sim.results(station=2, minutes=10, only_failed=True, limit=500, now=end)
    e204 = [r for r in failed if r.failure_code == "E-204"]
    assert e204
    assert all(r.measurements.quiescent_current_ua > LIMITS[r.variant]["quiescent_max_ua"] for r in e204)


def test_acoustic_noise_raises_e310(sim, now):
    sim.add_fault(AcousticNoise(station=3, noise_db=57), now=now)
    end = _run(sim, 3, now)
    g = next(g for g in sim.stats(minutes=10, now=end).groups if g.station == 3)
    assert g.failure_codes.get("E-310", 0) >= 10
    assert g.mean_ambient_noise_db > 45.0


def test_bad_lot_clusters_e120_on_one_lot(sim, now):
    sim.add_fault(BadLot(variant=Variant.B, lot="L2439-07", fail_rate=0.2), now=now)
    end = _run(sim, 3, now)
    failed = sim.results(station=3, minutes=10, only_failed=True, limit=500, now=end)
    lots = Counter(r.lot for r in failed if r.failure_code == "E-120")
    assert lots.most_common(1)[0][0] == "L2439-07"


def test_clear_faults(sim, now):
    sim.add_fault(TemperatureDrift(station=1), now=now)
    sim.add_fault(AcousticNoise(station=1), now=now)
    assert sim.clear_faults() == 2
    assert sim.faults() == []
