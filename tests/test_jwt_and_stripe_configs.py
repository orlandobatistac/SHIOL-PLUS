import os
from contextlib import contextmanager


@contextmanager
def envset(env: dict):
    old = {k: os.getenv(k) for k in env}
    try:
        for k, v in env.items():
            if v is None and k in os.environ:
                del os.environ[k]
            elif v is not None:
                os.environ[k] = v
        yield
    finally:
        for k, v in old.items():
            if v is None and k in os.environ:
                del os.environ[k]
            elif v is not None:
                os.environ[k] = v


def test_jwt_secret_dev_and_production():
    from src.jwt_config import get_jwt_secret
    # Reset module cache
    import importlib
    import src.jwt_config as jwtc
    jwtc._jwt_secret = None

    # Dev fallback
    with envset({"JWT_SECRET_KEY": None, "ENVIRONMENT": "development"}):
        secret = get_jwt_secret()
        assert isinstance(secret, str) and len(secret) > 10

    # Explicit secret via env
    jwtc._jwt_secret = None
    with envset({"JWT_SECRET_KEY": "abc123", "ENVIRONMENT": "production"}):
        assert get_jwt_secret() == "abc123"


def test_stripe_config_flags():
    from src.stripe_config import get_stripe_config, is_stripe_enabled, get_feature_flag_billing_enabled

    with envset({
        "ENVIRONMENT": "development",
        "STRIPE_SECRET_KEY": None,
        "STRIPE_WEBHOOK_SECRET": None,
        "STRIPE_PRICE_ID_ANNUAL": None,
        "FEATURE_BILLING_ENABLED": "true",
    }):
        cfg = get_stripe_config()
        assert cfg["environment"] == "development"
        assert is_stripe_enabled() is False  # using dev fallback key -> disabled
        assert get_feature_flag_billing_enabled() is False

    with envset({
        "ENVIRONMENT": "development",
        "STRIPE_SECRET_KEY": "sk_live_x",
        "STRIPE_WEBHOOK_SECRET": "whsec_x",
        "STRIPE_PRICE_ID_ANNUAL": "price_x",
        "FEATURE_BILLING_ENABLED": "1",
    }):
        cfg = get_stripe_config()
        assert cfg["enabled"] is True
        assert is_stripe_enabled() is True
        assert get_feature_flag_billing_enabled() is True
