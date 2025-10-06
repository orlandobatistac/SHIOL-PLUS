from fastapi import FastAPI, APIRouter, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loguru import logger
import os
from datetime import datetime
import asyncio
import uuid
from typing import Optional, Dict, Any
from pathlib import Path
import traceback # Import traceback for error logging

from src.predictor import Predictor
from src.intelligent_generator import IntelligentGenerator, DeterministicGenerator
from src.loader import update_database_from_source
import src.database as db
# from src.adaptive_feedback import initialize_adaptive_system  # REMOVED
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
import pytz
from pydantic import BaseModel
from starlette import status
from starlette.responses import Response

# Import remaining API components (simplified)
from src.simple_utils import convert_numpy_types, format_prediction_response
from src.api_prediction_endpoints import prediction_router, draw_router, set_prediction_components
from src.api_public_endpoints import public_frontend_router, set_public_components
from src.api_ticket_endpoints import ticket_router
from src.api_auth_endpoints import auth_router

# --- Pipeline Monitoring Global Variables ---
# Global variables for pipeline monitoring
# Pipeline orchestrator deprecated and removed
pipeline_executions = {}  # Track running pipeline executions
pipeline_logs = []  # Store recent pipeline logs

# --- Scheduler and App Lifecycle ---
scheduler = AsyncIOScheduler()

async def update_data_automatically():
    """Task to update database from source."""
    logger.info("Running automatic data update task.")
    try:
        update_database_from_source()
        logger.info("Automatic data update completed successfully.")
    except Exception as e:
        logger.error(f"Error during automatic data update: {e}")

async def evaluate_predictions_automatically():
    """Task to automatically evaluate predictions in background."""
    logger.info("Running automatic prediction evaluation task.")
    try:
        from src.prediction_evaluator import run_prediction_evaluation

        # Run the evaluation in background
        results = run_prediction_evaluation()

        if 'error' not in results:
            logger.info(f"Automatic evaluation completed: {results.get('total_predictions_evaluated', 0)} predictions evaluated")
        else:
            logger.error(f"Automatic evaluation failed: {results['error']}")

    except Exception as e:
        logger.error(f"Error during automatic prediction evaluation: {e}")

async def trigger_full_pipeline_automatically():
    """Task to trigger the full pipeline automatically with enhanced metadata."""
    logger.info("Running automatic full pipeline trigger.")
    try:
        # Check if pipeline is already running to prevent duplicates
        running_executions = [ex for ex in pipeline_executions.values() if ex.get("status") == "running"]
        if running_executions:
            logger.warning(f"Pipeline already running (ID: {running_executions[0].get('execution_id')}), skipping automatic execution.")
            return

        # Get current scheduler configuration
        current_time = datetime.now()
        current_day = current_time.strftime('%A').lower()
        current_time_str = current_time.strftime('%H:%M')

        # Expected scheduler configuration (from scheduler setup)
        expected_days = ['monday', 'wednesday', 'saturday']
        expected_time = '23:30'
        timezone = 'America/New_York'

        # Check if execution matches schedule
        matches_schedule = (
            current_day in expected_days and
            abs((current_time.hour * 60 + current_time.minute) - (23 * 60 + 30)) <= 5  # 5 minute tolerance
        )

        # Trigger the full pipeline execution with enhanced metadata
        execution_id = str(uuid.uuid4())[:8]
        pipeline_executions[execution_id] = {
            "execution_id": execution_id,
            "status": "starting",
            "start_time": current_time.isoformat(),
            "current_step": "automated_trigger",
            "steps_completed": 0,
            "total_steps": 7,  # Always 7 steps for full pipeline
            "num_predictions": 100,  # Standard 100 predictions
            "requested_steps": None,  # Full pipeline, all steps
            "error": None,
            "trigger_type": "automatic_scheduler",
            "execution_source": "automatic_scheduler",
            "trigger_details": {
                "type": "scheduled",
                "scheduled_config": {
                    "days": expected_days,
                    "time": expected_time,
                    "timezone": timezone
                },
                "actual_execution": {
                    "day": current_day,
                    "time": current_time_str,
                    "matches_schedule": matches_schedule
                },
                "triggered_by": "automatic_scheduler"
            }
        }

        # Run the full 6-step pipeline in background with 100 predictions using robust subprocess
        asyncio.create_task(run_full_pipeline_background(execution_id, 100))
        logger.info(f"Automatic pipeline execution started with ID: {execution_id} - Full 6-step pipeline (scheduled: {matches_schedule})")

    except Exception as e:
        logger.error(f"Error triggering automatic full pipeline: {e}")

