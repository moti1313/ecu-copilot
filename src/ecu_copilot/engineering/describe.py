"""describe_signal: compact text descriptors of a window instead of raw rows.

Statistics, trend (first half vs second half), the Iq-T1 relation, and flags the specification cares
about. The relation is judged on LEVELS against the leakage model, not on correlation: a window that
is uniformly hot has little variation and a low correlation although the current follows the
temperature perfectly. "Decoupled" (T1 says hot, Iq stays at its 25 °C level) is the signature of a
faulty temperature sensor.
"""

from __future__ import annotations

import math

from .spec import load_spec

MEASUREMENTS = ["quiescent_current_ua", "operating_current_a", "flash_time_s", "board_temp_c", "ambient_noise_db", "acoustic_score"]
LEAKAGE_COEFF_PER_K = 0.03  # system level (DS-MCU-XM32F7 §7.3: ~3.5 %/K for the MCU alone)
MIN_MODEL_RISE_UA = 8.0  # below this expected rise the relation cannot be judged


def _mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def _pearson(xs, ys) -> float | None:
    n = len(xs)
    if n < 5:
        return None
    mx, my = _mean(xs), _mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / math.sqrt(sxx * syy)


def describe_signal(results: list[dict], spec: dict | None = None) -> dict:
    spec = spec or load_spec()
    if not results:
        return {"tested": 0, "flags": ["no data"]}
    rs = sorted(results, key=lambda r: r["timestamp"])
    half = len(rs) // 2
    stats = {}
    for m in MEASUREMENTS:
        xs = [r["measurements"][m] for r in rs]
        first, second = _mean(xs[:half]) if half else float("nan"), _mean(xs[half:])
        stats[m] = {
            "mean": round(_mean(xs), 2),
            "min": round(min(xs), 2),
            "max": round(max(xs), 2),
            "first_half": round(first, 2) if half else None,
            "second_half": round(second, 2),
            "trend": ("up" if second - first > 0 else "down") if half and abs(second - first) > 1e-9 else "flat",
        }
    iq = [r["measurements"]["quiescent_current_ua"] for r in rs]
    t1 = [r["measurements"]["board_temp_c"] for r in rs]
    corr = _pearson(t1, iq)

    tw = spec["validity"]["board_temp_c"]
    nw = spec["validity"]["ambient_noise_db"]
    temp_out = sum(1 for x in t1 if not (tw["min"] <= x <= tw["max"]))
    noise_out = sum(1 for r in rs if r["measurements"]["ambient_noise_db"] > nw["max"])

    # Level check against the leakage model: what Iq SHOULD be at the reported temperatures (per variant),
    # versus what it is. ratio ≈ 1 -> current follows the reported temperature; ratio ≈ 0 -> it does not.
    typical = {v: spec["limits"][v]["typical_quiescent_ua"] for v in ("A", "B")}
    typ_mean = _mean([typical[r["variant"]] for r in rs])
    expected_mean = _mean(
        [typical[r["variant"]] * (1.0 + LEAKAGE_COEFF_PER_K * max(0.0, r["measurements"]["board_temp_c"] - 25.0)) for r in rs]
    )
    model_rise = expected_mean - typ_mean
    iq_rise = _mean(iq) - typ_mean
    ratio = (iq_rise / model_rise) if model_rise >= MIN_MODEL_RISE_UA else None

    flags = []
    if temp_out:
        flags.append(f"T1 outside {tw['min']}–{tw['max']} °C in {temp_out}/{len(rs)} results ({tw['rule']})")
    if noise_out:
        flags.append(f"ambient noise above {nw['max']} dB(A) in {noise_out}/{len(rs)} results ({nw['rule']})")
    if ratio is None:
        relation = "not assessable"
        note = f"reported T1 close to nominal (model expects only +{model_rise:.0f} µA) - nothing to judge"
    elif ratio >= 0.5:
        relation = "iq_follows_t1"
        note = (
            f"Iq is +{iq_rise:.0f} µA above the 25 °C level, the leakage model expects +{model_rise:.0f} µA at the reported T1 - consistent"
        )
        flags.append(note)
    else:
        relation = "decoupled"
        note = (
            f"reported T1 (mean {stats['board_temp_c']['mean']} °C) would raise Iq by ~{model_rise:.0f} µA, "
            f"measured rise is {iq_rise:+.0f} µA "
            "- temperature reading and current do not agree; check the T1 sensor before treating these results as invalid"
        )
        flags.append(note)

    return {
        "tested": len(rs),
        "from": rs[0]["timestamp"],
        "to": rs[-1]["timestamp"],
        "stats": stats,
        "iq_t1_correlation": round(corr, 2) if corr is not None else None,
        "iq_t1_relation": relation,
        "iq_model": {
            "typical_ua": round(typ_mean, 1),
            "expected_at_reported_t1_ua": round(expected_mean, 1),
            "measured_ua": round(_mean(iq), 1),
            "ratio": round(ratio, 2) if ratio is not None else None,
            "note": note,
        },
        "flags": flags,
        "spec": {"doc_id": spec["doc_id"], "revision": spec["revision"]},
    }
