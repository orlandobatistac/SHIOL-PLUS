"""
Authentication API endpoints for SHIOL+ login system.
Handles user registration, login, logout, and premium access control.
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Response, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import jwt
import secrets
import os
from loguru import logger
from passlib.context import CryptContext

from src.database import (
    create_user, authenticate_user, get_user_by_id, 
    get_user_stats, upgrade_user_to_premium
)
from src.stripe_config import get_stripe_config, get_feature_flag_billing_enabled
import stripe

# JWT Configuration - Centralized (imported from jwt_config.py)
from src.jwt_config import get_jwt_secret, JWT_ALGORITHM, JWT_EXPIRATION_DAYS
JWT_EXPIRE_HOURS = 24 * JWT_EXPIRATION_DAYS  # Use centralized expiration

# Password hashing context with bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password_secure(password: str) -> str:
    """Hash password using bcrypt."""
    return pwd_context.hash(password)

def verify_password_secure(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash."""
    return pwd_context.verify(password, hashed)

# Router setup
auth_router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
security = HTTPBearer(auto_error=False)

# =====================
# PYDANTIC MODELS
# =====================

class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=20, description="Unique username")
    password: str = Field(..., min_length=6, description="Password (minimum 6 characters)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "username": "john_doe",
                "password": "secure123"
            }
        }

class LoginRequest(BaseModel):
    login: str = Field(..., description="Email or username")
    password: str = Field(..., description="Password")
    remember_me: bool = Field(default=False, description="Keep user logged in (30 days)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "login": "user@example.com",
                "password": "secure123",
                "remember_me": False
            }
        }

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    is_premium: bool
    is_admin: bool = False
    premium_expires_at: Optional[str] = None
    created_at: str
    login_count: int
    plan_tier: str
    insights_remaining: int
    insights_total: int

class AuthResponse(BaseModel):
    success: bool
    message: str
    user: Optional[UserResponse] = None
    access_token: Optional[str] = None
    is_premium: bool = False

class StatsResponse(BaseModel):
    total_users: int
    premium_users: int
    free_users: int
    new_users_30d: int

class RegisterAndUpgradeRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=20, description="Unique username")
    password: str = Field(..., min_length=6, description="Password (minimum 6 characters)")
    success_url: str = Field(..., description="URL to redirect after successful payment")
    cancel_url: str = Field(..., description="URL to redirect if payment cancelled")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "username": "john_doe",
                "password": "secure123",
                "success_url": "https://shiol.app/payment-success",
                "cancel_url": "https://shiol.app/"
            }
        }

# =====================
# JWT HELPER FUNCTIONS
# =====================

