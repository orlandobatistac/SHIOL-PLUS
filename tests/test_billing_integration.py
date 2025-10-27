# Basic tests for Stripe billing integration
"""
Test suite for billing endpoints, idempotency, and webhook processing.
These tests use pytest and require the test environment to be set up.
"""

import pytest
import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from src.api import app
from src.database import get_db_connection, initialize_database
from src.premium_pass_service import create_premium_pass, revoke_premium_pass_by_subscription

# Test client fixture
@pytest.fixture(scope="module")
def client():
    """Create test client with FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture(scope="function")
def test_db():
    """Set up test database with clean state."""
    # Initialize database
    initialize_database()

    # Clean up any existing test data
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM idempotency_keys WHERE idempotency_key LIKE 'test-%'")
        cursor.execute("DELETE FROM webhook_events WHERE stripe_event_id LIKE 'evt_test_%'")
        cursor.execute("DELETE FROM premium_passes WHERE email LIKE '%@test.com'")
        conn.commit()

    yield

    # Cleanup after test
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM idempotency_keys WHERE idempotency_key LIKE 'test-%'")
        cursor.execute("DELETE FROM webhook_events WHERE stripe_event_id LIKE 'evt_test_%'")
        cursor.execute("DELETE FROM premium_passes WHERE email LIKE '%@test.com'")
        conn.commit()

def test_billing_status_disabled(client):
    """Test billing status when feature flag is disabled."""
    # Patch where the function is used (imported into the module under test)
    with patch('src.api_billing_endpoints.get_feature_flag_billing_enabled', return_value=False):
        response = client.get("/api/v1/billing/status")
        assert response.status_code == 200

        data = response.json()
        assert data["enabled"] is False
        assert "disabled" in data["message"]

def test_billing_status_enabled(client):
    """Test billing status when feature flag is enabled."""
    # Patch where the function is used (imported into the module under test)
    with patch('src.api_billing_endpoints.get_feature_flag_billing_enabled', return_value=True):
        response = client.get("/api/v1/billing/status")
        assert response.status_code == 200

        data = response.json()
        assert data["enabled"] is True
        assert data.get("is_premium") is None  # No authentication

def test_create_checkout_session_idempotency(client, test_db):
    """Test idempotency of checkout session creation."""
    idempotency_key = f"test-{uuid.uuid4()}"

    request_data = {
        "success_url": "https://test.com/success",
        "cancel_url": "https://test.com/cancel"
    }

    headers = {"Idempotency-Key": idempotency_key}

    # Mock Stripe to avoid real API calls
    # Patch where the function is used (imported into the module under test)
    with patch('src.api_billing_endpoints.get_feature_flag_billing_enabled', return_value=True), \
         patch('stripe.checkout.Session.create') as mock_stripe:

        # Configure mock response
        mock_stripe.return_value = MagicMock(
            id="cs_test_123",
            url="https://checkout.stripe.com/test"
        )

        # First request
        response1 = client.post(
            "/api/v1/billing/create-checkout-session",
            json=request_data,
            headers=headers
        )

        assert response1.status_code == 200
        data1 = response1.json()
        assert "checkout_url" in data1
        assert data1["session_id"] == "cs_test_123"

        # Second request with same idempotency key should return cached result
        response2 = client.post(
            "/api/v1/billing/create-checkout-session",
            json=request_data,
            headers=headers
        )

        assert response2.status_code == 200
        data2 = response2.json()
        assert data1 == data2

        # Stripe should only be called once due to idempotency
        assert mock_stripe.call_count == 1

def test_webhook_idempotency(client, test_db):
    """Test webhook event idempotency."""
    event_id = "evt_test_" + str(uuid.uuid4())

    # Mock webhook event
    webhook_payload = {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "customer_email": "test@test.com",
                "subscription": "sub_test_123",
                "customer": "cus_test_123"
            }
        }
    }

    # Mock Stripe webhook verification
    # Patch where the function is used (imported into the module under test)
    with patch('src.api_billing_endpoints.get_feature_flag_billing_enabled', return_value=True), \
        patch('stripe.Webhook.construct_event', return_value=webhook_payload), \
        patch('src.api_billing_endpoints.create_premium_pass') as mock_create_pass, \
        patch('stripe.Subscription.retrieve') as mock_sub_retrieve:

        mock_sub_retrieve.return_value = {
            'status': 'active',
            'current_period_start': 1700000000,
            'current_period_end': 1730000000,
            'canceled_at': None,
            'ended_at': None,
            'trial_start': None,
            'trial_end': None,
            'customer': 'cus_test_123'
        }

        mock_create_pass.return_value = {
            "pass_id": 1,
            "token": "test_token",
            "jti": "test_jti",
            "email": "test@test.com",
            "expires_at": datetime.utcnow() + timedelta(days=365)
        }

        headers = {"stripe-signature": "test_signature"}
        payload = json.dumps(webhook_payload).encode()

        # First webhook request
        response1 = client.post(
            "/api/v1/billing/webhook",
            content=payload,
            headers=headers
        )

        assert response1.status_code == 200
        assert response1.json()["status"] == "success"

        # Second webhook request with same event ID should return already_processed
        response2 = client.post(
            "/api/v1/billing/webhook",
            content=payload,
            headers=headers
        )

        assert response2.status_code == 200
        assert response2.json()["status"] == "already_processed"

        # Premium Pass should only be created once
        assert mock_create_pass.call_count == 1

def test_premium_pass_creation():
    """Test Premium Pass creation and validation."""
    email = "premium@test.com"
    subscription_id = "sub_test_premium"

    # Create Premium Pass
    pass_data = create_premium_pass(email, subscription_id)

    assert pass_data["email"] == email
    assert pass_data["stripe_subscription_id"] == subscription_id
    assert "token" in pass_data
    assert "jti" in pass_data
    assert "expires_at" in pass_data

def test_premium_pass_revocation():
    """Test Premium Pass revocation by subscription."""
    email = "revoke@test.com"
    subscription_id = "sub_test_revoke"

    # Create Premium Pass
    pass_data = create_premium_pass(email, subscription_id)

    # Revoke by subscription
    revoked_count = revoke_premium_pass_by_subscription(subscription_id, "test_cancellation")

    assert revoked_count == 1

    # Verify pass is revoked in database
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT revoked_at, revoked_reason FROM premium_passes 
            WHERE jti = ?
        """, (pass_data["jti"],))

        result = cursor.fetchone()
        assert result is not None
        assert result[0] is not None  # revoked_at
        assert result[1] == "test_cancellation"

