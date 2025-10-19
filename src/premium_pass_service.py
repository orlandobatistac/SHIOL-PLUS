# Premium Pass Service - Token and Device Management
"""
Service for managing Premium Pass tokens, device limits, and validation.
Handles token creation, revocation, and device fingerprinting.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from loguru import logger

from src.database import get_db_connection
from src.premium_pass_config import create_premium_pass_token, decode_premium_pass_token
from src.device_fingerprint import generate_device_fingerprint, validate_fingerprint_data

# Device limit per Premium Pass
MAX_DEVICES_PER_PASS = 3

class PremiumPassError(Exception):
    """Custom exception for Premium Pass operations."""
    pass

class DeviceLimitError(PremiumPassError):
    """Exception for device limit violations."""
    pass

def create_premium_pass(email: str, stripe_subscription_id: str, user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Create new Premium Pass with token and database record.
    
    Args:
        email: User email from Stripe
        stripe_subscription_id: Stripe subscription ID
        user_id: Optional user ID if registered
        
    Returns:
        Dict with pass details and token
        
    Raises:
        PremiumPassError: If creation fails
    """
    try:
        # Generate Premium Pass token
        token_data = create_premium_pass_token(email, stripe_subscription_id, user_id)
        
        # Store in database (with duplicate check for webhook idempotency)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if Premium Pass already exists for this subscription
            cursor.execute("""
                SELECT id, pass_token, jti, email, expires_at 
                FROM premium_passes 
                WHERE stripe_subscription_id = ? AND revoked_at IS NULL
            """, (stripe_subscription_id,))
            
            existing_pass = cursor.fetchone()
            if existing_pass:
                logger.info(f"Premium Pass already exists for subscription {stripe_subscription_id}, returning existing pass")
                return {
                    "pass_id": existing_pass[0],
                    "token": existing_pass[1],
                    "jti": existing_pass[2],
                    "email": existing_pass[3],
                    "expires_at": existing_pass[4],
                    "stripe_subscription_id": stripe_subscription_id
                }
            
            # Create new Premium Pass
            cursor.execute("""
                INSERT INTO premium_passes (
                    pass_token, jti, email, stripe_subscription_id, 
                    stripe_customer_id, user_id, expires_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                token_data["token"],
                token_data["jti"],
                email,
                stripe_subscription_id,
                None,  # Will be updated when we have customer_id
                user_id,
                token_data["expires_at"],
                datetime.utcnow(),
                datetime.utcnow()
            ))
            
            pass_id = cursor.lastrowid
            conn.commit()
            
        logger.info(f"Premium Pass created: pass_id={pass_id}, email={email}, subscription={stripe_subscription_id}")
        
        return {
            "pass_id": pass_id,
            "token": token_data["token"],
            "jti": token_data["jti"],
            "email": email,
            "expires_at": token_data["expires_at"],
            "stripe_subscription_id": stripe_subscription_id
        }
        
    except sqlite3.Error as e:
        logger.error(f"Database error creating Premium Pass: {e}")
        raise PremiumPassError(f"Failed to create Premium Pass: {e}")
    except Exception as e:
        logger.error(f"Unexpected error creating Premium Pass: {e}")
        raise PremiumPassError(f"Premium Pass creation failed: {e}")

def validate_premium_pass_token(token: str, device_info: Optional[Dict] = None, request=None) -> Dict[str, Any]:
    """
    Validate Premium Pass token and check device limits.
    
    Args:
        token: Premium Pass JWT token
        device_info: Device fingerprint data
        request: FastAPI request object for fingerprinting
        
    Returns:
        Dict with validation result and pass info
        
    Raises:
        PremiumPassError: If validation fails
        DeviceLimitError: If device limit exceeded
    """
    try:
        # Decode and validate token
        payload = decode_premium_pass_token(token)
        jti = payload["jti"]
        email = payload["email"]
        
        # Check if token is revoked
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, email, revoked_at, revoked_reason, device_count, expires_at
                FROM premium_passes 
                WHERE jti = ? AND pass_token = ?
            """, (jti, token))
            
            pass_record = cursor.fetchone()
            
            if not pass_record:
                logger.warning(f"Premium Pass not found in database: jti={jti}")
                raise PremiumPassError("Invalid Premium Pass")
            
            pass_id, db_email, revoked_at, revoked_reason, device_count, expires_at = pass_record
            
            # Check if revoked
            if revoked_at:
                logger.info(f"Premium Pass revoked: jti={jti}, reason={revoked_reason}")
                raise PremiumPassError(f"Premium Pass revoked: {revoked_reason}")
            
            # Check device limits if device info provided
            if device_info and request:
                try:
                    validated_data = validate_fingerprint_data(device_info)
                    device_fingerprint = generate_device_fingerprint(request, validated_data)
                    
                    # Check/register device
                    _check_and_register_device(cursor, pass_id, device_fingerprint)
                    conn.commit()
                    
                except DeviceLimitError:
                    raise
                except Exception as e:
                    logger.warning(f"Device fingerprinting failed, allowing access: {e}")
            
        logger.info(f"Premium Pass validated successfully: email={email}, jti={jti}")
        
        return {
            "valid": True,
            "pass_id": pass_id,
            "email": email,
            "jti": jti,
            "user_id": payload.get("user_id"),
            "stripe_subscription_id": payload["stripe_subscription_id"],
            "expires_at": expires_at
        }
        
    except DeviceLimitError:
        raise
    except Exception as e:
        logger.warning(f"Premium Pass validation failed: {e}")
        raise PremiumPassError(f"Premium Pass validation failed: {e}")

