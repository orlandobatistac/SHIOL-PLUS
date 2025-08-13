from fastapi import FastAPI, APIRouter, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
import os
from datetime import datetime
import asyncio
import uuid
from typing import Optional, Dict, Any
from pathlib import Path

from src.predictor import Predictor
from src.intelligent_generator import IntelligentGenerator, DeterministicGenerator
from src.loader import update_database_from_source
import src.database as db
from src.adaptive_feedback import initialize_adaptive_system
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
import pytz
from pydantic import BaseModel
from starlette import status
from starlette.responses import Response

# Import all modular API components
from src.api_utils import convert_numpy_types
from src.api_prediction_endpoints import prediction_router, set_prediction_components
from src.api_system_endpoints import system_router
# Removed unused endpoint imports after optimization
from src.api_pipeline_endpoints import pipeline_router
from src.public_api import public_router, auth_manager, auth_router
from src.api_public_endpoints import public_frontend_router, set_public_components
from src.api_dashboard_endpoints import dashboard_frontend_router, set_dashboard_components

# --- Pipeline Monitoring Global Variables ---
# Global variables for pipeline monitoring
pipeline_orchestrator = None
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

async def trigger_full_pipeline_automatically():
    """Task to trigger the full pipeline automatically with enhanced metadata."""
    logger.info("Running automatic full pipeline trigger.")
    try:
        # Check if pipeline is already running to prevent duplicates
        running_executions = [ex for ex in pipeline_executions.values() if ex.get("status") == "running"]
        if running_executions:
            logger.warning(f"Pipeline already running (ID: {running_executions[0].get('execution_id')}), skipping automatic execution.")
            return

        if pipeline_orchestrator:
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
                "num_predictions": 50,  # Standard 50 predictions
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

            # Run the full 7-step pipeline in background with 50 predictions using robust subprocess
            asyncio.create_task(run_full_pipeline_background(execution_id, 50))
            logger.info(f"Automatic pipeline execution started with ID: {execution_id} - Full 7-step pipeline (scheduled: {matches_schedule})")
        else:
            logger.warning("Pipeline orchestrator not available to trigger pipeline.")
    except Exception as e:
        logger.error(f"Error triggering automatic full pipeline: {e}")

async def run_full_pipeline_background(execution_id: str, num_predictions: int):
    """
    Run the full pipeline in background using subprocess for production reliability.

    Args:
        execution_id: Unique execution identifier
        num_predictions: Number of predictions to generate
    """
    logger.info(f"Starting background pipeline execution {execution_id} with {num_predictions} predictions")

    try:
        # Update execution status to starting
        pipeline_executions[execution_id]["status"] = "starting"

        # Build command - main.py ahora acepta argumentos
        cmd = [
            "python", "main.py"
        ]

        logger.info(f"Executing pipeline command: {' '.join(cmd)}")

        # Execute pipeline with proper timeout (15 minutes for Replit production)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=900,  # 15 minutes timeout optimized for Replit
                cwd=os.getcwd()
            )

            # Update execution status based on result
            if result.returncode == 0:
                pipeline_executions[execution_id].update({
                    "status": "completed",
                    "end_time": datetime.now().isoformat(),
                    "subprocess_success": True,
                    "steps_completed": 6,  # Pipeline has 6 steps
                    "stdout": result.stdout,
                    "stderr": result.stderr
                })
                logger.info(f"Pipeline execution {execution_id} completed successfully")
            else:
                pipeline_executions[execution_id].update({
                    "status": "failed",
                    "end_time": datetime.now().isoformat(),
                    "subprocess_success": False,
                    "error": f"Pipeline failed with return code {result.returncode}",
                    "stderr": result.stderr,
                    "stdout": result.stdout
                })
                logger.error(f"Pipeline execution {execution_id} failed with return code {result.returncode}")
                logger.error(f"STDERR: {result.stderr}")

        except subprocess.TimeoutExpired:
            pipeline_executions[execution_id].update({
                "status": "timeout",
                "end_time": datetime.now().isoformat(),
                "subprocess_success": False,
                "error": "Pipeline execution timed out after 15 minutes"
            })
            logger.error(f"Pipeline execution {execution_id} timed out")

        except Exception as subprocess_error:
            pipeline_executions[execution_id].update({
                "status": "failed",
                "end_time": datetime.now().isoformat(),
                "subprocess_success": False,
                "error": f"Subprocess execution failed: {str(subprocess_error)}"
            })
            logger.error(f"Pipeline subprocess execution failed: {subprocess_error}")

    except Exception as e:
        logger.error(f"Background pipeline execution failed: {e}")
        pipeline_executions[execution_id].update({
            "status": "failed",
            "end_time": datetime.now().isoformat(),
            "error": str(e),
            "subprocess_success": False
        })

    # Save execution record to database
    try:
        save_pipeline_execution_record(pipeline_executions[execution_id])
    except Exception as db_error:
        logger.error(f"Failed to save execution record to database: {db_error}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline_orchestrator
    # On startup
    logger.info("Application startup...")

    # Initialize pipeline orchestrator - CRITICAL COMPONENT
    try:
        from src.orchestrator import PipelineOrchestrator
        pipeline_orchestrator = PipelineOrchestrator()
        app.state.orchestrator = pipeline_orchestrator
        logger.info("Pipeline orchestrator initialized successfully")
    except ImportError as import_error:
        logger.critical(f"CRITICAL ERROR: PipelineOrchestrator class not found - {import_error}")
        logger.critical("Check src/orchestrator.py file exists and contains PipelineOrchestrator class")
        pipeline_orchestrator = None
        app.state.orchestrator = None
        raise RuntimeError(f"Pipeline orchestrator import failed: {import_error}")
    except Exception as e:
        logger.critical(f"CRITICAL ERROR: Failed to initialize pipeline orchestrator - {e}")
        logger.critical("Pipeline system cannot function without orchestrator")
        pipeline_orchestrator = None
        app.state.orchestrator = None
        raise RuntimeError(f"Pipeline orchestrator initialization failed: {e}")

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

# --- CORS Configuration - SECURED: Restricted to specific domains
# Security improvement: No longer using wildcard for origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://localhost:3000",
        "http://0.0.0.0:3000",  # For Replit external access
        # Add your production domain here
        # "https://yourdomain.com"
    ],
    allow_credentials=True,  # Required for HttpOnly cookies
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],  # Restricted headers for security
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
    set_dashboard_components(predictor, intelligent_generator, deterministic_generator)

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
        "database_status": "connected" if db.is_database_connected() else "disconnected",
        "model_status": "loaded" if predictor and hasattr(predictor, 'model') and predictor.model else "not_loaded"
    }

