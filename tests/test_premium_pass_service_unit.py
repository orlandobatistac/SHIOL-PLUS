import types
import sqlite3
import pytest


def test_create_and_reuse_premium_pass(monkeypatch):
    from src import premium_pass_service as pps

    # Monkeypatch token creation to deterministic values
    monkeypatch.setattr(
        pps,
        "create_premium_pass_token",
        lambda email, sub_id, user_id=None: {
            "token": "tok-abc",
            "jti": "jti-abc",
            "expires_at": "2099-01-01T00:00:00Z",
        },
        raising=True,
    )

    # Use shared DB via src.database monkeypatch from conftest
    result1 = pps.create_premium_pass("user@example.com", "sub_1")
    assert result1["token"] == "tok-abc"
    assert result1["jti"] == "jti-abc"

    # Duplicate should return existing (no new row)
    result2 = pps.create_premium_pass("user@example.com", "sub_1")
    assert result2["pass_id"] == result1["pass_id"]
    assert result2["token"] == "tok-abc"


def test_validate_limits_and_device_registration(monkeypatch):
    from src import premium_pass_service as pps

    # Seed a pass directly in DB for validation
    import src.database as db
    conn = db.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO premium_passes (pass_token, jti, email, stripe_subscription_id, user_id, expires_at)
        VALUES (?,?,?,?,?,?)
        """,
        ("tok-xyz", "jti-xyz", "pp@example.com", "sub_2", None, "2099-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()

    # Mock decode to return the same payload
    monkeypatch.setattr(
        pps,
        "decode_premium_pass_token",
        lambda token: {
            "jti": "jti-xyz",
            "email": "pp@example.com",
            "stripe_subscription_id": "sub_2",
        },
        raising=True,
    )

    # Patch fingerprint helpers to stable value
    monkeypatch.setattr(
        pps,
        "validate_fingerprint_data",
        lambda d: d or {"hw": 1},
        raising=False,
    )
    monkeypatch.setattr(
        pps,
        "generate_device_fingerprint",
        lambda request, data: "fp-123",
        raising=False,
    )

    class DummyRequest:
        headers = {}

    # First device should pass and register
    res = pps.validate_premium_pass_token(
        token="tok-xyz", device_info={"hw": 1}, request=DummyRequest()
    )
    assert res["valid"] is True
    assert res["email"] == "pp@example.com"

    # Enforce MAX_DEVICES_PER_PASS = 1 and attempt a second, different device
    monkeypatch.setattr(pps, "MAX_DEVICES_PER_PASS", 1, raising=True)
    monkeypatch.setattr(
        pps,
        "generate_device_fingerprint",
        lambda request, data: "fp-456",
        raising=False,
    )
    with pytest.raises(pps.DeviceLimitError):
        pps.validate_premium_pass_token(
            token="tok-xyz", device_info={"hw": 2}, request=DummyRequest()
        )


def test_revoke_premium_pass(monkeypatch):
    from src import premium_pass_service as pps
    import src.database as db

    # Seed a pass
    conn = db.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO premium_passes (pass_token, jti, email, expires_at) VALUES (?,?,?,?)",
        ("tok-rev", "jti-rev", "rev@example.com", "2099-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()

    assert pps.revoke_premium_pass("jti-rev", "testing") is True
    # Second revoke should return False (already revoked)
    assert pps.revoke_premium_pass("jti-rev", "testing") is False
