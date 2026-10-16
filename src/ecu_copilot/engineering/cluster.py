"""cluster_failures: is a failure code concentrated in one lot / firmware / station / hour?

Concentration needs a reference: 70 % of the failures from one lot mean nothing if that lot is
90 % of the units tested. Two references are reported for every group:
- lift  = share of failures ÷ share of tested units (1.0 = failures spread like the exposure).
  Note that lift is capped by exposure: a lot that is half of all units can never exceed 2.0.
- rate ratio = failure rate inside the group ÷ failure rate of everything else, with a two-proportion
  z-score. "Concentrated" = rate ratio ≥ 3, z ≥ 3 and at least `min_failures` failures.
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import datetime

KEYS = {
    "lot": lambda r: r["lot"],
    "variant": lambda r: r["variant"],
    "station": lambda r: f"EOL-{r['station']}",
    "firmware": lambda r: r.get("firmware_version", "n/a"),
    "hour": lambda r: datetime.fromisoformat(r["timestamp"]).strftime("%H:00"),
    "code": lambda r: r.get("failure_code") or "pass",
}


def _two_proportion_z(f_in: int, n_in: int, f_out: int, n_out: int) -> float:
    if n_in == 0 or n_out == 0:
        return 0.0
    p_in, p_out = f_in / n_in, f_out / n_out
    p = (f_in + f_out) / (n_in + n_out)
    se = math.sqrt(p * (1 - p) * (1 / n_in + 1 / n_out)) if 0 < p < 1 else 0.0
    return (p_in - p_out) / se if se else 0.0


def cluster_failures(
    results: list[dict],
    by: str = "lot",
    code: str | None = None,
    min_failures: int = 10,
    ratio_threshold: float = 3.0,
    z_threshold: float = 3.0,
) -> dict:
    if by not in KEYS:
        return {"error": f"unknown grouping {by}; choose one of {sorted(KEYS)}"}
    key = KEYS[by]
    exposure = Counter(key(r) for r in results)
    fails = Counter(key(r) for r in results if r["verdict"] == "fail" and (code is None or r.get("failure_code") == code))
    n_fail, n_all = sum(fails.values()), len(results)
    groups = []
    for k, tested in exposure.most_common():
        f = fails.get(k, 0)
        share_f = f / n_fail if n_fail else 0.0
        share_e = tested / n_all if n_all else 0.0
        rate_in = f / tested if tested else 0.0
        rate_out = (n_fail - f) / (n_all - tested) if n_all > tested else 0.0
        groups.append(
            {
                "group": k,
                "tested": tested,
                "failed": f,
                "failure_rate_pct": round(100.0 * rate_in, 1),
                "failure_rate_others_pct": round(100.0 * rate_out, 1),
                "share_of_failures_pct": round(100.0 * share_f, 1),
                "share_of_tested_pct": round(100.0 * share_e, 1),
                "lift": round(share_f / share_e, 2) if share_e and n_fail else 0.0,
                "rate_ratio": round(min(rate_in / rate_out, 999.0), 2)
                if rate_out
                else (999.0 if rate_in else 0.0),  # 999 = no failures elsewhere
                "z": round(_two_proportion_z(f, tested, n_fail - f, n_all - tested), 2),
            }
        )
    groups.sort(key=lambda g: (g["z"], g["failed"]), reverse=True)
    top = groups[0] if groups else None
    concentrated = bool(top and top["rate_ratio"] >= ratio_threshold and top["z"] >= z_threshold and top["failed"] >= min_failures)
    return {
        "by": by,
        "code": code,
        "failures": n_fail,
        "tested": n_all,
        "concentrated": concentrated,
        "top": top,
        "groups": groups[:10],
        "criterion": f"rate ratio ≥ {ratio_threshold}, z ≥ {z_threshold}, failures ≥ {min_failures}",
        "note": "lift = share of failures / share of tested (capped by exposure); rate_ratio = group rate / rate of all others",
    }
