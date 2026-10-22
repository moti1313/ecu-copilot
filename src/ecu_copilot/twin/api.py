"""REST API of the digital twin. Run with:  uvicorn ecu_copilot.twin.api:app --port 8001"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .. import config
from .models import ActiveFault, Fault, StationInfo, StatsResponse, TestResult, Variant
from .simulator import STATIONS, Simulator

sim = Simulator()
_subscribers: set[asyncio.Queue[TestResult]] = set()


async def _run_station(station: int, interval_s: float) -> None:
    while True:
        result = await asyncio.to_thread(sim.tick, station)
        for q in list(_subscribers):
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(result)
        await asyncio.sleep(interval_s)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    n = sim.seed_history(config.TWIN_SEED_MINUTES, config.TWIN_INTERVAL_S)
    print(f"[twin] seeded {n} historical results ({config.TWIN_SEED_MINUTES} min)")
    tasks = [asyncio.create_task(_run_station(s.station, config.TWIN_INTERVAL_S)) for s in STATIONS]
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()


app = FastAPI(
    title="EOL Test Line Digital Twin",
    description="Three end-of-line test stations for door control units, with fault injection.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def require_key(x_api_key: str | None = Header(default=None)) -> None:
    """Optional: enforced only when TWIN_API_KEY is set. Fault injection and reset change the shared simulation."""
    if config.TWIN_API_KEY and x_api_key != config.TWIN_API_KEY:
        raise HTTPException(status_code=401, detail="missing or invalid X-API-Key")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "results": len(sim._results), "active_faults": len(sim.faults())}


@app.get("/stations", response_model=list[StationInfo])
def stations() -> list[StationInfo]:
    return sim.stations()


@app.get("/results", response_model=list[TestResult])
def results(
    station: int | None = Query(default=None, ge=1, le=3),
    variant: Variant | None = None,
    minutes: int | None = Query(default=None, ge=1, le=240),
    only_failed: bool = False,
    limit: int = Query(default=50, ge=1, le=10000),
) -> list[TestResult]:
    return sim.results(station=station, variant=variant, minutes=minutes, only_failed=only_failed, limit=limit)


@app.get("/stats", response_model=StatsResponse)
def stats(minutes: int = Query(default=10, ge=1, le=240)) -> StatsResponse:
    return sim.stats(minutes=minutes)


@app.get("/faults", response_model=list[ActiveFault])
def faults() -> list[ActiveFault]:
    return sim.faults()


@app.post("/faults", response_model=ActiveFault, status_code=201, dependencies=[Depends(require_key)])
def add_fault(fault: Fault) -> ActiveFault:
    if hasattr(fault, "station") and fault.station not in {s.station for s in STATIONS}:
        raise HTTPException(status_code=404, detail=f"station {fault.station} does not exist")
    return sim.add_fault(fault)


@app.delete("/faults", dependencies=[Depends(require_key)])
def clear_faults() -> dict:
    return {"cleared": sim.clear_faults()}


@app.post("/reset", dependencies=[Depends(require_key)])
def reset(seed: int = 42, history_minutes: int = Query(default=30, ge=0, le=240)) -> dict:
    """Clean, reproducible state: no faults, fresh seeded history. Used by the benchmark between scenarios."""
    n = sim.reset(seed=seed, history_minutes=history_minutes, interval_s=config.TWIN_INTERVAL_S)
    return {"reset": True, "seed": seed, "seeded_results": n}


@app.delete("/faults/{fault_id}", dependencies=[Depends(require_key)])
def delete_fault(fault_id: int) -> dict:
    if not sim.clear_faults(fault_id):
        raise HTTPException(status_code=404, detail="fault not found")
    return {"cleared": 1}


@app.get("/series")
def series(
    station: int = Query(ge=1, le=3),
    variant: Variant | None = None,
    minutes: int = Query(default=30, ge=1, le=240),
    bucket_s: int = Query(default=30, ge=5, le=600),
) -> dict:
    """Bucketed signal history plus every failed unit, for the signal view."""
    return sim.series(station=station, variant=variant, minutes=minutes, bucket_s=bucket_s)


@app.get("/events")
async def events() -> StreamingResponse:
    """Server-sent events: one JSON test result per line as they happen."""
    queue: asyncio.Queue[TestResult] = asyncio.Queue(maxsize=500)
    _subscribers.add(queue)

    async def gen() -> AsyncIterator[str]:
        try:
            while True:
                r = await queue.get()
                yield f"data: {r.model_dump_json()}\n\n"
        finally:
            _subscribers.discard(queue)

    return StreamingResponse(gen(), media_type="text/event-stream")
