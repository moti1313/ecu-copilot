"""Jev (TypeSafe System One) shadow experiment - CONCEPT.md §12. Not wired into the answer path.

Jev answers typed questions (Choice / Noul) over a *state* and returns a distribution, no text. Here it gets
the same stored tool outputs as V2 (never V2's report) and is asked which counter-check should come first and
whether the T1 path / a product defect is suspected. Everything is logged; nothing is acted upon.

HTTP per docs.typesafe.ai (read 2026-10-17): POST https://api.typesafe.ai/v1/systemone, Bearer key,
body {state, model, questions}, answers keyed like the questions. Model is pinned to an exact version because
the `jev-latest` alias moves between releases.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

MODEL = "jev-1.13.0"  # exact version, see CONCEPT §12
BASE_URL = "https://api.typesafe.ai"
ENGINEERING_TOOLS = ("get_station_stats", "check_validity", "detect_change", "describe_signal", "cluster_failures")
DOC_EXCERPT_CHARS = 600
NOUL_YES, NOUL_NO = 0.7, 0.3

NEXT_CHECK_OPTIONS = {
    "reference_thermometer": "Compare the station's T1 temperature reading against an independent reference thermometer first.",
    "retest_valid_temperature": "Re-test the affected units under a valid temperature window (after cooling / at another station) first.",
    "lot_cross_station": "Investigate the suspected lot across all stations (failure concentration by lot, all stations) first.",
    "collect_more_data": "No decision yet: collect more measurements before any counter-check.",
    "no_additional_check": "No additional investigation is justified by the data (normal background failure rate).",
}

QUESTIONS: dict[str, dict[str, Any]] = {
    "next_check": {
        "type": "choice",
        "instructions": "Which counter-check should an EOL test engineer run FIRST, given the tool outputs in the state?",
        "criteria": NEXT_CHECK_OPTIONS,
    },
    "t1_unreliable": {
        "type": "noul",
        "instructions": "The station's T1 temperature measurement path is unreliable (the reported temperature should not be trusted).",
    },
    "product_defect": {
        "type": "noul",
        "instructions": "There is evidence of a product defect that is independent of the test environment (e.g. a lot concentration).",
    },
}

# Pre-registered expectations per scenario (CONCEPT §12). Q1 may list several acceptable options.
EXPECTED: dict[str, dict[str, Any]] = {
    "S01-temperature-drift": {"next_check": {"retest_valid_temperature"}, "t1_unreliable": False, "product_defect": False},
    "S04-no-fault": {"next_check": {"no_additional_check"}, "t1_unreliable": False, "product_defect": False},
    "S05-sensor-offset": {"next_check": {"reference_thermometer"}, "t1_unreliable": True, "product_defect": False},
    "S08-drift-and-bad-lot": {
        "next_check": {"lot_cross_station", "retest_valid_temperature"},
        "t1_unreliable": False,
        "product_defect": True,
    },
    "S08w-drift-and-bad-lot-weak": {
        "next_check": {"lot_cross_station", "retest_valid_temperature"},
        "t1_unreliable": False,
        "product_defect": True,
    },
}


# ---------------------------------------------------------------------------------------------
def choice_confidence(probabilities: dict[str, float]) -> float:
    """TypeSafe's documented formula for Choice: (p_max - 1/n) / (1 - 1/n)."""
    n = len(probabilities)
    if n < 2:
        return 1.0
    return max(0.0, (max(probabilities.values()) - 1 / n) / (1 - 1 / n))


def noul_verdict(p: float) -> str:
    return "yes" if p >= NOUL_YES else "no" if p <= NOUL_NO else "undecided"


