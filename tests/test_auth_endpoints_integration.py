import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(fastapi_app):
    return TestClient(fastapi_app)


def _fake_user(user_id: int = 1, premium: bool = False, admin: bool = False):
    now = datetime.utcnow().isoformat()
    return {
        "id": user_id,
        "email": "user@example.com",
        "username": "testuser",
        "is_premium": premium,
        "is_admin": admin,
        "premium_expires_at": (datetime.utcnow() + timedelta(days=365)).isoformat() if premium else None,
        "created_at": now,
        "last_login": now,
        "login_count": 1,
        "is_active": True,
    }


class DummyStripeSession:
    def __init__(self):
        self.id = "sess_123"
        self.url = "https://stripe.example/checkout/sess_123"


def test_register_success_sets_cookie_and_returns_user(client, monkeypatch):
    import src.api_auth_endpoints as auth

    # Patch DB layer functions consumed by the endpoint
    monkeypatch.setattr(auth, "create_user", lambda e, u, p: 1, raising=True)
    monkeypatch.setattr(auth, "get_user_by_id", lambda uid: _fake_user(uid, premium=False), raising=True)

    # Avoid bcrypt dependency flakiness during tests
    monkeypatch.setattr(auth, "hash_password_secure", lambda pw: "HASHED", raising=True)

    # Deterministic token generation to simplify cookie assertion
    monkeypatch.setattr(auth, "create_access_token", lambda user_data, remember_me=False: "TOK", raising=True)

    payload = {"email": "user@example.com", "username": "testuser", "password": "secretpw"}
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["user"]["username"] == "testuser"

    # Cookie must be set and HttpOnly
    set_cookie = resp.headers.get("set-cookie", "")
    assert "session_token=" in set_cookie
    assert "HttpOnly" in set_cookie


def test_register_conflict_returns_409(client, monkeypatch):
    import src.api_auth_endpoints as auth

    monkeypatch.setattr(auth, "create_user", lambda e, u, p: None, raising=True)
    monkeypatch.setattr(auth, "hash_password_secure", lambda pw: "HASHED", raising=True)

    payload = {"email": "user@example.com", "username": "dupe", "password": "secretpw"}
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


def test_login_success_with_remember_me_sets_long_cookie(client, monkeypatch):
    import src.api_auth_endpoints as auth

    monkeypatch.setattr(auth, "authenticate_user", lambda l, p: _fake_user(1, premium=True), raising=True)
    monkeypatch.setattr(auth, "create_access_token", lambda u, remember_me=False: "TOK", raising=True)

    payload = {"login": "user@example.com", "password": "pw", "remember_me": True}
    resp = client.post("/api/v1/auth/login", json=payload)
    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie", "")
    # 30 days in seconds
    assert "Max-Age=2592000" in set_cookie
    assert "session_token=" in set_cookie


def test_login_invalid_returns_401(client, monkeypatch):
    import src.api_auth_endpoints as auth
    monkeypatch.setattr(auth, "authenticate_user", lambda l, p: None, raising=True)
    resp = client.post("/api/v1/auth/login", json={"login": "nope", "password": "bad"})
    assert resp.status_code == 401


def test_me_and_check_and_status_with_header_auth(client, monkeypatch):
    import src.api_auth_endpoints as auth

    # Bypass real JWT verification by returning payload
    monkeypatch.setattr(auth, "verify_token", lambda t: {"user_id": 42}, raising=True)
    monkeypatch.setattr(auth, "get_user_by_id", lambda uid: _fake_user(uid, premium=True), raising=True)

    headers = {"Authorization": "Bearer DUMMY"}

    # /me should require auth and return user payload
    r1 = client.get("/api/v1/auth/me", headers=headers)
    assert r1.status_code == 200
    assert r1.json()["username"] == "testuser"

    # /check should show authenticated
    r2 = client.get("/api/v1/auth/check", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["authenticated"] is True
    assert r2.json()["is_premium"] is True

    # /status should include nested user info
    r3 = client.get("/api/v1/auth/status", headers=headers)
    assert r3.status_code == 200
    body = r3.json()
    assert body["is_authenticated"] is True
    assert body["user"]["username"] == "testuser"


def test_upgrade_premium_success(client, monkeypatch):
    import src.api_auth_endpoints as auth

    # Authenticate via header by patching get_current_user path
    monkeypatch.setattr(auth, "verify_token", lambda t: {"user_id": 7}, raising=True)
    monkeypatch.setattr(auth, "get_user_by_id", lambda uid: _fake_user(uid, premium=False), raising=True)
    monkeypatch.setattr(auth, "upgrade_user_to_premium", lambda uid, exp: True, raising=True)

    resp = client.post("/api/v1/auth/upgrade-premium", headers={"Authorization": "Bearer X"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "premium_expires_at" in body


def test_stats_uses_backend_result(client, monkeypatch):
    import src.api_auth_endpoints as auth
    monkeypatch.setattr(
        auth,
        "get_user_stats",
        lambda: {"total_users": 5, "premium_users": 2, "free_users": 3, "new_users_30d": 1},
        raising=True,
    )
    resp = client.get("/api/v1/auth/stats")
    assert resp.status_code == 200
    assert resp.json()["total_users"] == 5


def test_register_and_upgrade_billing_disabled_503(client, monkeypatch):
    import src.api_auth_endpoints as auth
    monkeypatch.setattr(auth, "get_feature_flag_billing_enabled", lambda: False, raising=True)

    payload = {
        "email": "user@example.com",
        "username": "testuser",
        "password": "secretpw",
        "success_url": "https://shiol.app/success",
        "cancel_url": "https://shiol.app/"
    }
    resp = client.post("/api/v1/auth/register-and-upgrade", json=payload)
    assert resp.status_code == 503


def test_register_and_upgrade_happy_path_sets_cookie_and_checkout(client, monkeypatch):
    import src.api_auth_endpoints as auth

    # Enable billing and stub functions
    monkeypatch.setattr(auth, "get_feature_flag_billing_enabled", lambda: True, raising=True)
    monkeypatch.setattr(auth, "create_user", lambda e, u, p: 11, raising=True)
    monkeypatch.setattr(auth, "get_user_by_id", lambda uid: _fake_user(uid, premium=False), raising=True)
    monkeypatch.setattr(auth, "hash_password_secure", lambda pw: "HASHED", raising=True)
    monkeypatch.setattr(auth, "create_access_token", lambda u: "TOK", raising=True)

    # Stripe stubs
    monkeypatch.setattr(auth, "get_stripe_config", lambda: {
        "secret_key": "sk_test_123",
        "price_id_annual": "price_123"
    }, raising=True)

    class _Stripe:
        class checkout:
            class Session:
                @staticmethod
                def create(**kwargs):
                    return DummyStripeSession()

    monkeypatch.setattr(auth, "stripe", _Stripe, raising=True)

    payload = {
        "email": "user@example.com",
        "username": "testuser",
        "password": "secretpw",
        "success_url": "https://shiol.app/success",
        "cancel_url": "https://shiol.app/"
    }
    resp = client.post("/api/v1/auth/register-and-upgrade", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["checkout_url"].startswith("https://stripe.example/checkout/")
    # Cookie should be set for the new session
    assert "session_token=" in resp.headers.get("set-cookie", "")
