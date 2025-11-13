# Ticket Verification Limits Integration for SHIOL+ Freemium System
"""
Integrated verification limits system that works with existing JWT authentication.
Implements weekly limits: Guest (1), Free (3), Premium (unlimited).
"""

import sqlite3
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from fastapi import Request
from loguru import logger

# Import existing authentication functions
from src.auth_middleware import get_user_from_request
from src.database import get_db_connection
from src.weekly_utils import get_week_start_sunday_et, get_next_reset_datetime, get_time_until_reset
from src.device_fingerprint import generate_device_fingerprint, validate_fingerprint_data


# Weekly verification limits by user type
VERIFICATION_LIMITS = {
    "guest": 1,        # Guest users: 1 verification per week
    "free_user": 3,    # Registered free users: 3 verifications per week
    "premium": -1      # Premium users: unlimited verifications
}

# IP rate limiting (abuse protection)
IP_RATE_LIMIT_PER_HOUR = 20  # Maximum verifications per IP per hour


def check_verification_access(request: Request, device_info: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Check if user can perform ticket verification based on integrated auth system.
    
    Args:
        request: FastAPI Request object
        device_info: Optional frontend device fingerprint data
        
    Returns:
        Dict with access information:
        {
            "allowed": bool,
            "remaining": int (-1 for unlimited),
            "user_type": str,
            "weekly_limit": int (-1 for unlimited), 
            "reset_time": datetime,
            "is_registered": bool,
            "error": str (if allowed=False)
        }
    """
    try:
        # 1. Get user from existing authentication system
        user = get_user_from_request(request)

        # 2. Check IP rate limiting first (abuse protection)
        ip_check = check_ip_rate_limit(request)
        if not ip_check["allowed"]:
            return ip_check

        # 3. Handle authenticated users
        if user:
            if user.get("is_premium", False):
                # Premium users: unlimited access
                return {
                    "allowed": True,
                    "remaining": -1,
                    "user_type": "premium",
                    "weekly_limit": -1,
                    "reset_time": get_next_reset_datetime(),
                    "is_registered": True,
                    "user_id": user["id"],
                    "username": user.get("username")
                }
            else:
                # Free registered users: 3 verifications per week
                return check_user_weekly_limit(user["id"], VERIFICATION_LIMITS["free_user"])

        # 4. Handle guest users (unauthenticated)
        else:
            if not device_info:
                return {
                    "allowed": False,
                    "error": "Device fingerprint required for guest access",
                    "user_type": "guest",
                    "is_registered": False
                }

            # Validate and generate device fingerprint
            try:
                validated_data = validate_fingerprint_data(device_info)
                device_fingerprint = generate_device_fingerprint(request, validated_data)
            except ValueError as e:
                return {
                    "allowed": False,
                    "error": f"Invalid device data: {str(e)}",
                    "user_type": "guest",
                    "is_registered": False
                }

            # Guest users: 1 verification per week
            return check_guest_weekly_limit(device_fingerprint, VERIFICATION_LIMITS["guest"])

    except Exception as e:
        logger.error(f"Error checking verification access: {e}")
        return {
            "allowed": False,
            "error": "System error checking access",
            "user_type": "unknown",
            "is_registered": False
        }


def check_user_weekly_limit(user_id: int, weekly_limit: int) -> Dict[str, Any]:
    """
    Check weekly verification limit for registered users.
    
    Args:
        user_id: Database user ID
        weekly_limit: Maximum verifications per week
        
    Returns:
        Access information dictionary
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            week_start = get_week_start_sunday_et()

            # Get or create weekly limit record
            cursor.execute("""
                SELECT verification_count, last_verification
                FROM weekly_verification_limits
                WHERE user_id = ? AND week_start_date = ?
            """, (user_id, week_start))

            result = cursor.fetchone()

            if result:
                verification_count, last_verification = result
            else:
                # Create new weekly record
                cursor.execute("""
                    INSERT INTO weekly_verification_limits 
                    (user_id, week_start_date, verification_count, user_type, created_at, updated_at)
                    VALUES (?, ?, 0, 'free_user', ?, ?)
                """, (user_id, week_start, datetime.now(), datetime.now()))
                conn.commit()
                verification_count = 0
                last_verification = None

            # Check if limit exceeded
            remaining = weekly_limit - verification_count

            return {
                "allowed": remaining > 0,
                "remaining": remaining,
                "user_type": "free_user",
                "weekly_limit": weekly_limit,
                "reset_time": get_next_reset_datetime(),
                "is_registered": True,
                "user_id": user_id,
                "used_this_week": verification_count,
                "last_verification": last_verification
            }

    except sqlite3.Error as e:
        logger.error(f"Database error checking user weekly limit: {e}")
        return {
            "allowed": False,
            "error": "Database error",
            "user_type": "free_user",
            "is_registered": True
        }


def check_guest_weekly_limit(device_fingerprint: str, weekly_limit: int) -> Dict[str, Any]:
    """
    Check weekly verification limit for guest users using device fingerprint.
    
    Args:
        device_fingerprint: Device fingerprint hash
        weekly_limit: Maximum verifications per week
        
    Returns:
        Access information dictionary
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            week_start = get_week_start_sunday_et()

            # Get or create weekly limit record for device
            cursor.execute("""
                SELECT verification_count, last_verification
                FROM weekly_verification_limits
                WHERE device_fingerprint = ? AND week_start_date = ?
            """, (device_fingerprint, week_start))

            result = cursor.fetchone()

            if result:
                verification_count, last_verification = result
            else:
                # Create new weekly record for device
                cursor.execute("""
                    INSERT INTO weekly_verification_limits 
                    (device_fingerprint, week_start_date, verification_count, user_type, created_at, updated_at)
                    VALUES (?, ?, 0, 'guest', ?, ?)
                """, (device_fingerprint, week_start, datetime.now(), datetime.now()))
                conn.commit()
                verification_count = 0
                last_verification = None

            # Check if limit exceeded
            remaining = weekly_limit - verification_count

            return {
                "allowed": remaining > 0,
                "remaining": remaining,
                "user_type": "guest",
                "weekly_limit": weekly_limit,
                "reset_time": get_next_reset_datetime(),
                "is_registered": False,
                "device_fingerprint": device_fingerprint[:16] + "...",  # Truncated for display
                "used_this_week": verification_count,
                "last_verification": last_verification
            }

    except sqlite3.Error as e:
        logger.error(f"Database error checking guest weekly limit: {e}")
        return {
            "allowed": False,
            "error": "Database error",
            "user_type": "guest",
            "is_registered": False
        }


def record_verification_usage(request: Request, device_info: Optional[Dict] = None) -> bool:
    """
    Record a verification usage (increment counter).
    Call this AFTER a successful verification.
    
    Args:
        request: FastAPI Request object
        device_info: Optional frontend device fingerprint data
        
    Returns:
        True if recorded successfully, False on error
    """
    from src.device_fingerprint import get_client_ip

    # Enhanced logging for troubleshooting
    client_ip = get_client_ip(request)
    logger.info(f"Recording verification usage - IP: {client_ip}, has_device_info: {device_info is not None}")

    try:
        user = get_user_from_request(request)

        if user:
            user_id = user.get("id")
            is_premium = user.get("is_premium", False)
            username = user.get("username", "unknown")

            logger.info(f"User verification recording - user_id: {user_id}, username: {username}, is_premium: {is_premium}")

            # Registered user
            if is_premium:
                # Premium users don't have limits - no need to record
                logger.info(f"Premium user {username} (ID: {user_id}) - unlimited verifications, no recording needed")
                return True
            else:
                # Free registered user
                if user_id is None:
                    logger.error(f"User ID is None for user {username}, cannot record verification")
                    return False
                logger.info(f"Recording verification for free user {username} (ID: {user_id})")
                return record_user_verification(user_id)
        else:
            # Guest user
            logger.info("Recording verification for guest user")

            if not device_info:
                logger.error("Device info required for guest verification recording")
                return False

            try:
                validated_data = validate_fingerprint_data(device_info)
                device_fingerprint = generate_device_fingerprint(request, validated_data)

                logger.info(f"Guest verification recording - fingerprint: {device_fingerprint[:16]}..., IP: {client_ip}")

                return record_guest_verification(device_fingerprint)
            except ValueError as e:
                logger.error(f"Invalid device data for verification recording: {e}")
                return False

    except Exception as e:
        logger.error(f"Error recording verification usage: {e}")
        return False


def record_user_verification(user_id: int) -> bool:
    """Record verification usage for registered user with atomic limit checking."""
    try:
        with get_db_connection() as conn:
            # Use IMMEDIATE transaction to prevent race conditions
            conn.execute("BEGIN IMMEDIATE")

            try:
                cursor = conn.cursor()
                week_start = get_week_start_sunday_et()
                now = datetime.now()

                # Get weekly limit for free registered users (5 verifications)
                weekly_limit = 5

                # Ensure weekly row exists (INSERT OR IGNORE for atomicity)
                cursor.execute("""
                    INSERT OR IGNORE INTO weekly_verification_limits 
                    (user_id, week_start_date, verification_count, user_type, created_at, updated_at)
                    VALUES (?, ?, 0, 'registered', ?, ?)
                """, (user_id, week_start, now, now))

                # Atomic check-and-increment: only update if under limit
                cursor.execute("""
                    UPDATE weekly_verification_limits
                    SET verification_count = verification_count + 1,
                        last_verification = ?,
                        updated_at = ?
                    WHERE user_id = ? AND week_start_date = ? AND verification_count < ?
                """, (now, now, user_id, week_start, weekly_limit))

                if cursor.rowcount == 0:
                    # Update failed - either limit exceeded or race condition
                    cursor.execute("""
                        SELECT verification_count
                        FROM weekly_verification_limits
                        WHERE user_id = ? AND week_start_date = ?
                    """, (user_id, week_start))

                    current_result = cursor.fetchone()
                    if current_result:
                        current = current_result[0]
                        logger.warning(f"ATOMIC LIMIT ENFORCEMENT: User {user_id} limit exceeded or race condition: {current}/{weekly_limit}")
                    else:
                        logger.error(f"ATOMIC LIMIT ENFORCEMENT: Failed to find verification record for user {user_id}")

                    conn.rollback()
                    return False

                conn.commit()
                logger.info(f"ATOMIC SUCCESS: Recorded verification for user {user_id} - limit enforced atomically")
                return True

            except Exception as e:
                conn.rollback()
                raise e

    except sqlite3.Error as e:
        logger.error(f"Database error recording user verification: {e}")
        return False


def record_guest_verification(device_fingerprint: str) -> bool:
    """Record verification usage for guest user with atomic limit checking."""
    try:
        with get_db_connection() as conn:
            # Use IMMEDIATE transaction to prevent race conditions
            conn.execute("BEGIN IMMEDIATE")

            try:
                cursor = conn.cursor()
                week_start = get_week_start_sunday_et()
                now = datetime.now()

                # Get weekly limit for guest users (3 verifications)
                weekly_limit = 3

                # Ensure weekly row exists (INSERT OR IGNORE for atomicity)
                cursor.execute("""
                    INSERT OR IGNORE INTO weekly_verification_limits 
                    (device_fingerprint, week_start_date, verification_count, user_type, created_at, updated_at)
                    VALUES (?, ?, 0, 'guest', ?, ?)
                """, (device_fingerprint, week_start, now, now))

                # Atomic check-and-increment: only update if under limit
                cursor.execute("""
                    UPDATE weekly_verification_limits
                    SET verification_count = verification_count + 1,
                        last_verification = ?,
                        updated_at = ?
                    WHERE device_fingerprint = ? AND week_start_date = ? AND verification_count < ?
                """, (now, now, device_fingerprint, week_start, weekly_limit))

                if cursor.rowcount == 0:
                    # Update failed - either limit exceeded or race condition
                    cursor.execute("""
                        SELECT verification_count
                        FROM weekly_verification_limits
                        WHERE device_fingerprint = ? AND week_start_date = ?
                    """, (device_fingerprint, week_start))

                    current_result = cursor.fetchone()
                    if current_result:
                        current = current_result[0]
                        logger.warning(f"ATOMIC LIMIT ENFORCEMENT: Device {device_fingerprint[:16]}... limit exceeded or race condition: {current}/{weekly_limit}")
                    else:
                        logger.error(f"ATOMIC LIMIT ENFORCEMENT: Failed to find verification record for device {device_fingerprint[:16]}...")

                    conn.rollback()
                    return False

                conn.commit()
                logger.info(f"ATOMIC SUCCESS: Recorded verification for guest device {device_fingerprint[:16]}... - limit enforced atomically")
                return True

            except Exception as e:
                conn.rollback()
                raise e

    except sqlite3.Error as e:
        logger.error(f"Database error recording guest verification: {e}")
        return False


def check_ip_rate_limit(request: Request) -> Dict[str, Any]:
    """
    Check IP-based rate limiting for abuse protection.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        Access information dictionary
    """
    try:
        from src.device_fingerprint import get_client_ip

        client_ip = get_client_ip(request)
        if not client_ip:
            # If we can't get IP, allow through (don't block legitimate users)
            return {"allowed": True}

        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Current hour window (truncated to hour)
            now = datetime.now()
            hour_window = now.replace(minute=0, second=0, microsecond=0)

            # Check current hour's request count
            cursor.execute("""
                SELECT request_count
                FROM ip_rate_limits
                WHERE ip_address = ? AND hour_window = ?
            """, (client_ip, hour_window))

            result = cursor.fetchone()

            if result:
                request_count = result[0]
                if request_count >= IP_RATE_LIMIT_PER_HOUR:
                    logger.warning(f"IP rate limit exceeded for {client_ip}: {request_count} requests this hour")
                    return {
                        "allowed": False,
                        "error": f"Too many requests from your IP. Limit: {IP_RATE_LIMIT_PER_HOUR} per hour",
                        "user_type": "rate_limited",
                        "is_registered": False
                    }

            # Allow request and increment counter
            cursor.execute("""
                INSERT OR REPLACE INTO ip_rate_limits (ip_address, hour_window, request_count)
                VALUES (?, ?, COALESCE((SELECT request_count FROM ip_rate_limits WHERE ip_address = ? AND hour_window = ?), 0) + 1)
            """, (client_ip, hour_window, client_ip, hour_window))

            conn.commit()
            return {"allowed": True}

    except sqlite3.Error as e:
        logger.error(f"Database error checking IP rate limit: {e}")
        # On database error, don't block requests
        return {"allowed": True}
    except Exception as e:
        logger.error(f"Error checking IP rate limit: {e}")
        return {"allowed": True}


def get_limits_info(request: Request, device_info: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Get comprehensive limits information for UI display.
    
    Args:
        request: FastAPI Request object  
        device_info: Optional frontend device fingerprint data
        
    Returns:
        Complete limits information for frontend
    """
    access_info = check_verification_access(request, device_info)

    # Add time formatting for frontend
    if "reset_time" in access_info:
        reset_time = access_info["reset_time"]
        time_until_reset = get_time_until_reset()

        access_info.update({
            "reset_time_formatted": reset_time.strftime("%A at %H:%M ET"),
            "time_until_reset_hours": int(time_until_reset.total_seconds() // 3600),
            "time_until_reset_readable": str(time_until_reset).split('.')[0],  # Remove microseconds
        })

    return access_info


if __name__ == "__main__":
    """Test the limits integration."""
    print("Ticket limits integration module loaded successfully")
    print(f"Limits configuration: {VERIFICATION_LIMITS}")
    print(f"IP rate limit: {IP_RATE_LIMIT_PER_HOUR} per hour")