def _check_and_register_device(cursor, pass_id: int, device_fingerprint: str) -> None:
    """
    Check device limit and register new device if within limit.
    
    Args:
        cursor: Database cursor
        pass_id: Premium Pass ID
        device_fingerprint: Device fingerprint hash
        
    Raises:
        DeviceLimitError: If device limit exceeded
    """
    now = datetime.utcnow()
    
    # Check if device already registered
    cursor.execute("""
        SELECT id FROM premium_pass_devices 
        WHERE pass_id = ? AND device_fingerprint = ?
    """, (pass_id, device_fingerprint))
    
    existing_device = cursor.fetchone()
    
    if existing_device:
        # Update last seen time
        cursor.execute("""
            UPDATE premium_pass_devices 
            SET last_seen_at = ? 
            WHERE pass_id = ? AND device_fingerprint = ?
        """, (now, pass_id, device_fingerprint))
        return
    
    # Check current device count
    cursor.execute("""
        SELECT COUNT(*) FROM premium_pass_devices 
        WHERE pass_id = ?
    """, (pass_id,))
    
    device_count = cursor.fetchone()[0]
    
    if device_count >= MAX_DEVICES_PER_PASS:
        logger.warning(f"Device limit exceeded for pass_id={pass_id}: {device_count}/{MAX_DEVICES_PER_PASS}")
        raise DeviceLimitError(f"Device limit exceeded. Maximum {MAX_DEVICES_PER_PASS} devices allowed per Premium Pass.")
    
    # Register new device
    cursor.execute("""
        INSERT INTO premium_pass_devices (pass_id, device_fingerprint, first_seen_at, last_seen_at)
        VALUES (?, ?, ?, ?)
    """, (pass_id, device_fingerprint, now, now))
    
    # Update device count in premium_passes
    cursor.execute("""
        UPDATE premium_passes 
        SET device_count = device_count + 1, updated_at = ?
        WHERE id = ?
    """, (now, pass_id))
    
    logger.info(f"New device registered for pass_id={pass_id}: {device_fingerprint[:16]}... ({device_count + 1}/{MAX_DEVICES_PER_PASS})")

def revoke_premium_pass(jti: str, reason: str) -> bool:
    """
    Revoke Premium Pass by JTI.
    
    Args:
        jti: JWT ID to revoke
        reason: Reason for revocation
        
    Returns:
        bool: True if revoked successfully
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE premium_passes 
                SET revoked_at = ?, revoked_reason = ?, updated_at = ?
                WHERE jti = ? AND revoked_at IS NULL
            """, (datetime.utcnow(), reason, datetime.utcnow(), jti))
            
            revoked_count = cursor.rowcount
            conn.commit()
            
            if revoked_count > 0:
                logger.info(f"Premium Pass revoked: jti={jti}, reason={reason}")
                return True
            else:
                logger.warning(f"Premium Pass not found or already revoked: jti={jti}")
                return False
                
    except sqlite3.Error as e:
        logger.error(f"Database error revoking Premium Pass: {e}")
        return False

def revoke_premium_pass_by_subscription(stripe_subscription_id: str, reason: str) -> int:
    """
    Revoke all Premium Passes for a Stripe subscription.
    
    Args:
        stripe_subscription_id: Stripe subscription ID
        reason: Reason for revocation
        
    Returns:
        int: Number of passes revoked
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE premium_passes 
                SET revoked_at = ?, revoked_reason = ?, updated_at = ?
                WHERE stripe_subscription_id = ? AND revoked_at IS NULL
            """, (datetime.utcnow(), reason, datetime.utcnow(), stripe_subscription_id))
            
            revoked_count = cursor.rowcount
            conn.commit()
            
            logger.info(f"Premium Passes revoked for subscription {stripe_subscription_id}: {revoked_count} passes, reason={reason}")
            return revoked_count
            
    except sqlite3.Error as e:
        logger.error(f"Database error revoking Premium Passes by subscription: {e}")
        return 0

def get_premium_pass_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Get active Premium Pass by email.
    
    Args:
        email: User email
        
    Returns:
        Premium Pass info or None if not found
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, pass_token, jti, email, stripe_subscription_id, 
                       user_id, expires_at, device_count, created_at
                FROM premium_passes 
                WHERE email = ? AND revoked_at IS NULL 
                ORDER BY created_at DESC LIMIT 1
            """, (email,))
            
            result = cursor.fetchone()
            
            if result:
                return {
                    "pass_id": result[0],
                    "token": result[1],
                    "jti": result[2],
                    "email": result[3],
                    "stripe_subscription_id": result[4],
                    "user_id": result[5],
                    "expires_at": result[6],
                    "device_count": result[7],
                    "created_at": result[8]
                }
            
            return None
            
    except sqlite3.Error as e:
        logger.error(f"Database error getting Premium Pass by email: {e}")
        return None