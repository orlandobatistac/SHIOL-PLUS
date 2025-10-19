# Stripe Configuration for SHIOL+ Premium Billing
"""
Centralized Stripe configuration management for premium subscriptions.
Handles environment-specific settings and validation.
"""

import os
from typing import Dict, Any, Optional
from loguru import logger

def get_stripe_config() -> Dict[str, Any]:
    """
    Get Stripe configuration from environment variables.
    
    Returns:
        Dict containing Stripe configuration
        
    Raises:
        RuntimeError: If required Stripe keys are missing in production
    """
    environment = os.getenv("ENVIRONMENT", "development")
    
    # Get Stripe keys from environment
    secret_key = os.getenv("STRIPE_SECRET_KEY")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    price_id_annual = os.getenv("STRIPE_PRICE_ID_ANNUAL")
    
    # Validate required keys in production
    if environment == "production":
        missing_keys = []
        if not secret_key:
            missing_keys.append("STRIPE_SECRET_KEY")
        if not webhook_secret:
            missing_keys.append("STRIPE_WEBHOOK_SECRET")
        if not price_id_annual:
            missing_keys.append("STRIPE_PRICE_ID_ANNUAL")
            
        if missing_keys:
            logger.error(f"Missing required Stripe environment variables in production: {missing_keys}")
            raise RuntimeError(f"Required Stripe environment variables not set: {', '.join(missing_keys)}")
    
    # Development fallbacks
    if not secret_key:
        secret_key = "sk_test_DEVELOPMENT_KEY_NOT_SET"
        logger.warning("Using development fallback for STRIPE_SECRET_KEY")
    
    if not webhook_secret:
        webhook_secret = "whsec_DEVELOPMENT_WEBHOOK_SECRET_NOT_SET"
        logger.warning("Using development fallback for STRIPE_WEBHOOK_SECRET")
        
    if not price_id_annual:
        price_id_annual = "price_DEVELOPMENT_ANNUAL_PRICE_NOT_SET"
        logger.warning("Using development fallback for STRIPE_PRICE_ID_ANNUAL")
    
    config = {
        "secret_key": secret_key,
        "webhook_secret": webhook_secret,
        "price_id_annual": price_id_annual,
        "environment": environment,
        "enabled": bool(secret_key and secret_key != "sk_test_DEVELOPMENT_KEY_NOT_SET")
    }
    
    logger.info(f"Stripe configuration loaded for {environment} environment (enabled: {config['enabled']})")
    return config

def is_stripe_enabled() -> bool:
    """
    Check if Stripe integration is properly configured and enabled.
    
    Returns:
        bool: True if Stripe is enabled and configured
    """
    try:
        config = get_stripe_config()
        return config["enabled"]
    except Exception as e:
        logger.error(f"Error checking Stripe configuration: {e}")
        return False

def get_feature_flag_billing_enabled() -> bool:
    """
    Feature flag to enable/disable billing functionality.
    Can be controlled via environment variable.
    
    Returns:
        bool: True if billing should be enabled
    """
    # Check feature flag environment variable
    feature_flag = os.getenv("FEATURE_BILLING_ENABLED", "true").lower()
    billing_enabled = feature_flag in ["true", "1", "yes", "on"]
    
    # Also check if Stripe is properly configured
    stripe_enabled = is_stripe_enabled()
    
    result = billing_enabled and stripe_enabled
    
    logger.info(f"Billing feature flag: {billing_enabled}, Stripe enabled: {stripe_enabled}, Final: {result}")
    return result