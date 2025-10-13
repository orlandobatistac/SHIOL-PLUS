# Authentication Middleware for SHIOL+ Freemium System
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any
import jwt
import os
from datetime import datetime
from loguru import logger
from src.database import get_user_by_id
from src.jwt_config import get_jwt_secret, JWT_ALGORITHM

# Security scheme for Bearer token
security = HTTPBearer(auto_error=False)

class AuthenticationError(Exception):
    """Custom exception for authentication errors"""
    pass

def decode_jwt_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate JWT token
    
    Returns:
        Dict containing user data if valid
    
    Raises:
        AuthenticationError if token is invalid
    """
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")

def get_user_from_request(request: Request) -> Optional[Dict[str, Any]]:
    """
    Extract user information from request (JWT token, session cookie, or Premium Pass)
    
    Args:
        request: FastAPI request object
        
    Returns:
        User dict if authenticated, None if not authenticated
    """
    try:
        # Try to get token from session cookie FIRST (prioritize web sessions)
        token = request.cookies.get("session_token")
        auth_source = "cookie"
        
        # Fallback to Authorization header (for API clients)
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]  # Remove "Bearer " prefix
                auth_source = "header"
        
        if token:
            # Process regular authentication token
            try:
                # Decode token to get user data
                payload = decode_jwt_token(token)
                user_id = payload.get("user_id")
                
                if not user_id:
                    logger.warning("Token missing user_id")
                    return None
                    
                # Get complete user data from database
                user_data = get_user_by_id(user_id)
                if not user_data:
                    logger.warning(f"User ID {user_id} not found in database")
                    return None
                    
                # Check if premium subscription is expired
                is_premium_active = user_data["is_premium"]
                if is_premium_active and user_data["premium_expires_at"]:
                    try:
                        from datetime import datetime
                        expiry_date = datetime.fromisoformat(user_data["premium_expires_at"].replace("Z", "+00:00"))
                        if expiry_date < datetime.now():
                            is_premium_active = False
                            logger.info(f"Premium subscription expired for user {user_data['id']}")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid premium_expires_at format for user {user_data['id']}: {e}")
                        is_premium_active = False
                
                # Debug logging to track auth source
                logger.debug(f"User authenticated via {auth_source}: {user_data.get('username', 'unknown')}")
                
                # Return minimal user info (no PII for public endpoints)
                return {
                    "id": user_data["id"],
                    "username": user_data["username"],
                    "email": user_data["email"],
                    "is_premium": is_premium_active,  # Use computed premium status
                    "premium_expires_at": user_data["premium_expires_at"],
                    "is_admin": user_data.get("is_admin", False),  # Include admin status
                    "auth_source": auth_source
                }
                
            except AuthenticationError as e:
                logger.warning(f"Authentication error: {e}")
                # Continue to check Premium Pass if regular auth fails
        
        # Check for Premium Pass token if no regular authentication
        premium_pass_token = request.cookies.get("premium_pass")
        if premium_pass_token:
            try:
                from src.premium_pass_service import validate_premium_pass_token
                from src.premium_pass_service import PremiumPassError
                
                # Validate Premium Pass with device info if available
                device_info = None
                # You could extract device info from headers here if needed
                
                pass_info = validate_premium_pass_token(premium_pass_token, device_info, request)
                
                if pass_info["valid"]:
                    logger.debug(f"Premium Pass authenticated: {pass_info['email']}")
                    
                    # Return Premium Pass user info
                    return {
                        "id": pass_info.get("user_id"),  # May be None for non-registered users
                        "username": None,  # Premium Pass users may not have username
                        "email": pass_info["email"],
                        "is_premium": True,  # Premium Pass = premium access
                        "premium_expires_at": pass_info["expires_at"],
                        "auth_source": "premium_pass",
                        "premium_pass_id": pass_info["pass_id"]
                    }
                    
            except (PremiumPassError, Exception) as e:
                logger.warning(f"Premium Pass validation failed: {e}")
                # Could clear invalid cookie here if needed
        
        # No valid authentication found
        return None
        
    except Exception as e:
        logger.error(f"Unexpected error in get_user_from_request: {e}")
        return None

def require_authentication(request: Request) -> Dict[str, Any]:
    """
    Dependency to require valid authentication
    
    Raises:
        HTTPException 401 if not authenticated
        
    Returns:
        User data if authenticated
    """
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please login to access this resource."
        )
    return user

def require_premium_access(request: Request) -> Dict[str, Any]:
    """
    Dependency to require premium user access
    
    Raises:
        HTTPException 401 if not authenticated
        HTTPException 403 if not premium
        
    Returns:
        Premium user data if authenticated and premium
    """
    user = require_authentication(request)
    
    if not user["is_premium"]:
        raise HTTPException(
            status_code=403,
            detail="Premium subscription required. Upgrade to access all 100 AI predictions for only $9.99/year!"
        )
    
    return user

def require_admin_access(request: Request) -> Dict[str, Any]:
    """
    Dependency to require admin user access
    
    Raises:
        HTTPException 401 if not authenticated
        HTTPException 403 if not admin
        
    Returns:
        Admin user data if authenticated and admin
    """
    user = require_authentication(request)
    
    if not user.get("is_admin", False):
        raise HTTPException(
            status_code=403,
            detail="Admin access required. This resource is restricted to administrators only."
        )
    
    return user

def check_premium_status(request: Request) -> bool:
    """
    Check if current user has premium access (non-blocking)
    
    Returns:
        True if user is premium, False otherwise
    """
    user = get_user_from_request(request)
    return user["is_premium"] if user else False

def get_user_access_level(request: Request, draw_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Get user access level and restrictions for freemium logic
    
    Args:
        request: FastAPI request object
        draw_date: Optional draw date in YYYY-MM-DD format for day-based quota
    
    Returns:
        Dict with user info and access restrictions
    """
    user = get_user_from_request(request)
    
    if not user:
        # Anonymous/guest user - most restrictive
        return {
            "authenticated": False,
            "is_premium": False,
            "max_predictions": 1,  # Only 1 prediction for guests
            "access_level": "guest",
            "user": None,
            "is_premium_day": False
        }
    elif user["is_premium"]:
        # Premium user - full access
        return {
            "authenticated": True,
            "is_premium": True,
            "max_predictions": 100,  # All predictions
            "access_level": "premium",
            "user": user,
            "is_premium_day": True  # Always premium day for premium users
        }
    else:
        # Free registered user - limited access with day-based quota
        # SECURITY: Fail closed - default to 1 insight if draw_date is missing or invalid
        max_predictions = 1  # Secure default
        is_premium_day = False
        draw_day_name = None
        
        # Calculate dynamic quota based on day of week
        if draw_date:
            try:
                from datetime import datetime
                draw_datetime = datetime.strptime(draw_date, "%Y-%m-%d")
                day_name = draw_datetime.strftime("%A")
                draw_day_name = day_name
                
                # Saturday is Premium Day - 5 insights
                # All other days (Tuesday, Thursday, etc.) - 1 insight
                if day_name == "Saturday":
                    max_predictions = 5
                    is_premium_day = True
                    logger.debug(f"Free user accessing Saturday draw - Premium Day (5 insights)")
                elif day_name in ("Tuesday", "Thursday", "Monday", "Wednesday", "Friday", "Sunday"):
                    # Explicit handling for all other days
                    max_predictions = 1
                    is_premium_day = False
                    logger.debug(f"Free user accessing {day_name} draw - Regular Day (1 insight)")
                else:
                    # Unknown day name - fail closed
                    logger.warning(f"Unexpected day name '{day_name}' for draw {draw_date}, defaulting to 1 insight")
                    max_predictions = 1
                    is_premium_day = False
            except (ValueError, ImportError, AttributeError) as e:
                # SECURITY: Fail closed - give minimum quota on error
                logger.warning(f"Error calculating day-based quota for draw_date='{draw_date}': {e}, failing closed to 1 insight")
                max_predictions = 1
        else:
            # No draw_date provided - fail closed
            logger.info("Free user quota requested without draw_date, defaulting to 1 insight (fail closed)")
            max_predictions = 1
        
        return {
            "authenticated": True,
            "is_premium": False,
            "max_predictions": max_predictions,
            "access_level": "free",
            "user": user,
            "is_premium_day": is_premium_day,
            "draw_day_name": draw_day_name
        }

