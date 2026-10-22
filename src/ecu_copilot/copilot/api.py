"""Copilot service. Run with:  uvicorn ecu_copilot.copilot.api:app --port 8000

Endpoints: POST /ask, GET /bom, POST /decisions, GET /decisions, GET /metrics, GET /metrics/recent,
GET /health (compat), GET /health/live, GET /health/ready, GET /config, GET / (investigation workspace).
"""

from __future__ import annotations

import contextlib
import json
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import FileResponse, PlainTextResponse
from opentelemetry import trace
from pydantic import BaseModel, Field

from .. import config
from ..rag.index import DocumentIndex
from . import tools
from .agent import make_copilot
from .metrics import MetricsStore, now_iso, prometheus_text
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
    state["investigations"] = _load_investigations()
    print(
        f"[copilot] ready: provider={config.LLM_PROVIDER} model={config.AGENT_MODEL} rag={index.mode} "
        f"twin={config.TWIN_URL} otel={config.OTEL_ENDPOINT}"
    )
    yield
    provider.shutdown()


app = FastAPI(title="ECU Copilot", version="0.2.0", lifespan=lifespan)
tracer = trace.get_tracer("ecu-copilot.api")


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Optional: enforced only when ECU_API_KEY is set. Protects the paid and the state-changing endpoints."""
    if config.ECU_API_KEY and x_api_key != config.ECU_API_KEY:
        raise HTTPException(status_code=401, detail="missing or invalid X-API-Key")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class Decision(BaseModel):
    """What the engineer decided about the agent's proposal. It only records the decision - nothing is
    blocked or re-tested by this endpoint (that is phase 2). Bound to a stored investigation."""

    investigation_id: str = Field(min_length=8, max_length=64)
    decision: str = Field(pattern="^(approve_test|block_units|reject|request_8d)$")
    note: str = Field(default="", max_length=2000)
    engineer: str = Field(default="", max_length=120)


def _load_investigations() -> dict[str, dict]:
    """Rebuild the id -> investigation mapping from the append-only file, so decisions survive a restart.

    Recovery rule (review R4): a line that does not parse is skipped and counted, never fatal. A truncated LAST
    line is the expected result of an interrupted append; a corrupt line in the middle is reported the same way
    but is not expected. The count is exposed in /health as `investigations_corrupt_lines`."""
    state["investigations_corrupt_lines"] = 0
    if not INVESTIGATIONS_FILE.exists():
        return {}
    out: dict[str, dict] = {}
    # bytes, not text: an append interrupted inside a multi-byte character must not raise UnicodeDecodeError here
    raw_lines = INVESTIGATIONS_FILE.read_bytes().split(b"\n")
    for n, raw in enumerate(raw_lines, start=1):
        if not raw.strip():
            continue
        try:
            rec = json.loads(raw.decode("utf-8"))
            out[rec["investigation_id"]] = rec
        except (ValueError, KeyError, TypeError, UnicodeDecodeError):
            state["investigations_corrupt_lines"] += 1
            where = "truncated last line" if n == len(raw_lines) else f"corrupt line {n}"
            print(f"[copilot] WARNING investigations.jsonl: {where} skipped ({len(out)} records loaded so far)")
    return out


def _find_investigation(inv_id: str) -> dict | None:
    """Memory first; on a miss re-read the file (another process or a restart may have written it)."""
    inv = state["investigations"].get(inv_id)
    if inv is None:
        state["investigations"].update(_load_investigations())
        inv = state["investigations"].get(inv_id)
    return inv


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
    _append_jsonl(INVESTIGATIONS_FILE, record)
    return inv_id


def _append_jsonl(path: Path, record: dict) -> None:
    """Append one JSON line. If the file does not end with a newline (an earlier append was interrupted), terminate
    that fragment first, so the new record is never glued to it and lost on the next load (review round 2)."""
    needs_newline = False
    if path.exists() and path.stat().st_size > 0:
        with path.open("rb") as r:  # append mode cannot read; check the last byte separately
            r.seek(-1, 2)
            needs_newline = r.read(1) != b"\n"
    with path.open("ab") as f:
        if needs_newline:
            f.write(b"\n")
        f.write(json.dumps(record, ensure_ascii=False).encode("utf-8") + b"\n")


@app.post("/ask", dependencies=[Depends(require_api_key)])
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


@app.post("/decisions", status_code=201, dependencies=[Depends(require_api_key)])
def add_decision(d: Decision) -> dict:
    inv = _find_investigation(d.investigation_id)
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
    _append_jsonl(DECISIONS_FILE, record)
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


@app.get("/metrics/prometheus", response_class=PlainTextResponse)
def metrics_prometheus() -> str:
    """Prometheus text exposition of the same per-question metrics (see docker-compose.monitoring.yml)."""
    return prometheus_text(state["metrics"].records(), health())


def _health_snapshot() -> dict:
    twin_ok = True
    try:
        tools._get_twin().health()
    except Exception:  # noqa: BLE001
        twin_ok = False
    index_ready = bool(state.get("index") is not None and state["index"].ready)
    return {
        "status": "ok" if (twin_ok and index_ready) else "degraded",
        "twin_reachable": twin_ok,
        "index_ready": index_ready,
        "provider": config.LLM_PROVIDER,
        "model": config.AGENT_MODEL,
        "investigations_corrupt_lines": int(state.get("investigations_corrupt_lines", 0) or 0),
    }


@app.get("/health")
def health() -> dict:
    """Compatibility endpoint: always HTTP 200 with the detailed fields; `status` is ok or degraded."""
    return _health_snapshot()


@app.get("/health/live")
def health_live() -> dict:
    """Liveness: the process answers. Never depends on the Twin or the index."""
    return {"status": "alive"}


@app.get("/health/ready")
def health_ready(response: Response) -> dict:
    """Readiness: 200 only when the Twin is reachable and the index is loaded, otherwise 503 with the reason."""
    snap = _health_snapshot()
    if snap["status"] != "ok":
        response.status_code = 503
    return snap


@app.get("/config")
def ui_config() -> dict:
    return {
        "twin_url": config.TWIN_PUBLIC_URL,
        "jaeger_url": config.JAEGER_UI_URL,
        "provider": config.LLM_PROVIDER,
        "model": config.AGENT_MODEL,
        "rag_mode": config.RAG_MODE,
        "prompt_version": config.PROMPT_VERSION,
        "auth_required": bool(config.ECU_API_KEY),  # the UI then asks for the key once and sends X-API-Key
        "twin_auth_required": bool(config.TWIN_API_KEY),
    }


@app.get("/")
def index_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
