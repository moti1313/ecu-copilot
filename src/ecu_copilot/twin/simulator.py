"""The stateful generator behind the twin API.

Design notes
- Limits below are the station firmware's copy of the EOL spec (docs/TS-DCU-EOL.md).
  Deliberately, the firmware does NOT implement the spec's environmental validity rule
  (§4.2: results outside 18-32 °C are INVALID, not FAIL). That gap is what produces
  pseudo failures under temperature drift - exactly the kind of thing the copilot
  should find by comparing live data with the spec.
- Quiescent current rises with temperature (CMOS leakage, ~3.5 %/K above 25 °C).
  Variant B sits closer to its limit, so drift hits B first. That asymmetry is the
  story of the demo.
"""

from __future__ import annotations

import math
import random
import threading
from collections import Counter, deque
from datetime import UTC, datetime, timedelta

from .models import (
    AcousticNoise,
    ActiveFault,
    BadLot,
    Fault,
    GroupStats,
    Measurements,
    StationInfo,
    StatsResponse,
    TemperatureDrift,
    TestResult,
    Variant,
    Verdict,
)

# Station firmware limits (mirrors docs/TS-DCU-EOL.md §5)
LIMITS = {
    Variant.A: {"quiescent_max_ua": 350.0, "flash_max_s": 45.0},
    Variant.B: {"quiescent_max_ua": 450.0, "flash_max_s": 60.0},
}
OPERATING_CURRENT_A = (1.0, 2.4)
ACOUSTIC_MIN_SCORE = 70.0

# Nominal behaviour at 25 °C
QUIESCENT_NOMINAL = {Variant.A: (240.0, 20.0), Variant.B: (330.0, 25.0)}  # mean, sd in µA
# System-level coefficient: the MCU's sleep current rises ~3.5 %/K (DS-MCU-XM32F7 §7.3), but part of the
# DCU quiescent current (antenna polling, transceiver) is not leakage, so the total rises a bit slower.
LEAKAGE_COEFF_PER_K = 0.03
FLASH_NOMINAL = {Variant.A: (31.0, 2.5), Variant.B: (44.0, 3.0)}
NOISE_NOMINAL_DB = 41.0  # spec §6.1: acoustic test valid only up to 45 dB(A)

STATIONS = [
    StationInfo(station=1, name="EOL-1 (line A)", variants=[Variant.A], interval_s=1.5),
    StationInfo(station=2, name="EOL-2 (mixed)", variants=[Variant.A, Variant.B], interval_s=1.5),
    StationInfo(station=3, name="EOL-3 (line B)", variants=[Variant.B], interval_s=1.5),
]
GOOD_LOTS = {Variant.A: ["L2441-01", "L2441-02"], Variant.B: ["L2441-03", "L2441-04"]}