def build_state(question: str, tool_calls: list, spec: dict | None) -> dict:
    """Same evidence V2 saw, nothing V2 concluded. Deterministic given the stored run."""
    tools, docs = [], []
    for c in tool_calls or []:
        name, inp, raw = getattr(c, "name", None), getattr(c, "input", None) or {}, getattr(c, "output", "") or ""
        try:
            out = json.loads(raw)
        except (TypeError, ValueError):
            out = raw
        if name in ENGINEERING_TOOLS:
            tools.append({"tool": name, "input": inp, "output": out})
        elif name == "search_docs" and isinstance(out, list):
            for hit in out:
                if isinstance(hit, dict):
                    docs.append({"citation": hit.get("citation"), "text": str(hit.get("text") or "")[:DOC_EXCERPT_CHARS]})
    state: dict[str, Any] = {"engineer_question": question, "tool_outputs": tools, "document_excerpts": docs}
    if spec:
        state["specification"] = {"limits": spec.get("limits"), "validity": spec.get("validity")}
    return state


def state_digest(state: dict) -> str:
    return hashlib.sha256(json.dumps(state, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------------------------
@dataclass
class JevResponse:
    model_requested: str
    model: str
    answers: dict[str, Any]
    usage: dict[str, Any]
    request_id: str | None
    latency_ms: int
    state_sha256: str
    question_keys: list[str] = field(default_factory=list)

    def verdicts(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, a in self.answers.items():
            if a.get("type") == "choice":
                out[k] = {"choice": a.get("choice"), "confidence": a.get("confidence"), "probabilities": a.get("probabilities")}
            elif a.get("type") == "noul":
                out[k] = {"noul": a.get("noul"), "verdict": noul_verdict(float(a.get("noul", 0.5)))}
        return out


class JevClient:
    """Thin HTTP client. `transport` lets tests inject httpx.MockTransport - no network, no key."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = MODEL,
        base_url: str = BASE_URL,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
    ):
        self.api_key = api_key if api_key is not None else os.environ.get("TYPESAFE_API_KEY", "")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(transport=transport, timeout=timeout) if transport else httpx.Client(timeout=timeout)

    def system_one(self, state: dict | str | list, questions: dict[str, dict] = QUESTIONS) -> JevResponse:
        if not self.api_key:
            raise RuntimeError("TYPESAFE_API_KEY is not set (put it in .env, never in the repo)")
        body = {"state": state, "model": self.model, "questions": questions}
        t0 = time.perf_counter()
        resp = self._client.post(
            f"{self.base_url}/v1/systemone",
            json=body,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        latency = int((time.perf_counter() - t0) * 1000)
        resp.raise_for_status()
        data = resp.json()
        return JevResponse(
            model_requested=self.model,
            model=str(data.get("model", "")),
            answers=data.get("answers") or {},
            usage=data.get("usage") or {},
            request_id=resp.headers.get("x-typesafe-request-id"),
            latency_ms=latency,
            state_sha256=state_digest(state) if isinstance(state, dict) else hashlib.sha256(json.dumps(state).encode()).hexdigest(),
            question_keys=list(questions.keys()),
        )


# ---------------------------------------------------------------------------------------------
def score_against_expected(scenario: str, verdicts: dict[str, Any]) -> dict[str, Any]:
    exp = EXPECTED.get(scenario)
    if not exp:
        return {"scored": False}
    q1 = verdicts.get("next_check", {}).get("choice")
    q2 = verdicts.get("t1_unreliable", {}).get("verdict")
    q3 = verdicts.get("product_defect", {}).get("verdict")
    want = lambda b: "yes" if b else "no"  # noqa: E731
    return {
        "scored": True,
        "next_check_ok": q1 in exp["next_check"],
        "t1_unreliable_ok": q2 == want(exp["t1_unreliable"]),
        "t1_unreliable_undecided": q2 == "undecided",
        "product_defect_ok": q3 == want(exp["product_defect"]),
        "product_defect_undecided": q3 == "undecided",
        "unnecessary_check": scenario == "S04-no-fault" and q1 not in (None, "no_additional_check"),
    }


def log_line(path: Path, run_key: dict, response: JevResponse, scoring: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        **run_key,
        **asdict(response),
        "verdicts": response.verdicts(),
        "scoring": scoring,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
