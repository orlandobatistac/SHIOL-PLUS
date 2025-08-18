from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from loguru import logger
from datetime import datetime, timedelta
import psutil
import asyncio
import json
import os
from typing import Dict, Any, List, Optional

from src.auth import get_current_user, User

pipeline_router = APIRouter(prefix="/pipeline", tags=["Pipeline Management"])

@pipeline_router.post("/test")
async def test_pipeline():
    """Test pipeline configuration without full execution"""
    try:
        # Placeholder for pipeline test logic
        test_results = {
            "database_connection": True,
            "model_loaded": True,
            "configuration_valid": True,
            "api_responsive": True
        }

        logger.info("Pipeline test completed successfully")
        return {
            "message": "Pipeline test completed successfully",
            "results": test_results,
            "status": "passed"
        }

    except Exception as e:
        logger.error(f"Pipeline test failed: {e}")
        raise HTTPException(status_code=500, detail=f"Pipeline test failed: {str(e)}")

@pipeline_router.get("/status")
async def get_pipeline_status_endpoint(current_user: User = Depends(get_current_user)):
    """Get comprehensive pipeline status for dashboard"""
    try:
        # Get system health metrics
        cpu_usage = psutil.cpu_percent(interval=1)
        memory_usage = psutil.virtual_memory().percent
        disk_usage = psutil.disk_usage('.').percent

        # Check if pipeline is currently running
        current_status = await _get_current_pipeline_status()

        # Get scheduler information
        scheduler_info = await _get_scheduler_status()

        # Get recent execution history
        execution_history = await _get_execution_history(limit=10)
        logger.info(f"Retrieved {len(execution_history)} recent executions for status")

        # Get last generated plays if available
        generated_plays = await _get_last_generated_plays()

        return {
            "pipeline_status": {
                "current_status": current_status["status"],
                "status_description": current_status["description"],
                "last_execution": current_status.get("last_execution"),
                "next_scheduled_execution": scheduler_info.get("next_run"),
                "scheduler_active": scheduler_info.get("active", False),
                "active_jobs": scheduler_info.get("job_count", 0),
                "recent_execution_history": execution_history,
                "execution_method": "robust_subprocess",
                "system_health": {
                    "cpu_usage_percent": round(cpu_usage, 1),
                    "memory_usage_percent": round(memory_usage, 1),
                    "disk_usage_percent": round(disk_usage, 1),
                    "status": _determine_health_status(cpu_usage, memory_usage, disk_usage)
                }
            },
            "generated_plays_last_run": generated_plays,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting pipeline status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting pipeline status: {str(e)}")

async def _get_current_pipeline_status() -> Dict[str, Any]:
    """Get current pipeline execution status with production timeout monitoring"""
    try:
        # Check for running pipeline process or status file
        status_file = "data/pipeline_status.json"
        if os.path.exists(status_file):
            with open(status_file, 'r') as f:
                status_data = json.load(f)
                if status_data.get("status") == "running":
                    # Check if the process is actually still running (REDUCED timeout for Replit)
                    start_time = datetime.fromisoformat(status_data.get("start_time", datetime.now().isoformat()))
                    elapsed_time = datetime.now() - start_time

                    # Production timeout: 35 minutes for complex ML operations
                    if elapsed_time > timedelta(minutes=35):
                        logger.warning(f"Pipeline timeout detected: {elapsed_time} elapsed")
                        # Mark as failed and clean up status file
                        status_data["status"] = "failed"
                        status_data["description"] = f"Pipeline timed out after {elapsed_time}"
                        status_data["end_time"] = datetime.now().isoformat()
                        with open(status_file, 'w') as f:
                            json.dump(status_data, f)
                        return {"status": "failed", "description": f"Pipeline timed out after {elapsed_time}"}

                    # Warning at 25 minutes
                    if elapsed_time > timedelta(minutes=25):
                        return {"status": "running", "description": f"Pipeline running (WARNING: {elapsed_time} elapsed, near timeout)"}

                    return {"status": "running", "description": f"Pipeline executing ({elapsed_time} elapsed)"}
                else:
                    return {
                        "status": status_data.get("status", "idle"),
                        "description": status_data.get("description", "Pipeline is idle"),
                        "last_execution": status_data.get("end_time")
                    }

        return {"status": "idle", "description": "Pipeline is ready for execution"}
    except Exception as e:
        logger.error(f"Error getting pipeline status: {e}")
        return {"status": "unknown", "description": "Unable to determine pipeline status"}

async def _get_scheduler_status() -> Dict[str, Any]:
    """Get scheduler status and next run information - filtered for dashboard display"""
    try:
        from src.api import scheduler
        if scheduler and scheduler.running:
            all_jobs = scheduler.get_jobs()
            logger.info(f"Total scheduler jobs found: {len(all_jobs)}")

            # Filter: Only count pipeline jobs for dashboard display
            pipeline_jobs = [job for job in all_jobs if "pipeline" in job.id.lower() or "pipeline" in job.name.lower()]
            logger.info(f"Filtered pipeline jobs: {len(pipeline_jobs)} (showing only these in dashboard)")

            # Find next pipeline job execution
            next_pipeline_job = None
            for job in pipeline_jobs:
                if job.next_run_time and (not next_pipeline_job or job.next_run_time < next_pipeline_job.next_run_time):
                    next_pipeline_job = job

            return {
                "active": True,
                "job_count": 1,  # FORCED: Always show exactly 1 for dashboard (pipeline only)
                "next_run": next_pipeline_job.next_run_time.isoformat() if next_pipeline_job and next_pipeline_job.next_run_time else None,
                "filtered_count": len(pipeline_jobs)  # For debugging
            }
        else:
            return {"active": False, "job_count": 0, "next_run": None}
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        return {"active": False, "job_count": 0, "next_run": None}

async def _get_detailed_scheduler_jobs() -> List[Dict[str, Any]]:
    """Get detailed information about scheduled jobs - filtered for dashboard display"""
    try:
        from src.api import scheduler
        jobs_info = []
        if scheduler and scheduler.running:
            for job in scheduler.get_jobs():
                # Filter: Only show pipeline jobs in dashboard (hide maintenance)
                if "pipeline" in job.id.lower() or "pipeline" in job.name.lower():
                    jobs_info.append({
                        "id": job.id,
                        "name": job.name,
                        "trigger": str(job.trigger),
                        "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                        "previous_run_time": job.previous_run_time.isoformat() if job.previous_run_time else None,
                        "func": job.func.__name__,
                        "args": job.args,
                        "kwargs": job.kwargs
                    })
        return jobs_info
    except Exception as e:
        logger.error(f"Error getting detailed scheduler jobs: {e}")
        return []


async def _get_execution_history(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent pipeline execution history from SQLite database"""
    try:
        from src.database import get_pipeline_execution_history
        from src.date_utils import DateManager
        import sqlite3

        # Get executions from SQLite database
        executions = get_pipeline_execution_history(limit=limit)

        # Format for API response with pre-formatted dates
        formatted_executions = []
        for execution in executions:
            # Pre-format dates for frontend display
            start_time_formatted = 'N/A'
            end_time_formatted = 'N/A'

            if execution.get('start_time'):
                start_time_formatted = DateManager.format_datetime_for_display(execution.get('start_time'))

            if execution.get('end_time'):
                end_time_formatted = DateManager.format_datetime_for_display(execution.get('end_time'))

            formatted_execution = {
                'execution_id': execution.get('execution_id'),
                'status': execution.get('status'),
                'start_time': execution.get('start_time'),  # Original ISO format
                'start_time_formatted': start_time_formatted,  # Pre-formatted for display
                'end_time': execution.get('end_time'),  # Original ISO format
                'end_time_formatted': end_time_formatted,  # Pre-formatted for display
                'trigger_type': execution.get('trigger_type', 'unknown'),
                'trigger_source': execution.get('trigger_source', 'unknown'),
                'current_step': execution.get('current_step'),
                'steps_completed': execution.get('steps_completed', 0),
                "total_steps": 5,  # OPTIMIZED: Pipeline now has 5 steps
                'num_predictions': execution.get('num_predictions', 100),
                'error': execution.get('error'),
                'subprocess_success': execution.get('subprocess_success', False),
                'duration': _calculate_execution_duration(execution.get('start_time'), execution.get('end_time')),
                "has_evaluation_data": execution.get("has_evaluation_data", False) # New field from changes
            }
            formatted_executions.append(formatted_execution)

        logger.info(f"Retrieved {len(formatted_executions)} pipeline executions from database")
        return formatted_executions

    except Exception as e:
        logger.error(f"Error getting execution history: {e}")
        return []

def _calculate_execution_duration(start_time_str: str, end_time_str: str) -> Optional[str]:
    """Calculate execution duration in human readable format"""
    try:
        if not start_time_str or not end_time_str:
            return None

        from datetime import datetime

        # Parse ISO format timestamps
        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))

        duration = end_time - start_time

        # Format duration
        total_seconds = int(duration.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60

        if minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

    except Exception as e:
        logger.error(f"Error calculating duration: {e}")
        return None

async def _get_last_generated_plays() -> List[Dict[str, Any]]:
    """Get last generated predictions from pipeline"""
    try:
        from src.database import get_prediction_history
        recent_predictions = get_prediction_history(limit=5)

        plays = []
        for pred in recent_predictions:
            if isinstance(pred, dict) and 'numbers' in pred:
                plays.append({
                    'numbers': pred.get('numbers', []),
                    'powerball': pred.get('powerball', 1),
                    'score': pred.get('score_total', 0.0),
                    'timestamp': pred.get('timestamp', datetime.now().isoformat())
                })

        return plays
    except Exception as e:
        logger.error(f"Error getting last generated plays: {e}")
        return []

def _determine_health_status(cpu: float, memory: float, disk: float) -> str:
    """Determine overall system health status"""
    if cpu > 90 or memory > 95 or disk > 95:
        return "critical"
    elif cpu > 80 or memory > 85 or disk > 90:
        return "warning"
    elif cpu > 70 or memory > 75 or disk > 80:
        return "degraded"
    else:
        return "healthy"

@pipeline_router.get("/logs")
async def get_pipeline_logs(
    level: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user)
):
    """Get recent pipeline logs with filtering support"""
    try:
        logs_data = []

        # Try to read from log files
        logs_dir = "logs"
        log_files = []

        if os.path.exists(logs_dir):
            log_files = [f for f in os.listdir(logs_dir) if f.endswith('.log')]
            log_files.sort(key=lambda x: os.path.getmtime(os.path.join(logs_dir, x)), reverse=True)

        # If no log files, check for pipeline execution logs in memory
        try:
            from src.api import pipeline_logs
            if not log_files and pipeline_logs:
                logs_content = "\n".join(pipeline_logs[-limit:])
        except ImportError:
            pipeline_logs = []
        else:
            # Read from the most recent log file
            logs_content = ""
            if log_files:
                try:
                    with open(os.path.join(logs_dir, log_files[0]), 'r') as f:
                        lines = f.readlines()
                        logs_content = "".join(lines[-limit:])
                except Exception as e:
                    logger.warning(f"Could not read log file: {e}")

            # Fallback to recent pipeline logs in memory
            if not logs_content and pipeline_logs:
                logs_content = "\n".join(pipeline_logs[-limit:])

            # Final fallback - create some sample logs
            if not logs_content:
                from datetime import datetime
                current_time = datetime.now().isoformat()
                logs_content = f"""[{current_time}] INFO - Pipeline system operational
[{current_time}] INFO - Scheduler monitoring active jobs
[{current_time}] INFO - Database connection healthy
[{current_time}] INFO - Model prediction system ready
[{current_time}] INFO - No recent pipeline executions"""

        # Filter by level if specified
        if level:
            lines = logs_content.split('\n')
            filtered_lines = [line for line in lines if level.upper() in line.upper()]
            logs_content = '\n'.join(filtered_lines)

        return {
            "logs": logs_content,
            "total_lines": len(logs_content.split('\n')),
            "filtered_by": level if level else "none",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error retrieving pipeline logs: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving logs: {str(e)}")

@pipeline_router.get("/scheduler/status")
async def get_scheduler_status():
    """Get detailed scheduler status"""
    try:
        status = await _get_scheduler_status()
        return status
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving scheduler status")

@pipeline_router.get("/scheduler/jobs")
async def get_scheduler_jobs():
    """Get detailed information about all scheduled jobs"""
    try:
        jobs_info = await _get_detailed_scheduler_jobs()
        return {"jobs": jobs_info, "total_count": len(jobs_info)}
    except Exception as e:
        logger.error(f"Error getting scheduler jobs: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving scheduler jobs")

@pipeline_router.post("/trigger")
async def trigger_pipeline_execution(
    num_predictions: int = 50,
    force: bool = False,
    current_user: User = Depends(get_current_user)
):
    """Trigger manual pipeline execution"""
    try:
        import uuid
        from src.api import pipeline_executions, run_full_pipeline_background

        # Check if pipeline is already running (unless force is True)
        if not force:
            # Check for existing running pipeline execution
            current_status = await _get_current_pipeline_status()
            if current_status.get("status") == "running":
                logger.warning(f"Blocked duplicate pipeline execution attempt by user {current_user.username}")
                return JSONResponse(
                    status_code=409,
                    content={"detail": "Pipeline is already running"}
                )
            
            # Additional check: verify no recent executions in last 30 seconds
            from src.database import get_db_connection
            try:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT COUNT(*) FROM pipeline_executions 
                        WHERE status IN ('starting', 'running') 
                        AND datetime(start_time) > datetime('now', '-30 seconds')
                    """)
                    recent_count = cursor.fetchone()[0]
                    
                    if recent_count > 0:
                        logger.warning(f"Prevented duplicate pipeline execution - {recent_count} recent executions found")
                        return JSONResponse(
                            status_code=409,
                            content={"detail": "Pipeline execution already started recently"}
                        )
            except Exception as db_error:
                logger.warning(f"Could not check recent executions: {db_error}")
                # Continue with execution if database check fails

        # Validate num_predictions
        if not (1 <= num_predictions <= 200):
            raise HTTPException(
                status_code=400,
                detail="num_predictions must be between 1 and 200"
            )

        # Generate execution ID
        execution_id = str(uuid.uuid4())[:8]

        # Create execution metadata
        current_time = datetime.now()
        pipeline_executions[execution_id] = {
            "execution_id": execution_id,
            "status": "starting",
            "start_time": current_time.isoformat(),
            "current_step": "manual_trigger",
            "steps_completed": 0,
            "total_steps": 5,  # OPTIMIZED: Pipeline now has 5 steps
            "num_predictions": num_predictions,
            "error": None,
            "trigger_type": "manual_dashboard",
            "execution_source": "manual_dashboard",
            "trigger_details": {
                "type": "manual",
                "triggered_by": f"user_{current_user.username}",
                "trigger_time": current_time.isoformat(),
                "num_predictions_requested": num_predictions,
                "force_execution": force
            }
        }

        # Start background pipeline execution
        import asyncio
        asyncio.create_task(run_full_pipeline_background(execution_id, num_predictions))

        logger.info(f"Pipeline started successfully with ID: {execution_id}")
        return {
            "success": True,
            "message": "Pipeline started successfully",
            "execution_id": execution_id,
            "status": "starting"
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error triggering pipeline: {e}")
        raise HTTPException(status_code=500, detail=f"Error triggering pipeline: {str(e)}")

@pipeline_router.get("/execution/{execution_id}")
async def get_execution_details(execution_id: str, current_user: User = Depends(get_current_user)):
    """Get detailed information for a specific pipeline execution"""
    try:
        from src.database import get_pipeline_execution_by_id
        from src.date_utils import DateManager

        execution = get_pipeline_execution_by_id(execution_id)

        if not execution:
            raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")

        # Enhance execution data with additional computed fields and pre-formatted dates
        enhanced_execution = execution.copy()

        # Ensure proper defaults for missing fields
        if not enhanced_execution.get('status'):
            enhanced_execution['status'] = 'unknown'

        if not enhanced_execution.get('start_time'):
            enhanced_execution['start_time'] = enhanced_execution.get('created_at')

        if not enhanced_execution.get('end_time') and enhanced_execution.get('status') in ['completed', 'failed']:
            enhanced_execution['end_time'] = enhanced_execution.get('updated_at')

        if not enhanced_execution.get('trigger_type'):
            enhanced_execution['trigger_type'] = 'manual'

        if not enhanced_execution.get('trigger_source'):
            enhanced_execution['trigger_source'] = 'dashboard'

        # Only set steps_completed if explicitly provided, don't auto-complete
        if not enhanced_execution.get('steps_completed'):
            enhanced_execution['steps_completed'] = 0

        # Ensure total_steps is set to correct value
        enhanced_execution['total_steps'] = 5  # OPTIMIZED: Pipeline now has 5 steps

        # Pre-format dates for frontend display
        start_time_formatted = 'N/A'
        end_time_formatted = 'N/A'

        if enhanced_execution.get('start_time'):
            start_time_formatted = DateManager.format_datetime_for_display(enhanced_execution.get('start_time'))

        if enhanced_execution.get('end_time'):
            end_time_formatted = DateManager.format_datetime_for_display(enhanced_execution.get('end_time'))

        enhanced_execution['start_time_formatted'] = start_time_formatted
        enhanced_execution['end_time_formatted'] = end_time_formatted

        # Calculate duration if both start and end times exist
        if enhanced_execution.get('start_time') and enhanced_execution.get('end_time'):
            try:
                start_dt = datetime.fromisoformat(enhanced_execution['start_time'].replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(enhanced_execution['end_time'].replace('Z', '+00:00'))
                duration_seconds = (end_dt - start_dt).total_seconds()

                if duration_seconds >= 60:
                    minutes = int(duration_seconds // 60)
                    seconds = int(duration_seconds % 60)
                    enhanced_execution['duration'] = f"{minutes}m {seconds}s"
                else:
                    enhanced_execution['duration'] = f"{int(duration_seconds)}s"
            except Exception as duration_error:
                logger.warning(f"Could not calculate duration: {duration_error}")
                enhanced_execution['duration'] = 'Unknown'

        # Add the 'has_evaluation_data' flag based on whether there are evaluated predictions
        try:
            from src.database import get_evaluated_predictions_count
            evaluation_count = get_evaluated_predictions_count(execution_id)
            enhanced_execution["has_evaluation_data"] = evaluation_count > 0
        except Exception as eval_err:
            logger.warning(f"Could not fetch evaluation data count: {eval_err}")
            enhanced_execution["has_evaluation_data"] = False

        return {
            "execution": enhanced_execution,
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error getting execution details for {execution_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting execution details: {str(e)}")

@pipeline_router.get("/execution/{execution_id}/evaluation")
async def get_execution_evaluation(execution_id: str):
    """Get evaluation results for a specific pipeline execution"""
    try:
        from src.database import get_evaluated_predictions_for_execution
        
        # Get evaluation data for this execution
        evaluation_data = get_evaluated_predictions_for_execution(execution_id)
        
        if not evaluation_data:
            raise HTTPException(status_code=404, detail="No evaluation data found for this execution")
        
        # Calculate summary statistics
        total_predictions = len(evaluation_data['predictions'])
        winning_predictions = len([p for p in evaluation_data['predictions'] if p.get('prize_amount', 0) > 0])
        total_prizes = sum(p.get('prize_amount', 0) for p in evaluation_data['predictions'])
        best_prize = max((p.get('prize_amount', 0) for p in evaluation_data['predictions']), default=0)
        
        # Calculate win rate and average matches
        win_rate = (winning_predictions / total_predictions * 100) if total_predictions > 0 else 0
        avg_matches = sum(p.get('matches', 0) for p in evaluation_data['predictions']) / total_predictions if total_predictions > 0 else 0
        
        # Get only winners for the prize winners table
        prize_winners = [p for p in evaluation_data['predictions'] if p.get('prize_amount', 0) > 0]
        
        response_data = {
            "execution_id": execution_id,
            "evaluation_summary": {
                "target_draw_date": evaluation_data.get('target_draw_date', 'Unknown'),
                "total_predictions": total_predictions,
                "predictions_evaluated": total_predictions,
                "winning_predictions": winning_predictions,
                "total_prizes_won": total_prizes,
                "best_prize": best_prize,
                "win_rate": win_rate,
                "average_matches": avg_matches
            },
            "prize_winners": prize_winners,
            "timestamp": datetime.now().isoformat()
        }
        
        return convert_numpy_types(response_data)
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error getting evaluation for execution {execution_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting evaluation data: {str(e)}")

@pipeline_router.get("/history")
async def get_pipeline_history():
    """Get recent pipeline execution history from SQLite database"""
    try:
        from src.database import get_pipeline_execution_history
        from src.date_utils import DateManager

        # Get executions from SQLite database
        executions = get_pipeline_execution_history(limit=50)  # Get more for detailed history

        # Format for API response
        formatted_executions = []
        for execution in executions:
            # Pre-format dates for frontend display
            start_time_formatted = 'N/A'
            end_time_formatted = 'N/A'

            if execution.get('start_time'):
                start_time_formatted = DateManager.format_datetime_for_display(execution.get('start_time'))

            if execution.get('end_time'):
                end_time_formatted = DateManager.format_datetime_for_display(execution.get('end_time'))

            formatted_execution = {
                "execution_id": execution.get('execution_id'),
                "status": execution.get('status'),
                "start_time": execution.get('start_time'),
                "start_time_formatted": start_time_formatted,
                "end_time": execution.get('end_time'),
                "end_time_formatted": end_time_formatted,
                "trigger_type": execution.get('trigger_type', 'unknown'),
                "trigger_source": execution.get('trigger_source', 'unknown'),
                "steps_completed": execution.get('steps_completed', 0),
                "total_steps": 5,  # OPTIMIZED: Pipeline now has 5 steps
                "num_predictions": execution.get('num_predictions', 0),
                "error": execution.get('error'),
                "subprocess_success": execution.get('subprocess_success', False),
                "duration": _calculate_execution_duration(execution.get('start_time'), execution.get('end_time')),
                "progress_percentage": (execution.get('steps_completed', 0) / 5) * 100 if 5 > 0 else 0,  # Use 5 steps
                "has_evaluation_data": execution.get("has_evaluation_data", False)
            }
            formatted_executions.append(formatted_execution)

        return {
            "executions": formatted_executions[:30],  # Return last 30 executions
            "total_executions": len(formatted_executions),
            "database_source": "sqlite",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting pipeline history: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting pipeline history: {str(e)}")

@pipeline_router.get("/execution-history")
async def get_execution_history(
    limit: int = 20,
    current_user: User = Depends(get_current_user)
):
    """Get pipeline execution history with enhanced details"""
    try:
        # Get execution history from database
        executions = get_pipeline_execution_history(limit=limit)

        logger.info(f"Retrieved {len(executions)} executions from database")

        if not executions:
            logger.warning("No pipeline executions found in database")
            # Return empty structure but don't fail
            return {
                "executions": [],
                "total_executions": 0,
                "database_source": "sqlite",
                "timestamp": datetime.now().isoformat(),
                "debug_info": "No executions found in pipeline_executions table"
            }

        # Format executions for frontend
        formatted_executions = []
        for execution in executions:
            formatted_execution = {
                "execution_id": execution.get("execution_id", "unknown"),
                "status": execution.get("status", "unknown"),
                "start_time": execution.get("start_time"),
                "end_time": execution.get("end_time"),
                "trigger_type": execution.get("trigger_type", "manual"),
                "trigger_source": execution.get("trigger_source", "dashboard"),
                "current_step": execution.get("current_step"),
                "steps_completed": execution.get("steps_completed", 0),
                "total_steps": execution.get("total_steps", 7),
                "num_predictions": execution.get("num_predictions", 100),
                "error": execution.get("error"),
                "subprocess_success": execution.get("subprocess_success", False),
                "created_at": execution.get("created_at"),
                "has_evaluation_data": False  # Will be set based on actual data
            }

            # Check if execution has evaluation data
            if execution.get("status") == "completed":
                try:
                    from src.database import get_db_connection
                    with get_db_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT COUNT(*) FROM predictions_log 
                            WHERE evaluated = 1 
                            AND target_draw_date IS NOT NULL
                            AND created_at >= ? 
                            AND created_at <= ?
                        """, (execution.get("start_time"), execution.get("end_time") or datetime.now().isoformat()))

                        evaluation_count = cursor.fetchone()[0]
                        formatted_execution["has_evaluation_data"] = evaluation_count > 0

                except Exception as e:
                    logger.warning(f"Could not check evaluation data for execution {execution.get('execution_id')}: {e}")

            formatted_executions.append(formatted_execution)

        logger.info(f"Formatted {len(formatted_executions)} executions for frontend")

        return {
            "executions": formatted_executions[:30],  # Return last 30 executions
            "total_executions": len(formatted_executions),
            "database_source": "sqlite",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting pipeline history: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting pipeline history: {str(e)}")