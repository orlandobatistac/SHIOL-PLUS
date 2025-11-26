"""
Admin endpoints for user management in system status.
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Body
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
from typing import Optional

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


@router.post("/pipeline/force-run", summary="Force manual pipeline execution (async)", responses={
    202: {"description": "Pipeline started successfully (async)"},
    403: {"description": "Admin required"},
    500: {"description": "Pipeline execution failed to start"}
})
async def force_pipeline_run(
    background_tasks: BackgroundTasks,
    retry_of: Optional[int] = Body(None),
    admin: dict = Depends(require_admin_access)
):
    """
    Force manual execution of the full pipeline in background. Admin only.

    This endpoint returns immediately (202 Accepted) and executes the pipeline
    in the background to avoid nginx timeout issues.

    Params:
    - retry_of: Optional execution_id to delete before retrying (for failed executions)

    Useful for:
    - Recovery from failed pipeline executions
    - Manual execution after missed draws
    - Testing and debugging

    Returns:
    - success: Whether pipeline started successfully
    - message: Human-readable status message
    - status: Will be 'queued' (execution happens in background)
    """
    import uuid
    from datetime import datetime

    try:
        # Delete failed execution if this is a retry
        if retry_of is not None:
            try:
                from src.database import get_db_connection
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        DELETE FROM pipeline_execution_logs
                        WHERE execution_id = ? AND status IN ('failed', 'error')
                    """, (retry_of,))
                    deleted_count = cursor.rowcount
                    conn.commit()

                    if deleted_count > 0:
                        logger.info(f"🔧 [admin] Deleted failed execution {retry_of} before retry")
                    else:
                        logger.warning(f"🔧 [admin] Could not delete execution {retry_of} (may not exist or not in failed state)")
            except Exception as e:
                logger.error(f"🔧 [admin] Error deleting failed execution {retry_of}: {e}")
                # Continue with retry even if deletion fails

        logger.info(f"🔧 [admin] Manual pipeline execution requested by admin {admin['id']} ({admin['username']})" + (f" (retry of {retry_of})" if retry_of else ""))

        # Generate execution hint for tracking
        execution_hint = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()

        # Create a simple wrapper to avoid import issues
        async def run_pipeline():
            try:
                from src.api import trigger_full_pipeline_automatically
                logger.info(f"🔧 [admin] Starting background pipeline execution (hint: {execution_hint})")
                await trigger_full_pipeline_automatically()
                logger.info(f"🔧 [admin] Background pipeline completed (hint: {execution_hint})")
            except Exception as e:
                logger.error(f"🔧 [admin] Background pipeline failed (hint: {execution_hint}): {e}")
                logger.exception("Full traceback:")

        # Schedule pipeline execution in background
        background_tasks.add_task(run_pipeline)

        logger.info(f"🔧 [admin] Pipeline queued for background execution (hint: {execution_hint})")

        # Return immediately (202 Accepted)
        return {
            "success": True,
            "message": "Pipeline started in background" + (" (retrying after deleting failed execution)" if retry_of else ""),
            "status": "queued",
            "hint": execution_hint,
            "timestamp": timestamp,
            "note": "Pipeline is executing in the background. Check logs in a few seconds."
        }
    except Exception as e:
        logger.error(f"🔧 [admin] Failed to queue pipeline execution: {e}")
        logger.exception("Full traceback:")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start pipeline: {str(e)}"
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


