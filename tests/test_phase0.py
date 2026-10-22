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


def test_decision_survives_restart_via_investigations_file(tmp_path, monkeypatch):
    """Review finding: the id -> investigation mapping lived only in memory, so after a restart a decision for a
    stored investigation was rejected with 404 although the record was still in investigations.jsonl."""
    from ecu_copilot.copilot import api

    monkeypatch.setattr(api, "DECISIONS_FILE", tmp_path / "decisions.jsonl")
    monkeypatch.setattr(api, "INVESTIGATIONS_FILE", tmp_path / "investigations.jsonl")
    api.state.update({"metrics": None, "index": None, "copilot": None, "investigations": {}})
    fake = SimpleNamespace(
        trace_id="t-2", provider="openai", model="m", prompt_version="p", error=None, report={"finding": "unclear", "next_test": None}
    )
    inv_id = api._store_investigation("Frage?", fake)
    api.state["investigations"] = {}  # simulate a restart
    client = TestClient(api.app)
    r = client.post("/decisions", json={"investigation_id": inv_id, "decision": "approve_test"})
    assert r.status_code == 201 and r.json()["trace_id"] == "t-2"
    assert api._load_investigations()[inv_id]["question"] == "Frage?"


def test_health_live_and_ready_semantics(monkeypatch):
    from ecu_copilot.copilot import api, tools

    class _Twin:
        def __init__(self, ok):
            self.ok = ok

        def health(self):
            if not self.ok:
                raise ConnectionError("twin down")
            return {"status": "ok"}

    api.state.update({"metrics": None, "copilot": None, "investigations": {}, "index": SimpleNamespace(ready=True)})
    client = TestClient(api.app)
    monkeypatch.setattr(tools, "_get_twin", lambda: _Twin(True))
    assert client.get("/health/live").json() == {"status": "alive"}
    assert client.get("/health/ready").status_code == 200 and client.get("/health").json()["status"] == "ok"
    monkeypatch.setattr(tools, "_get_twin", lambda: _Twin(False))
    r = client.get("/health/ready")
    assert r.status_code == 503 and r.json()["twin_reachable"] is False
    h = client.get("/health")
    assert h.status_code == 200 and h.json()["status"] == "degraded"  # compatibility: still 200, but honest
    assert client.get("/health/live").status_code == 200


def test_corrupt_investigations_file_does_not_block_restart(tmp_path, monkeypatch, capsys):
    """Review R4: a truncated last line (interrupted append) or a corrupt middle line must not raise at startup."""
    from ecu_copilot.copilot import api

    monkeypatch.setattr(api, "DECISIONS_FILE", tmp_path / "decisions.jsonl")
    monkeypatch.setattr(api, "INVESTIGATIONS_FILE", tmp_path / "investigations.jsonl")
    api.state.update({"metrics": None, "index": SimpleNamespace(ready=True), "copilot": None, "investigations": {}})
    fake = SimpleNamespace(
        trace_id="t-3", provider="openai", model="m", prompt_version="p", error=None, report={"finding": "unclear", "next_test": None}
    )
    good = api._store_investigation("gültig", fake)
    (tmp_path / "investigations.jsonl").open("a", encoding="utf-8").write('{"investigation_id": "zzz", "trunc')  # interrupted append
    loaded = api._load_investigations()
    assert good in loaded and "zzz" not in loaded and api.state["investigations_corrupt_lines"] == 1
    assert "truncated last line" in capsys.readouterr().out
    api.state["investigations"] = {}
    client = TestClient(api.app)
    assert client.post("/decisions", json={"investigation_id": good, "decision": "approve_test"}).status_code == 201
    assert client.get("/health").json()["investigations_corrupt_lines"] == 1
    # corrupt line in the middle: later records still load, warning names the line
    (tmp_path / "investigations.jsonl").write_text(
        '{"investigation_id": "a1", "question": "x"}\nnot json\n{"investigation_id": "b2", "question": "y"}\n', encoding="utf-8"
    )
    loaded = api._load_investigations()
    assert set(loaded) == {"a1", "b2"} and "corrupt line 2" in capsys.readouterr().out


def test_append_after_truncated_line_and_truncated_utf8(tmp_path, monkeypatch, capsys):
    """Review round 2: (1) a record appended after a truncated line must not be glued to the fragment;
    (2) a cut inside a multi-byte character must not raise UnicodeDecodeError at startup."""
    from ecu_copilot.copilot import api

    monkeypatch.setattr(api, "DECISIONS_FILE", tmp_path / "decisions.jsonl")
    monkeypatch.setattr(api, "INVESTIGATIONS_FILE", tmp_path / "investigations.jsonl")
    api.state.update({"metrics": None, "index": SimpleNamespace(ready=True), "copilot": None, "investigations": {}})
    fake = SimpleNamespace(
        trace_id="t-4", provider="openai", model="m", prompt_version="p", error=None, report={"finding": "unclear", "next_test": None}
    )
    # fragment cut inside the umlaut of "Prüfung" (0xC3 0xBC) -> file ends with a lone 0xC3 and no newline
    (tmp_path / "investigations.jsonl").write_bytes(b'{"investigation_id": "frag", "question": "Pr\xc3')
    loaded = api._load_investigations()  # must not raise
    assert loaded == {} and api.state["investigations_corrupt_lines"] == 1 and "truncated last line" in capsys.readouterr().out
    new_id = api._store_investigation("neu", fake)  # appended after the fragment
    loaded = api._load_investigations()
    assert new_id in loaded and loaded[new_id]["question"] == "neu", "record glued to the fragment would be lost"
    assert api.state["investigations_corrupt_lines"] == 1
    raw = (tmp_path / "investigations.jsonl").read_bytes()
    assert raw.count(b"\n") == 2 and raw.endswith(b"\n")
