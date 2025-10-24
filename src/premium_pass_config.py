# Premium Pass JWT Configuration - Separate from authentication JWT
"""
Dedicated JWT configuration for Premium Pass tokens.
Uses separate secret key to isolate premium functionality from auth system.
"""

import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from loguru import logger
import jwt

# Premium Pass JWT Algorithm
PREMIUM_PASS_ALGORITHM = "HS256"

# Premium Pass Expiration - 1 year (same as Stripe subscription)
PREMIUM_PASS_EXPIRATION_DAYS = 365

# Centralized Premium Pass Secret Management
_premium_pass_secret = None

def get_premium_pass_secret() -> str:
    """
    Get Premium Pass JWT secret with centralized management.
    
    Returns:
        str: Premium Pass JWT secret for token signing/verification
        
    Raises:
        RuntimeError: In production if PREMIUM_PASS_SECRET_KEY not set
    """
    global _premium_pass_secret

    if _premium_pass_secret is not None:
        return _premium_pass_secret

    # Try to get from environment first
    _premium_pass_secret = os.getenv("PREMIUM_PASS_SECRET_KEY")

    if _premium_pass_secret:
        logger.info("PREMIUM_PASS_SECRET_KEY loaded from environment variable")
        return _premium_pass_secret

    # Development fallback - different from auth JWT secret
    environment = os.getenv("ENVIRONMENT", "development")

    if environment == "production":
        logger.error("PREMIUM_PASS_SECRET_KEY environment variable is required in production!")
        raise RuntimeError("PREMIUM_PASS_SECRET_KEY must be set in production environment")

    # Fixed development secret for Premium Pass (different from auth)
    _premium_pass_secret = "SHIOL_PLUS_PREMIUM_PASS_DEV_SECRET_2025_STRIPE_INTEGRATION"
    logger.warning(
        "Using fixed development Premium Pass secret. "
        "Set PREMIUM_PASS_SECRET_KEY environment variable in production!"
    )

    return _premium_pass_secret

def generate_jti() -> str:
    """Generate unique JTI (JWT ID) for token revocation."""
    return str(uuid.uuid4())

def create_premium_pass_token(email: str, stripe_subscription_id: str, user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Create Premium Pass JWT token with JTI for revocation support.
    
    Args:
        email: User email from Stripe checkout
        stripe_subscription_id: Stripe subscription ID
        user_id: Optional user ID if user is registered
        
    Returns:
        Dict containing token, jti, and expiration info
    """
    jti = generate_jti()
    now = datetime.utcnow()
    expires_at = now + timedelta(days=PREMIUM_PASS_EXPIRATION_DAYS)

    payload = {
        "jti": jti,
        "email": email,
        "stripe_subscription_id": stripe_subscription_id,
        "user_id": user_id,
        "iat": now,
        "exp": expires_at,
        "type": "premium_pass"
    }

    token = jwt.encode(
        payload,
        get_premium_pass_secret(),
        algorithm=PREMIUM_PASS_ALGORITHM
    )

    return {
        "token": token,
        "jti": jti,
        "expires_at": expires_at,
        "email": email,
        "stripe_subscription_id": stripe_subscription_id
    }

def decode_premium_pass_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate Premium Pass token.
    
    Args:
        token: Premium Pass JWT token
        
    Returns:
        Dict containing token payload
        
    Raises:
        jwt.ExpiredSignatureError: Token has expired
        jwt.InvalidTokenError: Token is invalid
    """
    try:
        payload = jwt.decode(
            token,
            get_premium_pass_secret(),
            algorithms=[PREMIUM_PASS_ALGORITHM]
        )

        # Validate token type
        if payload.get("type") != "premium_pass":
            raise jwt.InvalidTokenError("Invalid token type")

        return payload

    except jwt.ExpiredSignatureError:
        logger.info("Premium Pass token has expired")
        raise
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid Premium Pass token: {e}")
        raise

def get_premium_pass_config() -> Dict[str, Any]:
    """
    Get complete Premium Pass JWT configuration.
    
    Returns:
        dict: Premium Pass configuration
    """
    return {
        "secret": get_premium_pass_secret(),
        "algorithm": PREMIUM_PASS_ALGORITHM,
        "expiration_days": PREMIUM_PASS_EXPIRATION_DAYS
    }
