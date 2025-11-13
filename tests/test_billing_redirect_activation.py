import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from src.api import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_activate_via_redirect_sets_cookie_and_redirects(client):
    session_id = "cs_test_e2e_123"

    # Mock a paid & complete session from Stripe
    mock_session = MagicMock()
    mock_session.payment_status = "paid"
    mock_session.status = "complete"
    mock_session.subscription = "sub_test_123"
    mock_session.customer = "cus_test_123"
    # Provide customer email via customer_details as in real responses
    mock_session.customer_details = MagicMock()
    mock_session.customer_details.email = "e2e@test.com"
    mock_session.customer_email = "e2e@test.com"
    mock_session.metadata = {"user_id": None}

    # Mock subscription retrieve used for FK upserts
    mock_subscription = MagicMock()
    mock_subscription.status = "active"
    mock_subscription.current_period_start = 1700000000
    mock_subscription.current_period_end = 1730000000
    mock_subscription.canceled_at = None
    mock_subscription.ended_at = None
    mock_subscription.trial_start = None
    mock_subscription.trial_end = None
    mock_subscription.customer = "cus_test_123"

    with patch("src.api_billing_endpoints.get_feature_flag_billing_enabled", return_value=True), \
        patch("stripe.checkout.Session.retrieve", return_value=mock_session), \
        patch("stripe.Subscription.retrieve", return_value=mock_subscription):

        # Call redirect activation endpoint; do not follow redirect to capture 303 and cookies
        resp = client.get(
            f"/api/v1/billing/activate-via-redirect?session_id={session_id}&next=/payment-success",
            follow_redirects=False,
        )

        assert resp.status_code == 303
        # Should redirect to provided 'next'
        assert resp.headers.get("location") == "/payment-success"

        # Cookie should be set in headers
        set_cookie = resp.headers.get("set-cookie", "")
        assert "premium_pass=" in set_cookie
