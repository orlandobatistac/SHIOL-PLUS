from fastapi.testclient import TestClient


def test_core_health_and_info(fastapi_app):
    client = TestClient(fastapi_app)

    r1 = client.get("/api/v1/health")
    assert r1.status_code == 200
    assert r1.json()["status"] == "ok"

    r2 = client.get("/health")
    assert r2.status_code == 200
    assert r2.json()["status"] == "ok"

    info = client.get("/api/v1/system/info").json()
    assert info["status"] == "operational"
    assert "version" in info


def test_system_stats(fastapi_app):
    client = TestClient(fastapi_app)
    stats = client.get("/api/v1/system/stats").json()
    assert "database" in stats
    assert "system" in stats
    assert "pipeline" in stats


def test_routes_debug(fastapi_app):
    client = TestClient(fastapi_app)
    r = client.get("/api/v1/debug/routes")
    assert r.status_code == 200
    data = r.json()
    assert "routes" in data
    assert any(route["path"].startswith("/api/v1") for route in data["routes"])  # sanity
