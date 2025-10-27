"""
Admin endpoints for user management in system status.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from src.database import (
    get_all_users,
    get_user_by_id_admin,
    update_user_password_hash,
    delete_user_account,
    toggle_user_premium,
)
from src.auth_middleware import require_admin_access
import secrets
from loguru import logger
from src.api_auth_endpoints import hash_password_secure

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

@router.get("/users", summary="List all users", response_model=list, responses={
    200: {"description": "List of users"},
    403: {"description": "Admin required"}
})
def list_users(admin: dict = Depends(require_admin_access)):
    """
    Returns a list of all users with basic info. Admin only.
    - id: User ID
    - username: Username
    - email: Email
    - is_admin: Admin status
    - premium_until: Premium expiration
    - created_at: Account creation date
    """
    users = get_all_users()
    return users


@router.post("/users/{user_id}/reset-password", summary="Reset user password", responses={
    200: {"description": "Password reset successful"},
    404: {"description": "User not found"},
    500: {"description": "Password reset failed"}
})
def reset_user_password(user_id: int, admin: dict = Depends(require_admin_access)):
    """
    Resets the password for a user and returns a temporary password. Admin only.
    Logs the action for audit.
    """
    user = get_user_by_id_admin(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    temp_password = secrets.token_urlsafe(10)
    # IMPORTANT: Use the same secure hashing used by registration/auth
    password_hash = hash_password_secure(temp_password)
    success = update_user_password_hash(user_id, password_hash)
    if not success:
        raise HTTPException(status_code=500, detail="Password reset failed")
    logger.info(f"Admin {admin['id']} reset password for user {user_id}")
    return {"success": True, "temp_password": temp_password}


@router.delete("/users/{user_id}", summary="Delete user account", responses={
    200: {"description": "User deleted"},
    403: {"description": "Admin cannot delete own account"},
    404: {"description": "User not found"},
    500: {"description": "User deletion failed"}
})
def delete_user(user_id: int, admin: dict = Depends(require_admin_access)):
    """
    Deletes a user account. Admin only. Prevents self-deletion.
    Logs the action for audit.
    """
    if user_id == admin["id"]:
        raise HTTPException(status_code=403, detail="Admin cannot delete own account")
    user = get_user_by_id_admin(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    success = delete_user_account(user_id)
    if not success:
        raise HTTPException(status_code=500, detail="User deletion failed")
    logger.info(f"Admin {admin['id']} deleted user {user_id}")
    return {"success": True}


@router.put("/users/{user_id}/premium", summary="Toggle user premium status", responses={
    200: {"description": "Premium status toggled"},
    404: {"description": "User not found"}
})
def toggle_premium(user_id: int, admin: dict = Depends(require_admin_access)):
    """
    Toggles premium status for a user. If not premium, assigns 30 days; if premium, removes. Admin only.
    Logs the action for audit.
    """
    user = get_user_by_id_admin(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    status = toggle_user_premium(user_id)
    logger.info(f"Admin {admin['id']} toggled premium for user {user_id} to {status}")
    return {"success": True, "premium_status": status}
