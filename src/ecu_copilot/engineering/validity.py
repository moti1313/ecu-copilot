"""check_validity: apply the specification's environmental validity rules to each result.

The station firmware reports FAIL; the specification says a measurement taken outside the temperature
window or above the noise limit is INVALID, not FAIL (TS-DCU-EOL §4.2, §6.1). This function is the
deterministic version of that rule - the agent must not decide validity by reading numbers itself.
"""

from __future__ import annotations

from collections import Counter

from .spec import load_spec


def classify_result(r: dict, spec: dict) -> tuple[str, str | None, str | None]:
    """Return (status, reason, rule) with status in {'pass', 'fail', 'invalid'}."""
    m = r["measurements"]
    code = r.get("failure_code")
    temp = spec["validity"]["board_temp_c"]
    noise = spec["validity"]["ambient_noise_db"]
    if r["verdict"] == "pass":
        return "pass", None, None
    if code in temp["applies_to_codes"] and not (temp["min"] <= m["board_temp_c"] <= temp["max"]):
        return "invalid", f"board_temp_c {m['board_temp_c']} outside {temp['min']}–{temp['max']} °C", temp["rule"]
    if code in noise["applies_to_codes"] and m["ambient_noise_db"] > noise["max"]:
        return "invalid", f"ambient_noise_db {m['ambient_noise_db']} above {noise['max']} dB(A)", noise["rule"]
    return "fail", None, None


def check_validity(results: list[dict], spec: dict | None = None, max_examples: int = 20) -> dict:
    """Summarise a window of results: per failure code, how many FAIL verdicts are INVALID per spec."""
    spec = spec or load_spec()
    per_code: dict[str, Counter] = {}
    invalid_examples: list[dict] = []
    real_examples: list[dict] = []
    totals = Counter()
    for r in results:
        status, reason, rule = classify_result(r, spec)
        totals[status] += 1
        if status == "pass":
            continue
        c = per_code.setdefault(r["failure_code"], Counter())
        c[status] += 1
        example = {
            "serial": r["serial"],
            "lot": r["lot"],
            "t": r["timestamp"],
            "code": r["failure_code"],
            "board_temp_c": r["measurements"]["board_temp_c"],
            "ambient_noise_db": r["measurements"]["ambient_noise_db"],
            "quiescent_current_ua": r["measurements"]["quiescent_current_ua"],
        }
        if status == "invalid":
            example["reason"], example["rule"] = reason, rule
            if len(invalid_examples) < max_examples:
                invalid_examples.append(example)
        elif len(real_examples) < max_examples:
            real_examples.append(example)

    codes = {
        code: {
            "fail_verdicts": c["fail"] + c["invalid"],
            "invalid_per_spec": c["invalid"],
            "fail_after_validity": c["fail"],
            "environmental_code": spec["codes"].get(code, {}).get("environmental"),
            "first_check": spec["codes"].get(code, {}).get("first_check"),
        }
        for code, c in sorted(per_code.items())
    }
    n_fail = totals["fail"] + totals["invalid"]
    return {
        "tested": len(results),
        "pass": totals["pass"],
        "fail_verdicts": n_fail,
        "invalid_per_spec": totals["invalid"],
        "invalid_share_pct": round(100.0 * totals["invalid"] / n_fail, 1) if n_fail else 0.0,
        "codes": codes,
        "rules": {"board_temp_c": spec["validity"]["board_temp_c"], "ambient_noise_db": spec["validity"]["ambient_noise_db"]},
        "spec": {"doc_id": spec["doc_id"], "revision": spec["revision"]},
        "invalid_examples": invalid_examples,
        "fail_examples": real_examples,
        "note": "INVALID = no assessment of the unit possible (re-test under valid conditions); it does not mean the unit is good.",
    }
