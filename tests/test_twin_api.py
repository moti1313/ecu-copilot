def test_health_and_stations(twin_client):
    assert twin_client.get("/health").json()["status"] == "ok"
    stations = twin_client.get("/stations").json()
    assert [s["station"] for s in stations] == [1, 2, 3]


def test_stats_shape(twin_client):
    body = twin_client.get("/stats", params={"minutes": 10}).json()
    assert body["window_minutes"] == 10
    keys = {"station", "variant", "tested", "failed", "failure_rate_pct", "failure_codes", "mean_board_temp_c"}
    assert all(keys <= g.keys() for g in body["groups"])


def test_fault_lifecycle(twin_client):
    r = twin_client.post("/faults", json={"type": "temperature_drift", "station": 2, "delta_c": 5})
    assert r.status_code == 201
    fid = r.json()["id"]
    assert any(f["id"] == fid for f in twin_client.get("/faults").json())
    assert twin_client.delete(f"/faults/{fid}").json() == {"cleared": 1}
    assert twin_client.delete(f"/faults/{fid}").status_code == 404


def test_fault_validation(twin_client):
    assert twin_client.post("/faults", json={"type": "temperature_drift", "station": 9}).status_code == 404
    assert twin_client.post("/faults", json={"type": "bad_lot", "fail_rate": 3}).status_code == 422


def test_results_filters(twin_client):
    rows = twin_client.get("/results", params={"station": 3, "only_failed": True, "limit": 20, "minutes": 60}).json()
    assert all(r["station"] == 3 and r["verdict"] == "fail" and r["failure_code"] for r in rows)
