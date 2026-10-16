"""Phase 0 corrections from the external reviews: simulator thread safety, decisions bound to stored
investigations, eval gate counting skipped cases as failed."""

import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from ecu_copilot.twin.models import TemperatureDrift
from ecu_copilot.twin.simulator import Simulator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evals.run import pass_rate  # noqa: E402


def test_readers_do_not_crash_while_stations_tick():
    """Before: iterating the deque during an append raised RuntimeError('deque mutated during iteration')."""
    sim = Simulator(seed=3)
    now = datetime.now(UTC)
    sim.seed_history(minutes=5, interval_s=1.5, now=now)
    errors: list[BaseException] = []
    stop = threading.Event()

    def writer(station: int):
        i = 0
        while not stop.is_set():
            i += 1
            sim.tick(station, now=now + timedelta(seconds=i))

    def reader():
        try:
            while not stop.is_set():
                sim.stats(minutes=5, now=now + timedelta(seconds=400))
                sim.results(station=2, minutes=5, limit=500, now=now + timedelta(seconds=400))
                sim.series(station=2, minutes=5, bucket_s=10, now=now + timedelta(seconds=400))
                sim.faults()
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(s,)) for s in (1, 2, 3)] + [threading.Thread(target=reader) for _ in range(3)]
    for t in threads:
        t.start()
    threading.Event().wait(0.8)
    stop.set()
    for t in threads:
        t.join(timeout=5)
    assert not errors, errors[:1]
    sim.add_fault(TemperatureDrift(station=2), now=now)
    assert len(sim.faults()) == 1


def test_decisions_require_a_stored_investigation(tmp_path, monkeypatch):
    from ecu_copilot.copilot import api

    monkeypatch.setattr(api, "DECISIONS_FILE", tmp_path / "decisions.jsonl")
    monkeypatch.setattr(api, "INVESTIGATIONS_FILE", tmp_path / "investigations.jsonl")
    api.state.update({"metrics": None, "index": None, "copilot": None, "investigations": {}})
    client = TestClient(api.app)

    # no investigation yet -> 404, nothing written
    r = client.post("/decisions", json={"investigation_id": "deadbeefdeadbeef", "decision": "approve_test"})
    assert r.status_code == 404 and not (tmp_path / "decisions.jsonl").exists()

    fake = SimpleNamespace(
        trace_id="t-1",
        provider="openai",
        model="m",
        prompt_version="p",
        error=None,
        report={"finding": "pseudo_failure", "next_test": {"title": "Re-Test"}},
    )
    inv_id = api._store_investigation("Warum?", fake)
    r = client.post("/decisions", json={"investigation_id": inv_id, "decision": "block_units", "engineer": "M. Molaei"})
    assert r.status_code == 201
    body = r.json()
    assert body["effect"] == "recorded_only" and body["trace_id"] == "t-1" and body["next_test"] == "Re-Test"
    assert client.get("/decisions").json()[0]["investigation_id"] == inv_id
    # old payload shape (free-text question / trace) is no longer accepted
    assert client.post("/decisions", json={"trace_id": "x", "question": "q", "decision": "reject"}).status_code == 422


def test_pass_rate_counts_skipped_as_failed():
    rows = [{"status": "pass"}, {"status": "pass"}, {"status": "skipped"}, {"status": "fail"}]
    passed, skipped, rate = pass_rate(rows)
    assert (passed, skipped) == (2, 1)
    assert rate == 0.5  # not 2/3
    assert pass_rate([]) == (0, 0, 0.0)
