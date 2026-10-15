"""Central configuration. Everything comes from environment variables (12-factor),
with defaults that work for local development. A `.env` file is loaded if present.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[2]


def _env_path(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, str(default))).expanduser()


# --- LLM ---------------------------------------------------------------------
# Two providers behind one interface (copilot/agent.py). Anthropic is the primary path
# (tool runner, prompt caching, SDK tracing); OpenAI is the alternative path with a hand-written loop.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER") or "anthropic"  # anthropic | openai  ("or": empty env = unset)
_DEFAULT_MODELS = {
    "anthropic": ("claude-opus-5-5", "claude-haiku-5-5"),
    "openai": ("gpt-5", "gpt-5-mini"),
}
AGENT_MODEL = os.environ.get("AGENT_MODEL") or _DEFAULT_MODELS.get(LLM_PROVIDER, _DEFAULT_MODELS["anthropic"])[0]
JUDGE_MODEL = os.environ.get("JUDGE_MODEL") or _DEFAULT_MODELS.get(LLM_PROVIDER, _DEFAULT_MODELS["anthropic"])[1]
AGENT_EFFORT = os.environ.get("AGENT_EFFORT") or "medium"  # low | medium | high
AGENT_MAX_TOKENS = int(os.environ.get("AGENT_MAX_TOKENS", "8000"))
PROMPT_VERSION = "2026-10-15.1"  # bump when the system prompt changes; logged with every answer

# USD per 1M tokens: (input, output, cache_write, cache_read). Used for the cost log only.
PRICING = {
    "claude-opus-5-5": (4.00, 20.00, 5.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 2.50, 0.20),
    "claude-haiku-5-5": (0.10, 0.50, 0.125, 0.01),
    "gpt-5": (1.25, 10.00, 1.25, 0.125),
    "gpt-5-mini": (0.25, 2.00, 0.25, 0.025),
    "gpt-5-nano": (0.05, 0.40, 0.05, 0.005),
}

# --- Services ----------------------------------------------------------------
TWIN_URL = os.environ.get("TWIN_URL", "http://localhost:8001")  # as seen from the copilot process
TWIN_PUBLIC_URL = os.environ.get("TWIN_PUBLIC_URL", TWIN_URL)  # as seen from the browser (docker: localhost)
TWIN_INTERVAL_S = float(os.environ.get("TWIN_INTERVAL_S", "1.5"))  # seconds between units per station
TWIN_SEED_MINUTES = int(os.environ.get("TWIN_SEED_MINUTES", "30"))  # history generated at startup
JAEGER_UI_URL = os.environ.get("JAEGER_UI_URL", "http://localhost:16686")

# --- RAG ---------------------------------------------------------------------
DOCS_DIR = _env_path("DOCS_DIR", ROOT_DIR / "docs")
DATA_DIR = _env_path("DATA_DIR", ROOT_DIR / "data")
CHROMA_DIR = _env_path("CHROMA_DIR", DATA_DIR / "chroma")
RAG_MODE = os.environ.get("RAG_MODE", "hybrid")  # hybrid (vector + BM25) | bm25 (no model download)
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
RAG_TOP_K = int(os.environ.get("RAG_TOP_K", "5"))

# --- Observability -----------------------------------------------------------
OTEL_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")  # e.g. http://localhost:4318
OTEL_SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "ecu-copilot")
METRICS_FILE = DATA_DIR / "metrics.jsonl"
REPORTS_DIR = DATA_DIR / "reports"