def test_webhook_subscription_deleted(client, test_db):
    """Test webhook handling for subscription deletion."""
    subscription_id = "sub_test_delete"
    event_id = "evt_test_delete_" + str(uuid.uuid4())

    # Create Premium Pass first
    pass_data = create_premium_pass("delete@test.com", subscription_id)

    # Mock webhook event for subscription deletion
    webhook_payload = {
        "id": event_id,
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": subscription_id
            }
        }
    }

    # Patch where the function is used (imported into the module under test)
    with patch('src.api_billing_endpoints.get_feature_flag_billing_enabled', return_value=True), \
         patch('stripe.Webhook.construct_event', return_value=webhook_payload):

        headers = {"stripe-signature": "test_signature"}
        payload = json.dumps(webhook_payload).encode()

        response = client.post(
            "/api/v1/billing/webhook",
            content=payload,
            headers=headers
        )

        assert response.status_code == 200

        # Verify Premium Pass was revoked
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT revoked_at, revoked_reason FROM premium_passes 
                WHERE jti = ?
            """, (pass_data["jti"],))

            result = cursor.fetchone()
            assert result is not None
            assert result[0] is not None  # revoked_at
            assert "subscription_canceled" in result[1]

if __name__ == "__main__":
    # Run tests with: python -m pytest tests/test_billing_integration.py -v
    pytest.main([__file__, "-v"])