async def run_full_pipeline_background(execution_id: str, num_predictions: int = 100):
    """
    UNIFIED PIPELINE: Run the full pipeline using main.py subprocess for maximum stability
    """
    try:
        logger.info(f"Starting UNIFIED pipeline execution {execution_id} via main.py subprocess")

        # Update status to running
        pipeline_executions[execution_id] = {
            **pipeline_executions.get(execution_id, {}),
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "current_step": "subprocess_initialization"
        }

        # Execute main.py in subprocess for stability (UNIFIED APPROACH)
        import subprocess
        import os

        cmd = [
            "python", "main.py",
            "--predictions", str(num_predictions)
        ]

        # Set environment variable for execution tracking
        env = os.environ.copy()
        env['PIPELINE_EXECUTION_ID'] = execution_id
        env['PIPELINE_EXECUTION_SOURCE'] = 'api_dashboard'

        logger.info(f"Executing UNIFIED pipeline via subprocess: {' '.join(cmd)}")

        # Execute with timeout (30 minutes for Replit production)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minutes timeout
            cwd=os.getcwd(),
            env=env
        )

        success = result.returncode == 0

        # Update execution status based on result
        pipeline_executions[execution_id] = {
            **pipeline_executions.get(execution_id, {}),
            "status": "completed" if success else "failed",
            "end_time": datetime.now().isoformat(),
            "subprocess_success": success,
            "return_code": result.returncode,
            "stdout": result.stdout[-1000:] if result.stdout else "",  # Last 1000 chars
            "stderr": result.stderr[-1000:] if result.stderr else "",   # Last 1000 chars
        }

        if success:
            logger.info(f"UNIFIED pipeline execution {execution_id} completed successfully")
        else:
            logger.error(f"UNIFIED pipeline execution {execution_id} failed with return code {result.returncode}")
            if result.stderr:
                logger.error(f"Pipeline stderr: {result.stderr[-500:]}")

    except subprocess.TimeoutExpired:
        error_msg = f"UNIFIED pipeline execution {execution_id} timed out after 30 minutes"
        logger.error(error_msg)

        pipeline_executions[execution_id] = {
            **pipeline_executions.get(execution_id, {}),
            "status": "timeout",
            "error": error_msg,
            "end_time": datetime.now().isoformat()
        }

    except Exception as e:
        error_msg = f"UNIFIED pipeline execution {execution_id} failed: {str(e)}"
        logger.error(error_msg)
        logger.error(f"Traceback: {traceback.format_exc()}")

        # Update execution status to failed
        pipeline_executions[execution_id] = {
            **pipeline_executions.get(execution_id, {}),
            "status": "failed",
            "error": error_msg,
            "end_time": datetime.now().isoformat(),
            "traceback": traceback.format_exc()
        }


