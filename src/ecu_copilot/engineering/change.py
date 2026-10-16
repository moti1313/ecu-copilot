"""detect_change: when did a metric shift, and is the shift significant?

Two-sample scan over time buckets: for every candidate split with at least `min_buckets` on each
side, compare the means before/after; the split with the largest standardised difference is the
onset. Deterministic, explainable, no learned parameters - the agent must not say "since 10 minutes"
without this.
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


def detect_change(
    results: list[dict],
    metric: str = "failure_rate",
    bucket_s: int = 60,
    min_buckets: int = 3,
    z_threshold: float = 3.0,
    now: datetime | None = None,
) -> dict:
    if metric not in METRICS:
        return {"error": f"unknown metric {metric}; choose one of {sorted(METRICS)}"}
    buckets = bucketize(results, bucket_s, now)
    values = [METRICS[metric](b["results"]) for b in buckets]
    if len(values) < 2 * min_buckets:
        return {"metric": metric, "bucket_s": bucket_s, "buckets": len(values), "significant": False, "reason": "not enough data"}

    best = None
    for i in range(min_buckets, len(values) - min_buckets + 1):
        before, after = values[:i], values[i:]
        sd = _std(before) or _std(values) or 1e-9
        z = (_mean(after) - _mean(before)) / (sd / math.sqrt(len(before)))
        if best is None or abs(z) > abs(best["z"]):
            best = {"i": i, "z": z, "before": _mean(before), "after": _mean(after)}
    assert best is not None
    rel = (best["after"] - best["before"]) / abs(best["before"]) if best["before"] else float("inf")
    significant = abs(best["z"]) >= z_threshold and abs(best["after"] - best["before"]) > 0
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
        "direction": "up" if best["after"] > best["before"] else "down",
        "series": [round(v, 2) for v in values],
    }
