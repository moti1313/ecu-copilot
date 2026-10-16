"""describe_signal: compact text descriptors of a window instead of raw rows.

Statistics, trend (first half vs second half), the Iq-T1 relation, and flags the specification cares
about. The decoupling flag ("T1 rose but Iq did not follow") is the signature of a temperature-sensor
fault - correlation alone would mislead there.
"""

from __future__ import annotations

import math

from .spec import load_spec

MEASUREMENTS = ["quiescent_current_ua", "operating_current_a", "flash_time_s", "board_temp_c", "ambient_noise_db", "acoustic_score"]


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
    t1_rise = stats["board_temp_c"]["second_half"] - (stats["board_temp_c"]["first_half"] or stats["board_temp_c"]["second_half"])
    iq_rel = (
        (stats["quiescent_current_ua"]["second_half"] / stats["quiescent_current_ua"]["first_half"] - 1.0)
        if stats["quiescent_current_ua"]["first_half"]
        else 0.0
    )
    expected_rel = 0.03 * max(0.0, t1_rise)  # the system-level leakage model, ~3 %/K (DS-MCU-XM32F7 §7.3 gives 3.5 %/K for the MCU alone)

    flags = []
    if temp_out:
        flags.append(f"T1 outside {tw['min']}–{tw['max']} °C in {temp_out}/{len(rs)} results ({tw['rule']})")
    if noise_out:
        flags.append(f"ambient noise above {nw['max']} dB(A) in {noise_out}/{len(rs)} results ({nw['rule']})")
    relation = "not assessable"
    if t1_rise >= 3.0:
        if iq_rel >= 0.5 * expected_rel and iq_rel > 0.02:
            relation = "iq_follows_t1"
            flags.append(
                f"Iq rose {100 * iq_rel:.1f} % while T1 rose {t1_rise:.1f} K - consistent with the leakage model "
                f"(~{100 * expected_rel:.0f} % expected)"
            )
        else:
            relation = "decoupled"
            flags.append(
                f"T1 rose {t1_rise:.1f} K but Iq changed only {100 * iq_rel:.1f} % (model expects ~{100 * expected_rel:.0f} %) "
                "- temperature reading and current do not agree; check the T1 sensor"
            )
    elif corr is not None and abs(corr) < 0.2 and temp_out:
        relation = "decoupled"
        flags.append("T1 is outside the window but Iq does not track it (|r| < 0.2) - check the T1 sensor")
    elif corr is not None and corr > 0.5:
        relation = "iq_follows_t1"

    return {
        "tested": len(rs),
        "from": rs[0]["timestamp"],
        "to": rs[-1]["timestamp"],
        "stats": stats,
        "iq_t1_correlation": round(corr, 2) if corr is not None else None,
        "iq_t1_relation": relation,
        "flags": flags,
        "spec": {"doc_id": spec["doc_id"], "revision": spec["revision"]},
    }