# --- Login Request Model ---
class LoginRequest(BaseModel):
    username: str
    password: str
    remember_me: bool = False

# --- Authentication Endpoints ---
@app.post("/api/v1/auth/login")
async def login(request: LoginRequest, response: Response):
    """Login endpoint that stores session token in HttpOnly cookie"""
    try:
        user = auth_manager.authenticate_user(request.username, request.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        # Determine session duration based on remember_me preference
        remember_me = getattr(request, 'remember_me', False)
        session_hours = 24 * 30 if remember_me else 24  # 30 days vs 24 hours
        cookie_max_age = session_hours * 3600  # Convert to seconds

        # Create session token with appropriate duration
        session_token = auth_manager.create_session(user, expires_hours=session_hours)
        if not session_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create session"
            )

        # Set HttpOnly, Secure, SameSite=Strict cookie
        response.set_cookie(
            key="shiol_session_token",
            value=session_token,
            httponly=True,        # Prevents JavaScript access (XSS protection)
            secure=False,         # Set to True in production with HTTPS
            samesite="lax",       # Changed from strict to lax for better compatibility
            max_age=cookie_max_age,  # Duration based on remember_me
            path="/"
        )
        return {
            "success": True,
            "message": "Login successful",
            "user": {
                "username": user.username,
                "role": user.role,
                "email": user.email
            }
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred during login."
        )

@app.post("/api/v1/auth/logout")
async def logout(response: Response):
    """Logout endpoint that clears session token from HttpOnly cookie"""
    try:
        # Clear the session cookie
        response.delete_cookie(key="shiol_session_token", path="/")
        return {"message": "Logout successful"}
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred during logout."
        )

# --- Application Mounting ---
# Mount all API routers before static files
app.include_router(api_router)
app.include_router(prediction_router)
app.include_router(system_router, prefix="/api/v1")
# Router mounts removed for optimized system
app.include_router(pipeline_router, prefix="/api/v1")
app.include_router(public_router)
app.include_router(auth_router)
# Mount modular frontend routers
app.include_router(public_frontend_router)
app.include_router(dashboard_frontend_router)

@app.get("/api/v1/prediction-history-grouped")
async def get_prediction_history_grouped(limit_dates: int = Query(25, ge=1, le=100)):
    """Get grouped prediction history by date"""
    try:
        from src.public_api import get_predictions_performance
        return await get_predictions_performance(limit_dates)
    except Exception as e:
        logger.error(f"Error in grouped prediction history: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving grouped prediction history")


# Build an absolute path to the 'frontend' directory for robust file serving.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))

# Ensure the frontend directory exists before mounting
if not os.path.exists(FRONTEND_DIR):
    logger.warning(f"Frontend directory not found at {FRONTEND_DIR}. Static file serving may fail.")

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")