@router.post("/pipeline/regenerate-for-draw", summary="Regenerate predictions for specific draw", responses={
    202: {"description": "Regeneration started successfully (async)"},
    400: {"description": "Invalid draw_date format"},
    403: {"description": "Admin required"},
    500: {"description": "Regeneration failed to start"}
})
async def regenerate_predictions_for_draw(
    background_tasks: BackgroundTasks,
    draw_date: str = Body(..., description="Draw date in YYYY-MM-DD format"),
    tickets: int = Body(500, description="Number of tickets to generate"),
    admin: dict = Depends(require_admin_access)
):
    """
    Regenerate predictions for a specific draw date. Admin only.
    
    This endpoint:
    1. Deletes existing tickets for the draw_date
    2. Generates new predictions using historical data BEFORE the draw
    3. Evaluates predictions against official results (if available)
    
    Returns immediately (202 Accepted) and executes in background.
    
    Params:
    - draw_date: Target draw date in YYYY-MM-DD format (e.g., "2025-11-23")
    - tickets: Number of tickets to generate (default: 500)
    
    Returns:
    - success: Whether regeneration started successfully
    - message: Human-readable status message
    - status: Will be 'queued' (execution happens in background)
    """
    import uuid
    from datetime import datetime
    import re
    
    # Validate draw_date format
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', draw_date):
        raise HTTPException(
            status_code=400, 
            detail="Invalid draw_date format. Use YYYY-MM-DD (e.g., 2025-11-23)"
        )
    
    # Validate tickets count
    if tickets < 1 or tickets > 10000:
        raise HTTPException(
            status_code=400,
            detail="tickets must be between 1 and 10000"
        )
    
    try:
        logger.info(f"🔧 [admin] Regenerate predictions requested by admin {admin['id']} ({admin['username']}) for draw_date={draw_date}, tickets={tickets}")
        
        execution_hint = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()
        
        async def run_regeneration():
            try:
                from src.database import get_db_connection
                from src.strategy_generators import StrategyManager
                from src.prediction_evaluator import PredictionEvaluator
                
                logger.info(f"🔧 [admin] Starting regeneration (hint: {execution_hint})")
                
                # Step 1: Delete existing tickets
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM generated_tickets WHERE draw_date = ?", (draw_date,))
                    existing_count = cursor.fetchone()[0]
                    
                    if existing_count > 0:
                        cursor.execute("DELETE FROM generated_tickets WHERE draw_date = ?", (draw_date,))
                        conn.commit()
                        logger.info(f"🗑️  Deleted {existing_count} existing tickets for {draw_date}")
                
                # Step 2: Generate new predictions (using historical data BEFORE draw_date)
                logger.info(f"🎲 Generating {tickets} predictions for {draw_date}")
                manager = StrategyManager(max_date=draw_date)
                new_tickets = manager.generate_balanced_tickets(total=tickets)
                
                # Insert new tickets
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    inserted = 0
                    
                    for ticket in new_tickets:
                        wb = ticket['white_balls']
                        pb = ticket['powerball']
                        
                        # Validate ranges
                        if not all(1 <= n <= 69 for n in wb) or not (1 <= pb <= 26):
                            continue
                        
                        cursor.execute("""
                            INSERT INTO generated_tickets (
                                draw_date, strategy_used, n1, n2, n3, n4, n5, powerball, confidence_score
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            draw_date,
                            ticket['strategy'],
                            wb[0], wb[1], wb[2], wb[3], wb[4],
                            pb,
                            ticket.get('confidence', 0.5)
                        ))
                        inserted += 1
                    
                    conn.commit()
                
                logger.success(f"✅ Inserted {inserted} tickets for {draw_date}")
                
                # Step 3: Evaluate predictions (if draw exists)
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM powerball_draws WHERE draw_date = ?", (draw_date,))
                    draw_exists = cursor.fetchone()[0] > 0
                
                if draw_exists:
                    logger.info(f"📊 Evaluating predictions for {draw_date}")
                    evaluator = PredictionEvaluator()
                    result = evaluator.evaluate_predictions_for_date(draw_date)
                    logger.success(f"✅ Evaluation complete: {result.get('total_wins', 0)} wins, ${result.get('total_winnings', 0):,.2f}")
                else:
                    logger.warning(f"⏭️  Skipping evaluation (no official results for {draw_date} yet)")
                
                logger.info(f"🔧 [admin] Regeneration completed (hint: {execution_hint})")
                
            except Exception as e:
                logger.error(f"🔧 [admin] Regeneration failed (hint: {execution_hint}): {e}")
                logger.exception("Full traceback:")
        
        # Schedule regeneration in background
        background_tasks.add_task(run_regeneration)
        
        logger.info(f"🔧 [admin] Regeneration queued for background execution (hint: {execution_hint})")
        
        return {
            "success": True,
            "message": f"Regeneration started for draw {draw_date}",
            "status": "queued",
            "draw_date": draw_date,
            "tickets": tickets,
            "hint": execution_hint,
            "timestamp": timestamp,
            "note": "Regeneration is executing in the background. Check logs in a few seconds."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start regeneration: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start regeneration: {str(e)}")
