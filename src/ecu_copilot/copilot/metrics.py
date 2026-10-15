"""Per-question metrics: what you need to run an LLM feature in production and answer
"what does it cost, how slow is it, is it getting worse". Appended to a JSONL file
(survives restarts, greppable) and summarised in memory for /metrics.
"""

from __future__ import annotations

import json
import statistics
import threading
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .. import config


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    def add(self, u) -> None:  # u: anthropic usage object
        self.input_tokens += u.input_tokens or 0
        self.output_tokens += u.output_tokens or 0
        self.cache_read_input_tokens += getattr(u, "cache_read_input_tokens", 0) or 0
        self.cache_creation_input_tokens += getattr(u, "cache_creation_input_tokens", 0) or 0

    def cost_usd(self, model: str) -> float:
        p_in, p_out, p_cw, p_cr = config.PRICING.get(model, config.PRICING["claude-opus-5-5"])
        return (
            self.input_tokens * p_in
            + self.output_tokens * p_out
            + self.cache_creation_input_tokens * p_cw
            + self.cache_read_input_tokens * p_cr
        ) / 1_000_000


@dataclass
class QuestionRecord:
    timestamp: str
    question: str
    model: str
    prompt_version: str
    latency_s: float
    iterations: int
    tools: list[str]
    usage: dict
    cost_usd: float
    citation_missing: bool
    error: str | None = None
    trace_id: str | None = None
    extra: dict = field(default_factory=dict)


class MetricsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config.METRICS_FILE
        self._lock = threading.Lock()
        self._records: list[QuestionRecord] = []
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._records.append(QuestionRecord(**json.loads(line)))

    def record(self, rec: QuestionRecord) -> None:
        with self._lock:
            self._records.append(rec)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")

    def recent(self, n: int = 20) -> list[dict]:
        return [asdict(r) for r in self._records[-n:]][::-1]

    def summary(self) -> dict:
        rs = self._records
        if not rs:
            return {"questions": 0}
        lat = [r.latency_s for r in rs]
        cache_read = sum(r.usage.get("cache_read_input_tokens", 0) for r in rs)
        inp = sum(r.usage.get("input_tokens", 0) for r in rs) + cache_read
        tools = Counter(t for r in rs for t in r.tools)
        return {
            "questions": len(rs),
            "errors": sum(1 for r in rs if r.error),
            "total_cost_usd": round(sum(r.cost_usd for r in rs), 4),
            "avg_cost_usd": round(sum(r.cost_usd for r in rs) / len(rs), 4),
            "avg_latency_s": round(statistics.fmean(lat), 2),
            "p95_latency_s": round(sorted(lat)[int(0.95 * (len(lat) - 1))], 2),
            "avg_iterations": round(statistics.fmean(r.iterations for r in rs), 2),
            "cache_hit_ratio": round(cache_read / inp, 3) if inp else 0.0,
            "citation_missing": sum(1 for r in rs if r.citation_missing),
            "tool_calls": dict(tools.most_common()),
            "prompt_versions": dict(Counter(r.prompt_version for r in rs)),
            "since": rs[0].timestamp,
        }


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