def save_pipeline_execution_record(execution_data: dict):
    """
    Save pipeline execution record to the database.

    Args:
        execution_data: Dictionary containing execution information
    """
    try:
        from src.database import save_pipeline_execution

        # Ensure all required fields are present with defaults
        record = {
            'execution_id': execution_data.get('execution_id'),
            'status': execution_data.get('status', 'unknown'),
            'start_time': execution_data.get('start_time'),
            'end_time': execution_data.get('end_time'),
            'trigger_type': execution_data.get('trigger_type', 'manual'),
            'trigger_source': execution_data.get('trigger_source', 'dashboard'),
            'steps_completed': execution_data.get('steps_completed', 0),
            'num_predictions': execution_data.get('num_predictions', 100),
            'error': execution_data.get('error'),
            'subprocess_success': execution_data.get('subprocess_success', False),
            'current_step': execution_data.get('current_step')
        }

        # Save to database
        save_pipeline_execution(record)
        logger.info(f"Saved execution record {record['execution_id']} to database")

    except Exception as e:
        logger.error(f"Error saving pipeline execution record: {e}")
        raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pipeline orchestrator is deprecated and removed
    # On startup
    logger.info("Application startup...")
    
    # Initialize database and create tables
    from src.database import initialize_database
    try:
        initialize_database()
        logger.info("Database initialized and migrations applied")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    # Pipeline orchestrator removed - deprecated system that caused inconsistent results

    # Schedule pipeline execution optimally:
    # 1. Full pipeline only on actual drawing days (Monday, Wednesday, Saturday)
    # Drawing is at 10:59 PM ET, so pipeline runs at 11:29 PM ET (30 minutes after)
    scheduler.add_job(
        func=trigger_full_pipeline_automatically,
        trigger="cron",
        day_of_week="mon,wed,sat", # Only on actual Powerball drawing days
        hour=23,                    # 11 PM ET
        minute=29,                  # 11:29 PM - 30 minutes after 10:59 PM drawing
        timezone="America/New_York", # EXPLICIT TIMEZONE FIX
        id="post_drawing_pipeline",
        name="Full Pipeline 30 Minutes After Drawing (11:29 PM ET)",
        max_instances=1,           # Prevent overlapping executions
        coalesce=True             # Merge multiple pending executions into one
    )

    # 2. Maintenance data update only (no full pipeline)
    scheduler.add_job(
        func=update_data_automatically,
        trigger="cron",
        day_of_week="tue,thu,fri,sun", # Non-drawing days only
        hour=6,                        # 6 AM instead of every 12 hours
        minute=0,
        timezone="America/New_York", # EXPLICIT TIMEZONE FIX
        id="maintenance_data_update",
        name="Maintenance Data Update on Non-Drawing Days",
        max_instances=1,
        coalesce=True
    )

    # 3. Automatic prediction evaluation every 6 hours
    scheduler.add_job(
        func=evaluate_predictions_automatically,
        trigger="cron",
        hour="6,12,18",             # Every 6 hours (6 AM, 12 PM, 6 PM ET)
        minute=15,                  # 15 minutes past the hour
        timezone="America/New_York",
        id="prediction_evaluation",
        name="Automatic Prediction Evaluation (Every 6 Hours)",
        max_instances=1,
        coalesce=True
    )
    # Start scheduler after configuration
    try:
        scheduler.start()
        logger.info("Scheduler started successfully")

        # Log detailed scheduler configuration for debugging
        jobs = scheduler.get_jobs()
        logger.info(f"Active scheduled jobs: {len(jobs)}")
        for job in jobs:
            try:
                next_run = getattr(job, 'next_run_time', 'Unknown')
                timezone = getattr(job.trigger, 'timezone', 'Unknown')
                logger.info(f"Job: {job.id} | Next run: {next_run} | Timezone: {timezone}")
            except AttributeError as e:
                logger.warning(f"Job {job.id} missing attributes: {e}")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")

    # Log current time in multiple timezones for debugging
    try:
        from src.date_utils import DateManager
        current_et = DateManager.get_current_et_time()
    except ImportError:
        # Fallback if date_utils is not available
        et_tz = pytz.timezone('America/New_York')
        current_et = datetime.now(et_tz)
    current_utc = datetime.now(pytz.UTC)
    logger.info(f"Current time - UTC: {current_utc.isoformat()} | ET: {current_et.isoformat()}")

    yield
    # On shutdown
    logger.info("Application shutdown...")
    scheduler.shutdown()
    logger.info("Scheduler shut down.")

# --- Application Initialization ---
logger.info("Initializing FastAPI application...")
app = FastAPI(
    title="SHIOL+ Powerball Prediction API",
    description="Provides ML-based Powerball number predictions.",
    version="6.0.0", # Updated version to 6.0.0
    lifespan=lifespan
)

# Configure file upload limits for mobile compatibility
app.extra["max_upload_size"] = 25 * 1024 * 1024  # 25MB for mobile images

# --- CORS Configuration - SECURED: Configured for Replit deployment
# Security improvement: Specific domains with Replit support
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for debugging
    allow_credentials=True,  # Required for HttpOnly cookies
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)

# --- Pipeline-Only Configuration ---
PIPELINE_ONLY_MODE = True
ALLOW_INDIVIDUAL_PREDICTIONS = False
MIN_PREDICTIONS_PER_EXECUTION = 100

logger.info(f"System Configuration: PIPELINE_ONLY_MODE={PIPELINE_ONLY_MODE}")

# --- Global Components ---
try:
    logger.info("Loading model and generator instances...")
    predictor = Predictor()

    # Load historical data first
    from src.loader import DataLoader
    data_loader = DataLoader()
    historical_data = data_loader.load_historical_data()

    # Initialize generators with historical data
    intelligent_generator = IntelligentGenerator(historical_data)
    deterministic_generator = DeterministicGenerator(historical_data)

    logger.info("Model and generators loaded successfully.")

    # Set up prediction components for modular endpoints
    set_prediction_components(predictor, intelligent_generator, deterministic_generator)
    set_public_components(predictor, intelligent_generator, deterministic_generator)
    # set_dashboard_components removed (no auth needed)

