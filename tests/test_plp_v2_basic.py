import os
import importlib
import time
import pytest
from fastapi.testclient import TestClient

# Ensure PLP v2 is enabled and API key is set BEFORE importing app
os.environ["PLP_API_ENABLED"] = "true"
os.environ["PREDICTLOTTOPRO_API_KEY"] = "test_key"

from src import plp_api_key as plp_keys
import src.api as api


@pytest.fixture()
def client(monkeypatch):
    # Reset in-memory rate limiter state between tests
    try:
        plp_keys._RATE_STATE.clear()  # type: ignore
    except Exception:
        pass
    # Ensure flags are set and reload app so /api/v2 is mounted
    monkeypatch.setenv("PLP_API_ENABLED", "true")
    monkeypatch.setenv("PREDICTLOTTOPRO_API_KEY", "test_key")
    importlib.reload(api)
    return TestClient(api.app)


def auth_headers(key: str = "test_key"):
    return {"Authorization": f"Bearer {key}"}


def test_health_auth_required(client: TestClient):
    r = client.get("/api/v2/health")
    # v2 middleware should wrap into standardized error JSON
    assert r.status_code == 401
    body = r.json()
    assert isinstance(body, dict)
    assert body.get("code") == 401
    assert "error" in body


def test_health_ok_and_rate_headers(client: TestClient):
    r = client.get("/api/v2/health", headers=auth_headers())
    assert r.status_code == 200
    j = r.json()
    assert j.get("status") == "ok"

    # Rate limit headers should be present
    assert "X-RateLimit-Limit" in r.headers
    assert "X-RateLimit-Remaining" in r.headers
    assert "X-RateLimit-Reset" in r.headers


def test_rate_limit_exceeded(client: TestClient, monkeypatch):
    # Set a very low RPM for test and ensure it's picked up
    monkeypatch.setenv("PLP_RATE_LIMIT_RPM", "2")

    # Perform 2 allowed calls
    for _ in range(2):
        ok = client.get("/api/v2/health", headers=auth_headers())
        assert ok.status_code == 200

    # Third call should exceed limit
    r = client.get("/api/v2/health", headers=auth_headers())
    assert r.status_code == 429
    body = r.json()
    assert body.get("code") == 429
    assert body.get("error")

    # Headers should reflect 0 remaining
    assert r.headers.get("X-RateLimit-Remaining") == "0"
