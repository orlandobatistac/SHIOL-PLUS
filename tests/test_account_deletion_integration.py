import uuid
from fastapi.testclient import TestClient

from src.api import app


def test_delete_account_happy_path():
    client = TestClient(app)

    # Unique credentials per run
    unique = uuid.uuid4().hex[:8]
    email = f"user_{unique}@example.com"
    username = f"user_{unique}"
    password = "StrongPassw0rd!"

    # Register
    r = client.post("/api/v1/auth/register", json={
        "email": email,
        "username": username,
        "password": password,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("success") is True

    # Verify session is active
    s = client.get("/api/v1/auth/status")
    assert s.status_code == 200
    assert s.json().get("is_authenticated") is True

    # Delete account
    d = client.request("DELETE", "/api/v1/auth/user/account", json={"password": password})
    assert d.status_code == 200, d.text
    assert d.json().get("success") is True

    # Session cookie should be cleared -> not authenticated
    s2 = client.get("/api/v1/auth/status")
    assert s2.status_code == 200
    assert s2.json().get("is_authenticated") is False

    # Login should fail now
    r2 = client.post("/api/v1/auth/login", json={
        "login": email,
        "password": password,
        "remember_me": False,
    })
    assert r2.status_code == 401
