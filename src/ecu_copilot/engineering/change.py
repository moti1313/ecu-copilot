"""detect_change: when did a metric shift, and is the shift significant?

Two-sample scan over time buckets: for every candidate split with at least `min_buckets` on each
side, compare before/after; the split with the largest standardised difference is the onset.
Deterministic, explainable, no learned parameters - the agent must not say "since 10 minutes"
without this.

Statistics (corrected after the run-4 dry run, 16.10.): the first version used the standard error of
the BEFORE buckets as the scale, which is tiny for a quiet failure-rate series (buckets of ~25 units
read 0 / 4 / 8 %) and produced false alarms on an unchanged line (S04).
- failure_rate: two-proportion z-test on COUNTS (failures vs tested, before vs after), plus a minimum
  effect: at least +1.5 percentage points AND +50 % relative. A rate going from 1.6 % to 2.4 % is noise.
- measurements: Welch z on bucket means with the pooled within-segment spread, plus a minimum effect
  of 1.0 pooled standard deviation.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

METRICS = {
    "failure_rate": lambda rs: 100.0 * sum(1 for r in rs if r["verdict"] == "fail") / len(rs),
    "quiescent_current_ua": lambda rs: _mean([r["measurements"]["quiescent_current_ua"] for r in rs]),
    "board_temp_c": lambda rs: _mean([r["measurements"]["board_temp_c"] for r in rs]),
    "ambient_noise_db": lambda rs: _mean([r["measurements"]["ambient_noise_db"] for r in rs]),
    "acoustic_score": lambda rs: _mean([r["measurements"]["acoustic_score"] for r in rs]),
}
MIN_RATE_EFFECT_PP = 1.5  # percentage points
MIN_RATE_EFFECT_REL = 0.5  # +50 % relative to the level before


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def _std(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def bucketize(results: list[dict], bucket_s: int, now: datetime | None = None) -> list[dict]:
    """Group results into fixed buckets ending at `now` (oldest first). Empty buckets are dropped."""
    if not results:
        return []
    ts = [datetime.fromisoformat(r["timestamp"]) for r in results]
    end = now or max(ts)
    groups: dict[int, list[dict]] = {}
    for r, t in zip(results, ts, strict=True):
        key = int((end - t).total_seconds() // bucket_s)
        groups.setdefault(key, []).append(r)
    out = []
    for key in sorted(groups, reverse=True):
        rs = groups[key]
        out.append({"t": (end - timedelta(seconds=(key + 1) * bucket_s)).isoformat(), "n": len(rs), "results": rs})
    return out


def _rate_split(buckets: list[dict], i: int) -> tuple[float, float, float]:
    """Two-proportion z on counts for split i. Returns (p_before %, p_after %, z)."""
    before = [r for b in buckets[:i] for r in b["results"]]
    after = [r for b in buckets[i:] for r in b["results"]]
    f1, n1 = sum(1 for r in before if r["verdict"] == "fail"), len(before)
    f2, n2 = sum(1 for r in after if r["verdict"] == "fail"), len(after)
    p1, p2 = f1 / n1, f2 / n2
    p = (f1 + f2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2)) if 0 < p < 1 else 0.0
    return 100 * p1, 100 * p2, ((p2 - p1) / se if se else 0.0)


def _mean_split(values: list[float], i: int) -> tuple[float, float, float, float]:
    """Welch z on bucket means with pooled within-segment spread. Returns (m_before, m_after, z, sd_pooled)."""
    before, after = values[:i], values[i:]
    s1, s2 = _std(before), _std(after)
    sd_pooled = (
        math.sqrt(((len(before) - 1) * s1**2 + (len(after) - 1) * s2**2) / max(1, len(before) + len(after) - 2)) or _std(values) or 1e-9
    )
    se = math.sqrt(s1**2 / len(before) + s2**2 / len(after)) or sd_pooled / math.sqrt(min(len(before), len(after)))
    return _mean(before), _mean(after), (_mean(after) - _mean(before)) / se, sd_pooled


def detect_change(
    results: list[dict],
    metric: str = "failure_rate",
    bucket_s: int = 60,
    min_buckets: int = 3,
    min_units: int = 120,
    z_threshold: float = 3.5,
    now: datetime | None = None,
) -> dict:
    if metric not in METRICS:
        return {"error": f"unknown metric {metric}; choose one of {sorted(METRICS)}"}
    buckets = bucketize(results, bucket_s, now)
    values = [METRICS[metric](b["results"]) for b in buckets]
    if len(values) < 2 * min_buckets:
        return {"metric": metric, "bucket_s": bucket_s, "buckets": len(values), "significant": False, "reason": "not enough data"}

    # Scanning ~60 split points is a multiple-comparison problem: tiny edge segments (3 buckets ≈ 75 units) reach
    # z ≈ 3 by chance. Both segments must hold at least `min_units` results, and z must clear 3.5.
    best = None
    for i in range(min_buckets, len(values) - min_buckets + 1):
        n_before = sum(b["n"] for b in buckets[:i])
        n_after = sum(b["n"] for b in buckets[i:])
        if n_before < min_units or n_after < min_units:
            continue
        if metric == "failure_rate":
            m1, m2, z = _rate_split(buckets, i)
            diff = abs(m2 - m1)
            effect_ok = diff >= MIN_RATE_EFFECT_PP and diff >= MIN_RATE_EFFECT_REL * max(min(m1, m2), 0.5)
        else:
            m1, m2, z, sd = _mean_split(values, i)
            effect_ok = abs(m2 - m1) >= 1.0 * sd
        if best is None or abs(z) > abs(best["z"]):
            best = {"i": i, "z": z, "before": m1, "after": m2, "effect_ok": effect_ok}
    if best is None:
        return {
            "metric": metric,
            "bucket_s": bucket_s,
            "buckets": len(values),
            "significant": False,
            "reason": f"segments below {min_units} units",
        }
    rel = (best["after"] - best["before"]) / abs(best["before"]) if best["before"] else float("inf")
    significant = abs(best["z"]) >= z_threshold and best["effect_ok"]
    return {
        "metric": metric,
        "bucket_s": bucket_s,
        "buckets": len(values),
        "window_from": buckets[0]["t"],
        "window_to": buckets[-1]["t"],
        "onset": buckets[best["i"]]["t"],
        "level_before": round(best["before"], 2),
        "level_after": round(best["after"], 2),
        "relative_change_pct": round(100.0 * rel, 1) if math.isfinite(rel) else None,
        "z": round(best["z"], 2),
        "significant": significant,
        "min_effect": {"failure_rate": f"+{MIN_RATE_EFFECT_PP} pp and +{int(100 * MIN_RATE_EFFECT_REL)} %", "other": "1.0 pooled sd"}[
            "failure_rate" if metric == "failure_rate" else "other"
        ],
        "direction": "up" if best["after"] > best["before"] else "down",
        "series": [round(v, 2) for v in values],
    }
