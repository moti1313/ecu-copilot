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

    def records(self) -> list[QuestionRecord]:
        return list(self._records)

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


# --- Prometheus exposition -----------------------------------------------------------------------
# Text format for a Prometheus scrape. Recomputed from the appended records on every scrape, so the
# counters are monotonic. No client library: the format is a handful of lines and stays dependency-free.
LATENCY_BUCKETS_S = (5, 10, 20, 30, 60, 90, 120, 180, 300, 600, 1200)  # quantiles above the last finite bucket are clamped by Prometheus


def _label(v: object) -> str:
    return str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def prometheus_text(records: list[QuestionRecord], health: dict | None = None) -> str:
    health = health or {}
    rs = records
    lines: list[str] = []

    def metric(name: str, kind: str, help_text: str, samples: list[tuple[str, float]]) -> None:
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} {kind}")
        for labels, value in samples:
            lines.append(f"{name}{labels} {value:g}")

    metric("ecu_copilot_questions_total", "counter", "Questions answered (including failed ones)", [("", len(rs))])
    metric("ecu_copilot_errors_total", "counter", "Questions that ended in an error", [("", sum(1 for r in rs if r.error))])
    metric(
        "ecu_copilot_citation_missing_total",
        "counter",
        "Document answers the guardrail flagged as uncited",
        [("", sum(1 for r in rs if r.citation_missing))],
    )
    tokens = {
        "input": sum(r.usage.get("input_tokens", 0) for r in rs),
        "output": sum(r.usage.get("output_tokens", 0) for r in rs),
        "cache_read": sum(r.usage.get("cache_read_input_tokens", 0) for r in rs),
        "cache_creation": sum(r.usage.get("cache_creation_input_tokens", 0) for r in rs),
    }
    metric("ecu_copilot_tokens_total", "counter", "Model tokens by kind", [(f'{{kind="{k}"}}', v) for k, v in tokens.items()])
    metric(
        "ecu_copilot_cost_usd_total",
        "counter",
        "Calculated model cost from token usage and configured prices (USD)",
        [("", sum(r.cost_usd for r in rs))],
    )
    metric("ecu_copilot_iterations_total", "counter", "Model calls summed over all questions", [("", sum(r.iterations for r in rs))])
    tools = Counter(t for r in rs for t in r.tools)
    metric(
        "ecu_copilot_tool_calls_total",
        "counter",
        "Tool calls by tool name",
        [(f'{{tool="{_label(t)}"}}', n) for t, n in sorted(tools.items())],
    )

    extras = [r.extra or {} for r in rs]
    metric(
        "ecu_copilot_tool_errors_total",
        "counter",
        "Tool calls that returned an error object",
        [("", sum(int(e.get("tool_errors", 0) or 0) for e in extras))],
    )
    flag_counts = Counter(code for e in extras for code in (e.get("consistency_flags") or []))
    metric(
        "ecu_copilot_consistency_flags_total",
        "counter",
        "Consistency marks (CONCEPT §11) by code; a low number is not proof of a correct diagnosis",
        [(f'{{code="{_label(c)}"}}', n) for c, n in sorted(flag_counts.items())] or [('{code="none"}', 0)],
    )
    metric(
        "ecu_copilot_questions_with_flags_total",
        "counter",
        "Questions that carried at least one consistency mark",
        [("", sum(1 for e in extras if e.get("consistency_flags")))],
    )
    metric(
        "ecu_copilot_provenance_unverified_total",
        "counter",
        "Evidence items whose provenance did not verify",
        [("", sum(int(e.get("provenance_unverified", 0) or 0) for e in extras))],
    )
    metric(
        "ecu_copilot_injection_flags_total",
        "counter",
        "Retrieved document passages flagged by the prompt-injection screen",
        [("", sum(int(e.get("injection_hits", 0) or 0) for e in extras))],
    )

    lat = sorted(r.latency_s for r in rs)
    lines.append("# HELP ecu_copilot_latency_seconds Answer latency per question")
    lines.append("# TYPE ecu_copilot_latency_seconds histogram")
    for b in LATENCY_BUCKETS_S:
        lines.append(f'ecu_copilot_latency_seconds_bucket{{le="{b}"}} {sum(1 for x in lat if x <= b)}')
    lines.append(f'ecu_copilot_latency_seconds_bucket{{le="+Inf"}} {len(lat)}')
    lines.append(f"ecu_copilot_latency_seconds_sum {sum(lat):g}")
    lines.append(f"ecu_copilot_latency_seconds_count {len(lat)}")

    metric(
        "ecu_copilot_twin_reachable",
        "gauge",
        "1 if the Twin answered the last health check",
        [("", 1 if health.get("twin_reachable") else 0)],
    )
    metric("ecu_copilot_index_ready", "gauge", "1 if the document index is loaded", [("", 1 if health.get("index_ready") else 0)])
    info_labels = (
        f'{{provider="{_label(health.get("provider", ""))}",model="{_label(health.get("model", ""))}",'
        f'prompt_version="{_label(config.PROMPT_VERSION)}"}}'
    )
    metric("ecu_copilot_build_info", "gauge", "Static configuration labels", [(info_labels, 1)])
    return "\n".join(lines) + "\n"
