"""
Admin endpoints for user management in system status.
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
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
import asyncio

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


@router.post("/pipeline/force-run", summary="Force manual pipeline execution", responses={
    200: {"description": "Pipeline executed successfully"},
    403: {"description": "Admin required"},
    500: {"description": "Pipeline execution failed"}
})
async def force_pipeline_run(admin: dict = Depends(require_admin_access)):
    """
    Force manual execution of the full pipeline. Admin only.

    Useful for:
    - Recovery from failed pipeline executions
    - Manual execution after missed draws
    - Testing and debugging

    Returns:
    - success: Whether pipeline started successfully
    - execution_id: Unique ID for this pipeline run
    - status: Current status of execution
    - message: Human-readable status message
    """
    try:
        logger.info(f"🔧 [admin] Manual pipeline execution requested by admin {admin['id']} ({admin['username']})")

        # Import here to avoid circular dependency
        from src.api import trigger_full_pipeline_automatically

        # Execute pipeline
        result = await trigger_full_pipeline_automatically()

        logger.info(f"🔧 [admin] Manual pipeline completed: {result.get('status')}")

        return {
            "success": True,
            "message": "Pipeline ejecutado manualmente",
            "execution_id": result.get('execution_id'),
            "status": result.get('status'),
            "steps_completed": result.get('steps_completed'),
            "result": result
        }
    except Exception as e:
        logger.error(f"🔧 [admin] Manual pipeline execution failed: {e}")
        logger.exception("Full traceback:")
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline execution failed: {str(e)}"
        )


@router.get("/pipeline/execution-logs", summary="Get pipeline execution logs", response_model=dict, responses={
    200: {"description": "Pipeline execution logs with statistics"},
    403: {"description": "Admin required"}
})
def get_pipeline_logs(
    limit: int = 20,
    status: str = None,
    start_date: str = None,
    end_date: str = None,
    admin: dict = Depends(require_admin_access)
):
    """
    Returns pipeline execution logs with optional filters. Admin only.

    Query parameters:
    - limit: Maximum number of logs to return (default: 20, max: 100)
    - status: Filter by status ('running', 'completed', 'failed', 'timeout')
    - start_date: Filter logs after this date (YYYY-MM-DD)
    - end_date: Filter logs before this date (YYYY-MM-DD)

    Returns:
    - logs: Array of execution records sorted by start_time DESC
    - statistics: Summary statistics (total runs, success rate, avg duration, etc.)
    """
    from src.database import get_pipeline_execution_logs, get_pipeline_execution_statistics

    # Enforce max limit
    if limit > 100:
        limit = 100

    # Validate status if provided
    valid_statuses = ['running', 'completed', 'failed', 'timeout']
    if status and status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )

    try:
        logs = get_pipeline_execution_logs(
            limit=limit,
            status=status,
            start_date=start_date,
            end_date=end_date
        )

        statistics = get_pipeline_execution_statistics()

        return {
            "success": True,
            "logs": logs,
            "statistics": statistics,
            "filters_applied": {
                "limit": limit,
                "status": status,
                "start_date": start_date,
                "end_date": end_date
            }
        }

    except Exception as e:
        logger.error(f"Failed to retrieve pipeline execution logs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve pipeline logs: {str(e)}"
        )

async def _run_pipeline_in_background():
    """
    Internal wrapper to run the pipeline in background.
    This ensures the HTTP response is sent before the pipeline starts.
    """
    try:
        from src.api import trigger_full_pipeline_automatically
        await trigger_full_pipeline_automatically()
    except Exception as e:
        logger.error(f"Background pipeline execution failed: {e}")

@router.post("/pipeline/trigger", summary="Trigger full pipeline run", responses={
    200: {"description": "Pipeline started"},
    403: {"description": "Admin required"},
    500: {"description": "Failed to start pipeline"}
})
async def trigger_pipeline(
    background_tasks: BackgroundTasks,
    async_run: bool = True,
    admin: dict = Depends(require_admin_access)
):
    """
    Triggers the full pipeline execution. Admin only.

    Params:
    - async_run: If True (default), returns immediately after scheduling the run.
                 If False, waits for the pipeline to finish and returns the result.

    Note: Using FastAPI BackgroundTasks to ensure response is sent before pipeline starts.
    This prevents nginx 504 Gateway Timeout errors on long-running pipelines.
    """
    try:
        # Lazy import to avoid circular import with src.api including this router
        from src.api import trigger_full_pipeline_automatically

        if async_run:
            # Use BackgroundTasks to ensure response is sent BEFORE pipeline starts
            # This prevents 504 Gateway Timeout from nginx
            background_tasks.add_task(_run_pipeline_in_background)
            logger.info(f"Admin {admin['id']} triggered pipeline (async via BackgroundTasks)")
            return {"success": True, "message": "Pipeline started", "async": True}
        else:
            # Await completion (blocks until done) - only for synchronous requests
            result = await trigger_full_pipeline_automatically()
            logger.info(f"Admin {admin['id']} triggered pipeline (sync)")
            return {"success": True, "async": False, "result": result}
    except Exception as e:
        logger.error(f"Failed to trigger pipeline: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger pipeline: {str(e)}")

