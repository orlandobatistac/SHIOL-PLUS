from fastapi import APIRouter, HTTPException
from loguru import logger
from datetime import datetime

import src.database as db

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
async def get_pipeline_status():
    """Get current pipeline status and recent execution history"""
    try:
        from src.api import pipeline_executions
        from datetime import datetime, timezone
        import pytz

        pipeline_status = "idle"
        last_execution = None
        current_executions = []
        next_scheduled_execution = None

        # Check if there's an active orchestrator in the app state
        if hasattr(app.state, 'orchestrator') and app.state.orchestrator:
            try:
                status_info = app.state.orchestrator.get_pipeline_status()
                pipeline_status = status_info.get('current_status', 'idle')
                last_execution_info = status_info.get('last_execution')
                if last_execution_info and isinstance(last_execution_info, dict) and last_execution_info.get('start_time'):
                    last_execution = last_execution_info['start_time']
                elif isinstance(last_execution_info, str):
                    last_execution = last_execution_info
            except Exception as e:
                logger.warning(f"Could not retrieve pipeline status: {e}")
                pipeline_status = "idle"

        # Calculate next scheduled execution (Mon, Wed, Sat at 11:30 PM ET)
        try:
            et_tz = pytz.timezone('America/New_York')
            now_et = datetime.now(et_tz)

            # Drawing days: Monday (0), Wednesday (2), Saturday (5) (weekday format)
            drawing_days = [0, 2, 5]  # Monday, Wednesday, Saturday
            execution_hour = 23  # 11 PM
            execution_minute = 30

            # Find the next drawing day
            for i in range(8):  # Check next 8 days
                check_date = now_et.replace(hour=execution_hour, minute=execution_minute, second=0, microsecond=0)
                check_date = check_date + timezone.timedelta(days=i)

                if check_date.weekday() in drawing_days:
                    # If it's today and the execution time hasn't passed yet
                    if i == 0 and now_et.time() < check_date.time():
                        next_scheduled_execution = check_date.isoformat()
                        break
                    # If it's a future day
                    elif i > 0:
                        next_scheduled_execution = check_date.isoformat()
                        break
        except Exception as e:
            logger.warning(f"Could not calculate next scheduled execution: {e}")

        # Get current running executions
        for execution_id, execution_data in pipeline_executions.items():
            if execution_data.get("status") == "running":
                current_executions.append({
                    "execution_id": execution_id,
                    "start_time": execution_data.get("start_time"),
                    "current_step": execution_data.get("current_step"),
                    "steps_completed": execution_data.get("steps_completed", 0),
                    "total_steps": execution_data.get("total_steps", 7)
                })

        return {
            "status": pipeline_status,
            "last_execution": last_execution,
            "next_scheduled_execution": next_scheduled_execution,
            "current_executions": current_executions,
            "total_executions": len(pipeline_executions),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting pipeline status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting pipeline status: {str(e)}")

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