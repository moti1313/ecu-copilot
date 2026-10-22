"""Optional API keys (review: no access control). Off by default; when set, paid and state-changing endpoints need X-API-Key."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from ecu_copilot import config


def _copilot_client(tmp_path, monkeypatch):
    from ecu_copilot.copilot import api

    monkeypatch.setattr(api, "DECISIONS_FILE", tmp_path / "decisions.jsonl")
    monkeypatch.setattr(api, "INVESTIGATIONS_FILE", tmp_path / "investigations.jsonl")
    api.state.update({"metrics": None, "copilot": None, "investigations": {}, "index": SimpleNamespace(ready=True)})
    return api, TestClient(api.app)


def test_copilot_without_key_is_open(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ECU_API_KEY", "")
    api, client = _copilot_client(tmp_path, monkeypatch)
    assert client.post("/decisions", json={"investigation_id": "deadbeefdeadbeef", "decision": "reject"}).status_code == 404
    assert client.get("/config").json()["auth_required"] is False


def test_copilot_with_key_requires_header_on_writes_only(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ECU_API_KEY", "s3cret")
    api, client = _copilot_client(tmp_path, monkeypatch)
    body = {"investigation_id": "deadbeefdeadbeef", "decision": "reject"}
    assert client.post("/decisions", json=body).status_code == 401
    assert client.post("/decisions", json=body, headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.post("/decisions", json=body, headers={"X-API-Key": "s3cret"}).status_code == 404  # auth ok, id unknown
    assert client.post("/ask", json={"question": "x"}).status_code == 401
    assert client.get("/decisions").status_code == 200 and client.get("/health").status_code == 200  # reads stay open
    assert client.get("/config").json()["auth_required"] is True


def test_twin_key_protects_faults_and_reset(twin_client, monkeypatch):
    monkeypatch.setattr(config, "TWIN_API_KEY", "twin-key")
    fault = {"type": "temperature_drift", "station": 2}
    assert twin_client.post("/faults", json=fault).status_code == 401
    assert twin_client.post("/reset").status_code == 401
    assert twin_client.get("/faults").status_code == 200  # reads stay open
    r = twin_client.post("/faults", json=fault, headers={"X-API-Key": "twin-key"})
    assert r.status_code == 201
    assert twin_client.delete("/faults", headers={"X-API-Key": "twin-key"}).status_code in (200, 204)
    monkeypatch.setattr(config, "TWIN_API_KEY", "")
    assert twin_client.post("/faults", json=fault).status_code == 201  # off again
    twin_client.delete("/faults")


def test_twin_client_sends_key_when_configured(monkeypatch):
    from ecu_copilot.copilot.twin_client import TwinClient

    monkeypatch.setattr(config, "TWIN_API_KEY", "twin-key")
    assert TwinClient(base_url="http://twin.test")._client.headers.get("x-api-key") == "twin-key"
    monkeypatch.setattr(config, "TWIN_API_KEY", "")
    assert "x-api-key" not in TwinClient(base_url="http://twin.test")._client.headers