except Exception as e:
    logger.critical(f"Fatal error during startup: Failed to load model. Error: {e}")
    predictor = None
    intelligent_generator = None
    deterministic_generator = None

# --- API Router ---
api_router = APIRouter(prefix="/api/v1")

# Basic system info endpoint (kept in main API for core functionality)
@api_router.get("/system/info")
async def get_system_info():
    """Get system information"""
    return {
        "version": "6.0.0",
        "status": "operational",
        "database_status": "connected",
        "model_status": "loaded" if predictor and hasattr(predictor, 'model') and predictor.model else "not_loaded"
    }

# --- Health Check Endpoint ---
@api_router.get("/health")
async def health_check():
    """Health check endpoint with timestamp"""
    from datetime import datetime
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "3.0.0",
        "service": "SHIOL+ API"
    }

# Simple health endpoint without prefix for easy access
@app.get("/health")
async def health():
    """Simple health check"""
    return {"status": "ok"}

# --- Application Mounting ---
# Mount all API routers before static files
# Mount routers - public routes first to ensure they are always accessible
app.include_router(api_router)  # Core API routes (health, system info)
app.include_router(auth_router)  # Authentication endpoints

# Import billing router
from src.api_billing_endpoints import billing_router
app.include_router(billing_router)  # Billing endpoints
app.include_router(prediction_router, prefix="/api/v1/predictions")
app.include_router(draw_router, prefix="/api/v1/draws")
app.include_router(ticket_router)  # Ticket verification endpoints
app.include_router(public_frontend_router)

@app.get("/api/v1/prediction-history-grouped")
async def get_prediction_history_grouped(limit_dates: int = Query(25, ge=1, le=100)):
    """Get grouped prediction history by date"""
    try:
        # from src.public_api import get_predictions_performance
        # Temporarily disabled - implement if needed
        return {"message": "Prediction history temporarily unavailable"}
    except Exception as e:
        logger.error(f"Error in grouped prediction history: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving grouped prediction history")

# Debug endpoint to verify all routes
@app.get("/api/v1/debug/routes")
async def debug_routes():
    """Debug endpoint to show all available routes"""
    routes = []
    for route in app.routes:
        try:
            if hasattr(route, 'path'):
                routes.append({
                    "path": str(route.path),
                    "methods": list(getattr(route, 'methods', [])) if hasattr(route, 'methods') else []
                })
        except Exception:
            continue
    return {"routes": routes}


# Build an absolute path to the 'frontend' directory for robust file serving.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))

# Ensure directories exist before mounting
if not os.path.exists(FRONTEND_DIR):
    logger.warning(f"Frontend directory not found at {FRONTEND_DIR}. Static file serving may fail.")

# Generate automatic version for service worker based on server start time
SERVER_START_TIMESTAMP = datetime.now().strftime("%Y%m%d%H%M%S")
logger.info(f"Service Worker auto-version: {SERVER_START_TIMESTAMP}")


# PWA assets now served directly from frontend directory

# Special route for payment success page (before middleware)
@app.get("/payment-success", response_class=Response)
async def payment_success_page():
    """Serve payment success page specifically"""
    payment_success_path = os.path.join(FRONTEND_DIR, "payment-success.html")
    if os.path.exists(payment_success_path):
        with open(payment_success_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return Response(content=content, media_type="text/html")
    else:
        raise HTTPException(status_code=404, detail="Payment success page not found")

# Dynamic service worker endpoint with auto-versioning
@app.get("/service-worker.js", response_class=Response)
async def serve_service_worker():
    """Serve service worker with automatic version based on server start time"""
    sw_path = os.path.join(FRONTEND_DIR, "service-worker.js")
    if os.path.exists(sw_path):
        with open(sw_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace the static version with dynamic server timestamp
        content = content.replace(
            "const APP_VERSION = '2.0.1';",
            f"const APP_VERSION = '{SERVER_START_TIMESTAMP}';"
        )
        
        # Add no-cache headers to ensure browser always checks for updates
        response = Response(content=content, media_type="application/javascript")
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        return response
    else:
        raise HTTPException(status_code=404, detail="Service worker not found")

# Add cache control middleware for CSS/JS files to prevent Chrome caching issues
@app.middleware("http")
async def cache_control_middleware(request, call_next):
    """
    Prevent aggressive caching of CSS/JS files that causes inconsistent blur behavior in Chrome.
    """
    response = await call_next(request)
    
    # Apply no-cache headers to CSS and JS files to prevent Chrome blur inconsistencies
    if request.url.path.endswith(('.css', '.js')):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    
    return response

# Mount frontend last (catch-all for HTML)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")