def create_access_token(user_data: Dict[str, Any], remember_me: bool = False) -> str:
    """Create JWT access token for user."""
    if remember_me:
        expiration = datetime.utcnow() + timedelta(days=30)
    else:
        expiration = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    
    payload = {
        "user_id": user_data["id"],
        "username": user_data["username"],
        "is_premium": user_data["is_premium"],
        "is_admin": user_data.get("is_admin", False),
        "exp": expiration,
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode JWT token."""
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Invalid token")
        return None

# =====================
# USER TIER HELPER FUNCTIONS
# =====================

def get_user_tier_info(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate user tier and insights quota information with day-based limits."""
    is_premium = user_data.get("is_premium", False)
    
    # Check if premium is expired
    if is_premium and user_data.get("premium_expires_at"):
        try:
            expiry_date = datetime.fromisoformat(user_data["premium_expires_at"].replace("Z", "+00:00"))
            if expiry_date < datetime.now():
                is_premium = False
        except (ValueError, TypeError):
            is_premium = False
    
    # Determine tier and quotas
    if is_premium:
        return {
            "plan_tier": "premium",
            "insights_remaining": 100,
            "insights_total": 100,
            "is_premium_day": True,
            "next_draw_day": None
        }
    else:
        # Free tier - calculate day-based quota
        # SECURITY: Fail closed - default to 1 insight if calculation fails
        insights_for_next_draw = 1  # Secure default
        is_premium_day = False
        next_draw_day = None
        
        try:
            from src.date_utils import DateManager
            current_et = DateManager.get_current_et_time()
            next_draw_str = DateManager.calculate_next_drawing_date(reference_date=current_et)
            next_draw = datetime.strptime(next_draw_str, "%Y-%m-%d")
            next_draw_day = next_draw.strftime("%A")
            
            # Saturday is Premium Day - 5 insights
            # All other days (Tuesday, Thursday, etc.) - 1 insight
            if next_draw_day == "Saturday":
                insights_for_next_draw = 5
                is_premium_day = True
                logger.debug(f"Next draw is Saturday - Premium Day (5 insights)")
            elif next_draw_day in ("Tuesday", "Thursday", "Monday", "Wednesday", "Friday", "Sunday"):
                insights_for_next_draw = 1
                is_premium_day = False
                logger.debug(f"Next draw is {next_draw_day} - Regular Day (1 insight)")
            else:
                # Unknown day name - fail closed
                logger.warning(f"Unexpected next draw day '{next_draw_day}', defaulting to 1 insight")
                insights_for_next_draw = 1
                is_premium_day = False
                
        except Exception as e:
            # SECURITY: Fail closed - give minimum quota on error
            logger.warning(f"Error calculating next draw day for quota: {e}, failing closed to 1 insight")
            insights_for_next_draw = 1
        
        return {
            "plan_tier": "free",
            "insights_remaining": insights_for_next_draw,
            "insights_total": insights_for_next_draw,
            "is_premium_day": is_premium_day,
            "next_draw_day": next_draw_day
        }

# =====================
# AUTHENTICATION DEPENDENCIES
# =====================

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session_token: Optional[str] = Cookie(None, alias="session_token")
) -> Optional[Dict[str, Any]]:
    """Get current authenticated user from token or session."""
    token = None
    auth_source = None
    
    # Try session cookie FIRST (prioritize web session auth)
    if session_token:
        token = session_token
        auth_source = "cookie"
    # Fallback to Authorization header (for API clients)
    elif credentials:
        token = credentials.credentials
        auth_source = "header"
    
    if not token:
        return None
    
    # Verify token
    payload = verify_token(token)
    if not payload:
        return None
    
    # Get fresh user data from database
    user_data = get_user_by_id(payload["user_id"])
    if not user_data:
        return None
    
    # Debug logging to track auth source
    logger.debug(f"User authenticated via {auth_source}: {user_data.get('username', 'unknown')}")
    
    return user_data