def apply_freemium_restrictions(predictions: list, request: Request, draw_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Apply freemium restrictions to predictions list with day-based quota
    
    Args:
        predictions: List of prediction objects
        request: FastAPI request object
        draw_date: Optional draw date for day-based quota calculation
        
    Returns:
        Dict with restricted predictions and access info
    """
    # Extract draw_date from predictions if not provided
    if not draw_date and predictions:
        draw_date = predictions[0].get("draw_date")
    
    # Get access level with day-based quota
    access = get_user_access_level(request, draw_date)
    
    # Sort predictions by score (best first) if not already sorted
    sorted_predictions = sorted(predictions, key=lambda x: x.get("confidence_score", 0), reverse=True)
    
    # Apply access restrictions
    if access["is_premium"]:
        # Premium users get up to 100 predictions (business rule cap)
        accessible_predictions = sorted_predictions[:100]
        locked_predictions = sorted_predictions[100:] if len(sorted_predictions) > 100 else []
    else:
        # Free/guest users get limited predictions based on day
        accessible_predictions = sorted_predictions[:access["max_predictions"]]
        locked_predictions = sorted_predictions[access["max_predictions"]:]
    
    # Add rank and access info to each prediction
    for i, pred in enumerate(accessible_predictions):
        pred["rank"] = i + 1
        pred["access_type"] = "unlocked"
        pred["is_premium_only"] = False
    
    # Create secure placeholder objects for locked predictions
    # SECURITY: Never send actual prediction data to non-premium users
    secure_locked_predictions = []
    for i, pred in enumerate(locked_predictions):
        secure_placeholder = {
            "id": f"locked_{i}",  # Generate secure placeholder ID
            "rank": len(accessible_predictions) + i + 1,
            "access_type": "locked",
            "is_premium_only": True,
            # Send only placeholders - NO ACTUAL PREDICTION DATA
            "n1": "?",
            "n2": "?", 
            "n3": "?",
            "n4": "?",
            "n5": "?",
            "pb": "?",
            "prediction_date": "",
            "draw_date": pred.get("draw_date", ""),  # Safe to show target draw date
            "generator_type": "premium",
            "confidence_score": 0.0,  # Don't expose actual confidence
            "created_at": "",
            "evaluated": False,
            "matches_main": 0,
            "matches_powerball": False
        }
        secure_locked_predictions.append(secure_placeholder)
    
    return {
        "predictions": accessible_predictions + secure_locked_predictions,
        "accessible_count": len(accessible_predictions),
        "locked_count": len(secure_locked_predictions),
        "total_count": len(predictions),
        "access_info": {
            "is_premium": access["is_premium"],
            "access_level": access["access_level"],
            "max_predictions": access["max_predictions"],
            "is_premium_day": access.get("is_premium_day", False),
            "draw_day_name": access.get("draw_day_name"),
            "upgrade_message": "Upgrade to Premium for $9.99/year to unlock all 100 AI predictions!" if not access["is_premium"] else None
        },
        "user": access["user"]
    }