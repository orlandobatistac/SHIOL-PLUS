import uuid
from typing import Dict

import pytest
from fastapi.testclient import TestClient


def _make_client(app) -> TestClient:
    return TestClient(app)


def _unique_user() -> Dict[str, str]:
    uid = uuid.uuid4().hex[:8]
    return {
        "email": f"user_{uid}@test.com",
        "username": f"user_{uid}",
        # long unicode password to exercise pre-hash + bcrypt path
        "password": ("pässwörd-🔒-very-long" * 20),
    }


def test_register_user_success_long_password(fastapi_app):
    from src.database import get_db_connection

    client = _make_client(fastapi_app)
    payload = _unique_user()

    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 200, resp.text

    data = resp.json()
    assert data.get("success") is True
    assert data.get("user") is not None
    user = data["user"]
    assert user["email"] == payload["email"].lower()
    assert user["username"] == payload["username"]
    assert data.get("access_token") is None  # web-session cookie is used instead

    # Cookie should be set
    set_cookie = resp.headers.get("set-cookie", "")
    assert "session_token=" in set_cookie

    # Verify bcrypt stored ($2x$ prefix) in DB for the new user
    user_id = user["id"]
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM users WHERE id=?", (user_id,))
        row = cur.fetchone()
        assert row is not None
        assert isinstance(row[0], str) and row[0].startswith("$2"), "Expected bcrypt hash in DB"


def test_register_user_duplicate_conflict(fastapi_app):
    client = _make_client(fastapi_app)
    payload = _unique_user()

    # First registration OK
    resp1 = client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 200, resp1.text

    # Second registration with same email/username should conflict
    resp2 = client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 409
    data2 = resp2.json()
    assert data2.get("detail") in ("Email or username already exists", "Registration failed")
