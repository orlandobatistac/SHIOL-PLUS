# JWT Configuration - CENTRALIZED for SHIOL+ Authentication System
"""
Centralized JWT configuration to ensure consistent token generation 
and verification across all modules. CRITICAL for auth functionality.
"""

import os
import secrets
from loguru import logger

# JWT Algorithm - Fixed across all modules
JWT_ALGORITHM = "HS256"

# JWT Expiration - 7 days (consistent with api_auth_endpoints.py)
JWT_EXPIRATION_DAYS = 7

# Centralized JWT Secret Management
_jwt_secret = None

def get_jwt_secret() -> str:
    """
    Get JWT secret with centralized management.
    
    Returns:
        str: JWT secret for token signing/verification
        
    Raises:
        RuntimeError: In production if JWT_SECRET_KEY not set
    """
    global _jwt_secret
    
    if _jwt_secret is not None:
        return _jwt_secret
        
    # Try to get from environment first
    _jwt_secret = os.getenv("JWT_SECRET_KEY")
    
    if _jwt_secret:
        logger.info("JWT_SECRET_KEY loaded from environment variable")
        return _jwt_secret
    
    # Development fallback - CONSISTENT across all modules
    environment = os.getenv("ENVIRONMENT", "development")
    
    if environment == "production":
        logger.error("JWT_SECRET_KEY environment variable is required in production!")
        raise RuntimeError("JWT_SECRET_KEY must be set in production environment")
    
    # Fixed development secret (not random per module)
    _jwt_secret = "SHIOL_PLUS_DEV_SECRET_2025_FIXED_FOR_CONSISTENCY"
    logger.warning(
        "Using fixed development JWT secret. "
        "Set JWT_SECRET_KEY environment variable in production!"
    )
    
    return _jwt_secret

def get_jwt_config() -> dict:
    """
    Get complete JWT configuration.
    
    Returns:
        dict: JWT configuration including secret, algorithm, and expiration
    """
    return {
        "secret": get_jwt_secret(),
        "algorithm": JWT_ALGORITHM,
        "expiration_days": JWT_EXPIRATION_DAYS
    }