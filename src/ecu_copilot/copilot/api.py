"""Copilot service. Run with:  uvicorn ecu_copilot.copilot.api:app --port 8000

Endpoints: POST /ask, GET /metrics, GET /metrics/recent, GET /health, GET /config, GET / (dashboard).
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from pathlib import Path

import anthropic
from fastapi import FastAPI
from fastapi.responses import FileResponse
from opentelemetry import trace
from pydantic import BaseModel, Field

from .. import config
from ..rag.index import DocumentIndex
from . import tools
from .agent import Copilot
from .metrics import MetricsStore
from .telemetry import setup_tracing
from .twin_client import TwinClient

STATIC_DIR = Path(__file__).parent / "static"
state: dict = {}


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
    client = anthropic.Anthropic(open_telemetry={"tracer_provider": provider})
    state["copilot"] = Copilot(client=client, metrics=metrics)
    state["metrics"] = metrics
    state["index"] = index
    print(f"[copilot] ready: model={config.AGENT_MODEL} rag={index.mode} twin={config.TWIN_URL} otel={config.OTEL_ENDPOINT}")
    yield
    provider.shutdown()


app = FastAPI(title="ECU Copilot", version="0.1.0", lifespan=lifespan)
tracer = trace.get_tracer("ecu-copilot.api")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


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
        return result.to_dict()


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
    return {"status": "ok", "twin_reachable": twin_ok, "index_ready": state["index"].ready, "model": config.AGENT_MODEL}


@app.get("/config")
def ui_config() -> dict:
    return {
        "twin_url": config.TWIN_PUBLIC_URL,
        "jaeger_url": config.JAEGER_UI_URL,
        "model": config.AGENT_MODEL,
        "rag_mode": config.RAG_MODE,
    }


@app.get("/")
def index_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