class Simulator:
    def __init__(self, seed: int = 42, max_results: int = 20_000) -> None:
        self._rng = random.Random(seed)
        self._lock = threading.Lock()
        self._results: deque[TestResult] = deque(maxlen=max_results)
        self._faults: dict[int, ActiveFault] = {}
        self._next_result_id = 1
        self._next_fault_id = 1
        self._seq: Counter[str] = Counter()
        # slow-moving ambient temperature per station (random walk around 24 °C)
        self._ambient_c = {s.station: 24.0 + self._rng.uniform(-1.0, 1.0) for s in STATIONS}

    # --- public API ---------------------------------------------------------------
    def stations(self) -> list[StationInfo]:
        return STATIONS

    def add_fault(self, fault: Fault, now: datetime | None = None) -> ActiveFault:
        with self._lock:
            active = ActiveFault(id=self._next_fault_id, started_at=now or _utcnow(), fault=fault)
            self._faults[active.id] = active
            self._next_fault_id += 1
            return active

    def faults(self) -> list[ActiveFault]:
        return list(self._faults.values())

    def clear_faults(self, fault_id: int | None = None) -> int:
        with self._lock:
            if fault_id is None:
                n = len(self._faults)
                self._faults.clear()
                return n
            return 1 if self._faults.pop(fault_id, None) else 0

    def results(
        self,
        *,
        station: int | None = None,
        variant: Variant | None = None,
        minutes: int | None = None,
        only_failed: bool = False,
        limit: int = 100,
        now: datetime | None = None,
    ) -> list[TestResult]:
        cutoff = (now or _utcnow()) - timedelta(minutes=minutes) if minutes else None
        out: list[TestResult] = []
        for r in reversed(self._results):  # newest first
            if cutoff and r.timestamp < cutoff:
                break
            if station is not None and r.station != station:
                continue
            if variant is not None and r.variant != variant:
                continue
            if only_failed and r.verdict != Verdict.FAIL:
                continue
            out.append(r)
            if len(out) >= limit:
                break
        return out

    def series(
        self, station: int, variant: Variant | None = None, minutes: int = 30, bucket_s: int = 30, now: datetime | None = None
    ) -> dict:
        """Time series for the signal view: per-bucket means plus every failed unit as a marker."""
        now = now or _utcnow()
        cutoff = now - timedelta(minutes=minutes)
        buckets: dict[int, list[TestResult]] = {}
        fails: list[dict] = []
        for r in reversed(self._results):
            if r.timestamp < cutoff:
                break
            if r.station != station or (variant is not None and r.variant != variant):
                continue
            key = int((r.timestamp - cutoff).total_seconds() // bucket_s)
            buckets.setdefault(key, []).append(r)
            if r.verdict == Verdict.FAIL and len(fails) < 400:
                m = r.measurements
                fails.append(
                    {
                        "t": r.timestamp.isoformat(),
                        "code": r.failure_code,
                        "serial": r.serial,
                        "lot": r.lot,
                        "variant": r.variant,
                        "quiescent_current_ua": m.quiescent_current_ua,
                        "board_temp_c": m.board_temp_c,
                        "ambient_noise_db": m.ambient_noise_db,
                        "acoustic_score": m.acoustic_score,
                        "operating_current_a": m.operating_current_a,
                        "flash_time_s": m.flash_time_s,
                    }
                )
        rows = []
        for key in sorted(buckets):
            rs = buckets[key]
            rows.append(
                {
                    "t": (cutoff + timedelta(seconds=key * bucket_s)).isoformat(),
                    "n": len(rs),
                    "failed": sum(1 for r in rs if r.verdict == Verdict.FAIL),
                    "quiescent_current_ua": _mean([r.measurements.quiescent_current_ua for r in rs]),
                    "board_temp_c": _mean([r.measurements.board_temp_c for r in rs]),
                    "ambient_noise_db": _mean([r.measurements.ambient_noise_db for r in rs]),
                    "acoustic_score": _mean([r.measurements.acoustic_score for r in rs]),
                }
            )
        limits = {
            "quiescent_max_ua": {v.value: LIMITS[v]["quiescent_max_ua"] for v in Variant},
            "flash_max_s": {v.value: LIMITS[v]["flash_max_s"] for v in Variant},
            "operating_current_a": list(OPERATING_CURRENT_A),
            "acoustic_min_score": ACOUSTIC_MIN_SCORE,
            "temp_valid_c": [18.0, 32.0],
            "noise_max_db": 45.0,
        }
        return {
            "station": station,
            "variant": variant.value if variant else None,
            "minutes": minutes,
            "bucket_s": bucket_s,
            "from_time": cutoff.isoformat(),
            "to_time": now.isoformat(),
            "buckets": rows,
            "fails": list(reversed(fails)),  # oldest first
            "limits": limits,
        }

    def stats(self, minutes: int = 10, now: datetime | None = None) -> StatsResponse:
        now = now or _utcnow()
        cutoff = now - timedelta(minutes=minutes)
        buckets: dict[tuple[int, Variant], list[TestResult]] = {}
        for r in reversed(self._results):
            if r.timestamp < cutoff:
                break
            buckets.setdefault((r.station, r.variant), []).append(r)

        groups: list[GroupStats] = []
        for (station, variant), rs in sorted(buckets.items()):
            failed = [r for r in rs if r.verdict == Verdict.FAIL]
            codes = Counter(r.failure_code for r in failed if r.failure_code)
            groups.append(
                GroupStats(
                    station=station,
                    variant=variant,
                    tested=len(rs),
                    failed=len(failed),
                    failure_rate_pct=round(100.0 * len(failed) / len(rs), 1) if rs else 0.0,
                    failure_codes=dict(codes.most_common()),
                    mean_board_temp_c=_mean([r.measurements.board_temp_c for r in rs]),
                    mean_ambient_noise_db=_mean([r.measurements.ambient_noise_db for r in rs]),
                    mean_quiescent_current_ua=_mean([r.measurements.quiescent_current_ua for r in rs]),
                    mean_acoustic_score=_mean([r.measurements.acoustic_score for r in rs]),
                )
            )
        return StatsResponse(window_minutes=minutes, from_time=cutoff, to_time=now, groups=groups)

    def tick(self, station: int, now: datetime | None = None) -> TestResult:
        """Test one unit at `station` and store the result."""
        now = now or _utcnow()
        info = next(s for s in STATIONS if s.station == station)
        variant = self._pick_variant(info)
        lot = self._pick_lot(variant)
        with self._lock:
            result = self._test_unit(info, variant, lot, now)
            self._results.append(result)
            return result

    def seed_history(self, minutes: int, interval_s: float, now: datetime | None = None) -> int:
        """Generate `minutes` of normal history before `now` so stats are meaningful at startup."""
        now = now or _utcnow()
        n_per_station = int(minutes * 60 / interval_s)
        count = 0
        for i in range(n_per_station, 0, -1):
            ts = now - timedelta(seconds=i * interval_s)
            for s in STATIONS:
                self.tick(s.station, now=ts)
                count += 1
        return count

    # --- internals ------------------------------------------------------------------
    def _pick_variant(self, info: StationInfo) -> Variant:
        if len(info.variants) == 1:
            return info.variants[0]
        return Variant.B if self._rng.random() < 0.6 else Variant.A

    def _pick_lot(self, variant: Variant) -> str:
        bad = [f.fault for f in self._faults.values() if isinstance(f.fault, BadLot) and f.fault.variant == variant]
        if bad and self._rng.random() < 0.5:
            return bad[0].lot
        return self._rng.choice(GOOD_LOTS[variant])

    def _station_temp(self, station: int, now: datetime) -> float:
        # ambient random walk, clamped to a realistic shop-floor band
        self._ambient_c[station] = min(25.5, max(23.5, self._ambient_c[station] + self._rng.gauss(0, 0.03)))
        temp = self._ambient_c[station]
        for af in self._faults.values():
            f = af.fault
            if isinstance(f, TemperatureDrift) and f.station == station:
                elapsed = (now - af.started_at).total_seconds()
                progress = min(1.0, max(0.0, elapsed / f.ramp_s)) if f.ramp_s > 0 else 1.0
                temp += f.delta_c * progress
        return temp + self._rng.gauss(0, 0.4)

    def _station_noise(self, station: int) -> float:
        noise = NOISE_NOMINAL_DB + self._rng.gauss(0, 1.5)
        for af in self._faults.values():
            f = af.fault
            if isinstance(f, AcousticNoise) and f.station == station:
                noise = f.noise_db + self._rng.gauss(0, 2.0)
        return noise

    def _test_unit(self, info: StationInfo, variant: Variant, lot: str, now: datetime) -> TestResult:
        rng = self._rng
        temp = self._station_temp(info.station, now)
        noise_db = self._station_noise(info.station)

        q_mean, q_sd = QUIESCENT_NOMINAL[variant]
        leakage_factor = 1.0 + LEAKAGE_COEFF_PER_K * max(0.0, temp - 25.0)
        quiescent = rng.gauss(q_mean * leakage_factor, q_sd)

        operating = rng.gauss(1.7, 0.18)
        if rng.random() < 0.002:  # rare real fault: stalled motor / short
            operating = rng.uniform(2.5, 3.2)

        f_mean, f_sd = FLASH_NOMINAL[variant]
        flash = rng.gauss(f_mean, f_sd)
        if rng.random() < 0.003:
            flash += rng.uniform(15, 30)  # rare: flash retry

        # acoustic score drops when the cell is noisy (hall noise leaks past the damping)
        acoustic = rng.gauss(88.0, 5.0) - max(0.0, noise_db - 45.0) * 1.0
        if rng.random() < 0.007:  # rare real fault: gear noise
            acoustic -= rng.uniform(20, 35)

        lin_ok = rng.random() > 0.008  # baseline intermittent LIN
        bad = [f.fault for f in self._faults.values() if isinstance(f.fault, BadLot)]
        for b in bad:
            if b.variant == variant and b.lot == lot and rng.random() < b.fail_rate:
                lin_ok = False

        m = Measurements(
            quiescent_current_ua=round(quiescent, 1),
            operating_current_a=round(operating, 2),
            flash_time_s=round(flash, 1),
            board_temp_c=round(temp, 1),
            ambient_noise_db=round(noise_db, 1),
            acoustic_score=round(max(0.0, min(100.0, acoustic)), 1),
            lin_comm_ok=lin_ok,
        )
        code = self._judge(variant, m)
        self._seq[f"{variant}{lot}"] += 1
        serial = f"DCU{variant}-{lot}-{self._seq[f'{variant}{lot}']:05d}"
        result = TestResult(
            id=self._next_result_id,
            timestamp=now,
            station=info.station,
            variant=variant,
            serial=serial,
            lot=lot,
            measurements=m,
            verdict=Verdict.FAIL if code else Verdict.PASS,
            failure_code=code,
        )
        self._next_result_id += 1
        return result

    @staticmethod
    def _judge(variant: Variant, m: Measurements) -> str | None:
        """Station firmware verdict, in the order the spec's test sequence runs (§3)."""
        lim = LIMITS[variant]
        if not m.lin_comm_ok:
            return "E-120"
        if m.flash_time_s > lim["flash_max_s"]:
            return "E-401"
        if m.quiescent_current_ua > lim["quiescent_max_ua"]:
            return "E-204"
        if not (OPERATING_CURRENT_A[0] <= m.operating_current_a <= OPERATING_CURRENT_A[1]):
            return "E-205"
        if m.acoustic_score < ACOUSTIC_MIN_SCORE:
            return "E-310"
        return None


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(math.fsum(values) / len(values), 1)