async def require_auth(current_user: Optional[Dict[str, Any]] = Depends(get_current_user)) -> Dict[str, Any]:
    """Require authentication - raise 401 if not authenticated."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return current_user

async def require_premium(current_user: Dict[str, Any] = Depends(require_auth)) -> Dict[str, Any]:
    """Require premium access - raise 403 if not premium."""
    if not current_user.get("is_premium"):
        raise HTTPException(status_code=403, detail="Premium access required")
    return current_user

# =====================
# AUTHENTICATION ENDPOINTS
# =====================

@auth_router.post("/register", response_model=AuthResponse)
async def register_user(user_data: RegisterRequest, response: Response):
    """Register a new user account."""
    try:
        # Validate input
        if len(user_data.username.strip()) < 3:
            raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
        
        if len(user_data.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        
        # Hash password securely with bcrypt
        password_hash = hash_password_secure(user_data.password)
        # Create user
        try:
            user_id = create_user(user_data.email, user_data.username, password_hash)
        except Exception as e:
            logger.error(f"Register DB error: {e}")
            raise HTTPException(status_code=500, detail="Database error")
        
        if user_id is None:
            raise HTTPException(status_code=409, detail="Email or username already exists")
        
        # Get user data for response
        user_info = get_user_by_id(user_id)
        if not user_info:
            raise HTTPException(status_code=500, detail="Failed to retrieve user data")
        
        # Create session token
        access_token = create_access_token(user_info)
        
        # Set secure session cookie
        is_production = os.getenv("ENVIRONMENT", "development") == "production"
        response.set_cookie(
            key="session_token",
            value=access_token,
            max_age=JWT_EXPIRE_HOURS * 3600,
            httponly=True,
            secure=is_production,  # True in production with HTTPS
            samesite="strict" if is_production else "lax",
            path="/"  # Ensure consistent path with logout
        )
        
        logger.info(f"User registered successfully: {user_data.username}")
        
        # Get user tier info for response
        user_tier_info = get_user_tier_info(user_info)
        user_response_data = {**user_info, **user_tier_info}
        
        return AuthResponse(
            success=True,
            message="Account created successfully",
            user=UserResponse(**user_response_data),
            access_token=None,  # Don't return token for web session auth
            is_premium=user_info["is_premium"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

@auth_router.post("/register-and-upgrade")
async def register_and_upgrade(user_data: RegisterAndUpgradeRequest, response: Response):
    """
    Register a new user and immediately create Stripe checkout session for premium upgrade.
    This simplifies the UX by combining registration + payment in one flow.
    """
    if not get_feature_flag_billing_enabled():
        raise HTTPException(
            status_code=503,
            detail="Billing functionality is currently disabled"
        )
    
    try:
        # Step 1: Validate input (same as register endpoint)
        if len(user_data.username.strip()) < 3:
            raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
        
        if len(user_data.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        
        # Step 2: Hash password and create user
        password_hash = hash_password_secure(user_data.password)
        try:
            user_id = create_user(user_data.email, user_data.username, password_hash)
        except Exception as e:
            logger.error(f"Register-and-upgrade DB error: {e}")
            raise HTTPException(status_code=500, detail="Database error")
        
        if user_id is None:
            raise HTTPException(status_code=409, detail="Email or username already exists")
        
        # Step 3: Get user data and create session token
        user_info = get_user_by_id(user_id)
        if not user_info:
            raise HTTPException(status_code=500, detail="Failed to retrieve user data")
        
        access_token = create_access_token(user_info)
        
        # Step 4: Set secure session cookie
        is_production = os.getenv("ENVIRONMENT", "development") == "production"
        response.set_cookie(
            key="session_token",
            value=access_token,
            max_age=JWT_EXPIRE_HOURS * 3600,
            httponly=True,
            secure=is_production,
            samesite="strict" if is_production else "lax",
            path="/"
        )
        
        # Step 5: Create Stripe checkout session
        stripe_config = get_stripe_config()
        stripe.api_key = stripe_config["secret_key"]
        
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': stripe_config["price_id_annual"],
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=user_data.success_url + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=user_data.cancel_url,
                customer_email=user_info["email"],
                metadata={
                    'user_id': str(user_info["id"]),
                    'source': 'shiol_plus_register_and_upgrade'
                },
                subscription_data={
                    'metadata': {
                        'user_id': str(user_info["id"]),
                        'source': 'shiol_plus_register_and_upgrade'
                    }
                }
            )
            
            logger.info(f"User {user_data.username} registered and checkout session created: {session.id}")
            
            # Get user tier info for response
            user_tier_info = get_user_tier_info(user_info)
            user_response_data = {**user_info, **user_tier_info}
            
            return {
                "success": True,
                "message": "Account created successfully",
                "user": UserResponse(**user_response_data),
                "checkout_url": session.url,
                "session_id": session.id
            }
            
        except Exception as e:
            logger.error(f"Stripe error after registration: {e}")
            # User is already registered at this point, so return success with error message
            user_tier_info = get_user_tier_info(user_info)
            user_response_data = {**user_info, **user_tier_info}
            return {
                "success": True,
                "message": "Account created but payment setup failed. Please try upgrading from your account.",
                "user": UserResponse(**user_response_data),
                "checkout_url": None,
                "error": str(e)
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Register-and-upgrade error: {e}")
        raise HTTPException(status_code=500, detail="Registration and upgrade failed")

@auth_router.post("/login", response_model=AuthResponse)
async def login_user(login_data: LoginRequest, response: Response):
    """Authenticate user and create session."""
    try:
        # Authenticate user
        user_info = authenticate_user(login_data.login, login_data.password)
        
        if not user_info:
            raise HTTPException(status_code=401, detail="Invalid email/username or password")
        
        # Create session token with remember_me support
        access_token = create_access_token(user_info, remember_me=login_data.remember_me)
        
        # Calculate cookie max_age based on remember_me
        if login_data.remember_me:
            max_age = 30 * 24 * 3600  # 30 days
        else:
            max_age = JWT_EXPIRE_HOURS * 3600  # 7 days
        
        # Set secure session cookie
        is_production = os.getenv("ENVIRONMENT", "development") == "production"
        response.set_cookie(
            key="session_token",
            value=access_token,
            max_age=max_age,
            httponly=True,
            secure=is_production,  # True in production with HTTPS
            samesite="strict" if is_production else "lax",
            path="/"  # Ensure consistent path with logout
        )
        
        logger.info(f"User logged in: {user_info['username']} (Premium: {user_info['is_premium']}, Remember: {login_data.remember_me})")
        
        # Get user tier info for response
        user_tier_info = get_user_tier_info(user_info)
        user_response_data = {**user_info, **user_tier_info}
        
        return AuthResponse(
            success=True,
            message="Login successful",
            user=UserResponse(**user_response_data),
            access_token=None,  # Don't return token for web session auth
            is_premium=user_info["is_premium"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")

@auth_router.post("/logout")
async def logout_user(response: Response):
    """Logout user by clearing session."""
    # Determine if we're in production
    is_production = os.getenv('ENVIRONMENT', '').lower() == 'production'
    
    # Clear session cookie - only key and path needed for deletion
    response.delete_cookie(
        key="session_token",
        path="/"
    )
    
    return {"success": True, "message": "Logged out successfully"}

@auth_router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: Dict[str, Any] = Depends(require_auth)):
    """Get current authenticated user information."""
    user_tier_info = get_user_tier_info(current_user)
    user_response_data = {**current_user, **user_tier_info}
    return UserResponse(**user_response_data)

@auth_router.get("/check")
async def check_auth_status(current_user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    """Check if user is authenticated (for frontend)."""
    if current_user:
        return {
            "authenticated": True,
            "is_premium": current_user.get("is_premium", False),
            "username": current_user.get("username"),
            "user_id": current_user.get("id")
        }
    else:
        return {
            "authenticated": False,
            "is_premium": False,
            "username": None,
            "user_id": None
        }

@auth_router.get("/status")
async def get_auth_status(current_user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    """Get authentication status in format expected by AuthManager frontend."""
    if current_user:
        user_tier_info = get_user_tier_info(current_user)
        return {
            "is_authenticated": True,
            "user": {
                "id": current_user["id"],
                "email": current_user["email"],
                "username": current_user["username"],
                "is_premium": current_user["is_premium"],
                "is_admin": current_user.get("is_admin", False),
                "premium_expires_at": current_user.get("premium_expires_at"),
                "created_at": current_user["created_at"],
                "login_count": current_user["login_count"],
                "plan_tier": user_tier_info["plan_tier"],
                "insights_remaining": user_tier_info["insights_remaining"],
                "insights_total": user_tier_info["insights_total"]
            }
        }
    else:
        return {
            "is_authenticated": False,
            "user": None
        }

# =====================
# PREMIUM ACCESS ENDPOINTS
# =====================

@auth_router.post("/upgrade-premium")
async def upgrade_to_premium(current_user: Dict[str, Any] = Depends(require_auth)):
    """Upgrade current user to premium access (demo - in production integrate with payment)."""
    try:
        # For demo purposes - grant 1 year premium access
        expiry_date = datetime.now() + timedelta(days=365)
        
        success = upgrade_user_to_premium(current_user["id"], expiry_date)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to upgrade to premium")
        
        logger.info(f"User {current_user['username']} upgraded to premium")
        
        return {
            "success": True,
            "message": "Successfully upgraded to premium access for 1 year!",
            "premium_expires_at": expiry_date.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Premium upgrade error: {e}")
        raise HTTPException(status_code=500, detail="Premium upgrade failed")

# =====================
# PUBLIC STATISTICS
# =====================

@auth_router.get("/stats", response_model=StatsResponse)
async def get_platform_stats():
    """Get public platform statistics."""
    try:
        stats = get_user_stats()
        return StatsResponse(**stats)
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")

# =====================
# ADMIN ENDPOINTS (Future)
# =====================

# @auth_router.get("/admin/users")
# async def list_users(current_user: Dict[str, Any] = Depends(require_admin)):
#     """Admin endpoint to list users."""
#     pass