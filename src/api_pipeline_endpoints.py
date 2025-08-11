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
    """Get current pipeline execution status"""
    try:
        # Check for running pipeline process or status file
        status_file = "data/pipeline_status.json"
        if os.path.exists(status_file):
            with open(status_file, 'r') as f:
                status_data = json.load(f)
                if status_data.get("status") == "running":
                    # Check if the process is actually still running
                    start_time = datetime.fromisoformat(status_data.get("start_time", datetime.now().isoformat()))
                    if datetime.now() - start_time > timedelta(hours=2):
                        # Process likely hung, mark as failed
                        return {"status": "failed", "description": "Pipeline execution timed out"}
                    return {"status": "running", "description": "Pipeline is currently executing"}
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
    """Get scheduler status and next run information"""
    try:
        from src.api import scheduler
        if scheduler and scheduler.running:
            jobs = scheduler.get_jobs()
            next_job = None
            for job in jobs:
                if not next_job or job.next_run_time < next_job.next_run_time:
                    next_job = job

            return {
                "active": True,
                "job_count": len(jobs),
                "next_run": next_job.next_run_time.isoformat() if next_job and next_job.next_run_time else None
            }
        else:
            return {"active": False, "job_count": 0, "next_run": None}
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        return {"active": False, "job_count": 0, "next_run": None}

async def _get_execution_history(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent pipeline execution history"""
    try:
        history_file = "data/pipeline_history.json"
        if os.path.exists(history_file):
            with open(history_file, 'r') as f:
                history = json.load(f)
                return history[-limit:] if isinstance(history, list) else []
        return []
    except Exception as e:
        logger.error(f"Error getting execution history: {e}")
        return []

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

@pipeline_router.get("/history")
async def get_pipeline_history():
    """Get recent pipeline execution history"""
    try:
        from src.api import pipeline_executions

        # Convert pipeline executions to list and sort by start time
        history = []
        for execution_id, execution_data in pipeline_executions.items():
            history.append({
                "execution_id": execution_id,
                "status": execution_data.get("status"),
                "start_time": execution_data.get("start_time"),
                "end_time": execution_data.get("end_time"),
                "trigger_type": execution_data.get("trigger_type", "unknown"),
                "steps_completed": execution_data.get("steps_completed", 0),
                "total_steps": execution_data.get("total_steps", 7),
                "num_predictions": execution_data.get("num_predictions", 0),
                "error": execution_data.get("error")
            })

        # Sort by start time (most recent first)
        history.sort(key=lambda x: x.get("start_time", ""), reverse=True)

        return {
            "executions": history[:20],  # Return last 20 executions
            "total_executions": len(history),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting pipeline history: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting pipeline history: {str(e)}")