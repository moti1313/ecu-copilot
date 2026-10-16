"""Copilot service. Run with:  uvicorn ecu_copilot.copilot.api:app --port 8000

Endpoints: POST /ask, GET /bom, POST /decisions, GET /decisions, GET /metrics, GET /metrics/recent,
GET /health, GET /config, GET / (investigation workspace).
"""

from __future__ import annotations

import contextlib
import json
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from opentelemetry import trace
from pydantic import BaseModel, Field

from .. import config
from ..rag.index import DocumentIndex
from . import tools
from .agent import make_copilot
from .metrics import MetricsStore, now_iso
from .telemetry import setup_tracing
from .twin_client import TwinClient

STATIC_DIR = Path(__file__).parent / "static"
DECISIONS_FILE = config.DATA_DIR / "decisions.jsonl"
INVESTIGATIONS_FILE = config.DATA_DIR / "investigations.jsonl"
state: dict = {"investigations": {}}


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    provider = setup_tracing()
    index = DocumentIndex()
    if not index.chunks_file.exists():
        print("[copilot] no index found - building it (first run downloads the embedding model)")
        index.build()
    index.load()
    tools.configure(index=index, twin=TwinClient())
    metrics = MetricsStore()
    state["copilot"] = make_copilot(metrics=metrics, tracer_provider=provider)
    state["metrics"] = metrics
    state["index"] = index
    print(
        f"[copilot] ready: provider={config.LLM_PROVIDER} model={config.AGENT_MODEL} rag={index.mode} "
        f"twin={config.TWIN_URL} otel={config.OTEL_ENDPOINT}"
    )
    yield
    provider.shutdown()


app = FastAPI(title="ECU Copilot", version="0.2.0", lifespan=lifespan)
tracer = trace.get_tracer("ecu-copilot.api")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class Decision(BaseModel):
    """What the engineer decided about the agent's proposal. It only records the decision - nothing is
    blocked or re-tested by this endpoint (that is phase 2). Bound to a stored investigation."""

    investigation_id: str = Field(min_length=8, max_length=64)
    decision: str = Field(pattern="^(approve_test|block_units|reject|request_8d)$")
    note: str = Field(default="", max_length=2000)
    engineer: str = Field(default="", max_length=120)


def _store_investigation(question: str, result) -> str:
    """Keep what the engineer saw, server-side, so a decision can be tied to it."""
    inv_id = uuid.uuid4().hex
    record = {
        "investigation_id": inv_id,
        "timestamp": now_iso(),
        "question": question[:4000],
        "trace_id": result.trace_id,
        "provider": result.provider,
        "model": result.model,
        "prompt_version": result.prompt_version,
        "finding": (result.report or {}).get("finding"),
        "next_test": ((result.report or {}).get("next_test") or {}).get("title"),
        "error": result.error,
    }
    state["investigations"][inv_id] = record
    INVESTIGATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with INVESTIGATIONS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return inv_id


@app.post("/ask")
def ask(req: AskRequest) -> dict:
    with tracer.start_as_current_span("ask") as span:
        span.set_attribute("question", req.question[:200])
        result = state["copilot"].ask(req.question)
        span.set_attribute("cost_usd", result.cost_usd)
        span.set_attribute("tool_calls", len(result.tool_calls))
        span.set_attribute("citation_missing", result.citation_missing)
        if result.error:
            span.set_attribute("error", result.error)
        payload = result.to_dict()
        payload["investigation_id"] = _store_investigation(req.question, result)
        return payload


@app.get("/bom")
def bom() -> dict:
    path = config.DOCS_DIR / "BOM-DCU.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"parts": []}


@app.post("/decisions", status_code=201)
def add_decision(d: Decision) -> dict:
    inv = state["investigations"].get(d.investigation_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="unknown investigation_id - decisions must refer to a stored investigation")
    record = {
        "timestamp": now_iso(),
        **d.model_dump(),
        "trace_id": inv["trace_id"],
        "question": inv["question"],
        "next_test": inv["next_test"],
        "finding": inv["finding"],
        "effect": "recorded_only",  # phase 2 adds retest / blocking; until then the UI must say exactly this
    }
    DECISIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with DECISIONS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


@app.get("/decisions")
def decisions(n: int = 20) -> list[dict]:
    if not DECISIONS_FILE.exists():
        return []
    rows = [json.loads(line) for line in DECISIONS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows[-n:][::-1]


@app.get("/metrics")
def metrics() -> dict:
    return state["metrics"].summary()


@app.get("/metrics/recent")
def metrics_recent(n: int = 20) -> list[dict]:
    return state["metrics"].recent(n)


@app.get("/health")
def health() -> dict:
    twin_ok = True
    try:
        tools._get_twin().health()
    except Exception:  # noqa: BLE001
        twin_ok = False
    return {
        "status": "ok",
        "twin_reachable": twin_ok,
        "index_ready": state["index"].ready,
        "provider": config.LLM_PROVIDER,
        "model": config.AGENT_MODEL,
    }


@app.get("/config")
def ui_config() -> dict:
    return {
        "twin_url": config.TWIN_PUBLIC_URL,
        "jaeger_url": config.JAEGER_UI_URL,
        "provider": config.LLM_PROVIDER,
        "model": config.AGENT_MODEL,
        "rag_mode": config.RAG_MODE,
        "prompt_version": config.PROMPT_VERSION,
    }


@app.get("/")
def index_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
