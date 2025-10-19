from fastapi import FastAPI, APIRouter, Query, HTTPException, Depends, Request
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
import traceback
import subprocess

from src.predictor import Predictor
from src.intelligent_generator import IntelligentGenerator, DeterministicGenerator
from src.loader import update_database_from_source
import src.database as db
# from src.adaptive_feedback import initialize_adaptive_system  # REMOVED
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
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
from src.auth_middleware import require_admin_access

# --- Pipeline Monitoring Global Variables ---
# Global variables for pipeline monitoring
# Pipeline orchestrator deprecated and removed
pipeline_executions = {}  # Track running pipeline executions
pipeline_logs = []  # Store recent pipeline logs

# --- Scheduler and App Lifecycle ---
# Configure persistent jobstore using SQLite
# Use relative path from project root for portability (Replit/VPS)
import os
scheduler_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'scheduler.db')
scheduler_db_url = f'sqlite:///{scheduler_db_path}'

jobstores = {
    'default': SQLAlchemyJobStore(url=scheduler_db_url)
}

# Configure thread pool executor for job execution
executors = {
    'default': ThreadPoolExecutor(max_workers=3)
}

# Default job configuration
job_defaults = {
    'coalesce': True,           # Merge multiple missed runs into one
    'max_instances': 1,         # Prevent overlapping executions
    'misfire_grace_time': 600   # 10 minutes tolerance for missed jobs
}

# Initialize scheduler with persistent configuration
scheduler = AsyncIOScheduler(
    jobstores=jobstores,
    executors=executors,
    job_defaults=job_defaults
)

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

        # Get current scheduler configuration
        current_time = datetime.now()
        current_day = current_time.strftime('%A').lower()
        current_time_str = current_time.strftime('%H:%M')

    # Expected scheduler configuration (from scheduler setup)
    # Drawings occur Monday, Wednesday, Saturday at 22:59 ET; pipeline runs the next day at 01:00 ET
    expected_days = ['tuesday', 'thursday', 'sunday']
    expected_time = '01:00'
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
    # 1. Full pipeline runs at 01:00 AM ET the day after each drawing (Tue/Thu/Sun)
    #    This gives external APIs time to publish official results before evaluation.
    scheduler.add_job(
        func=trigger_full_pipeline_automatically,
        trigger="cron",
        day_of_week="tue,thu,sun", # Next-day after actual Powerball drawing days
        hour=1,                      # 01:00 AM ET
        minute=0,                    # 01:00 AM - safer delay to allow results to be published
        timezone="America/New_York", # EXPLICIT TIMEZONE
        id="post_drawing_pipeline",
        name="Full Pipeline Next-Day 01:00 AM ET",
        max_instances=1,           # Prevent overlapping executions
        coalesce=True,             # Merge multiple pending executions into one
        replace_existing=True      # Update job on restart instead of duplicating
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
        coalesce=True,
        replace_existing=True      # Update job on restart instead of duplicating
    )

    # Start scheduler after configuration
    try:
        scheduler.start()
        logger.info("✅ Scheduler started successfully with persistent jobstore (SQLite)")
        logger.info(f"📁 Jobstore location: {scheduler_db_path}")

        # Log detailed scheduler configuration for debugging
        jobs = scheduler.get_jobs()
        logger.info(f"📋 Active scheduled jobs: {len(jobs)}")
        for job in jobs:
            try:
                next_run = getattr(job, 'next_run_time', 'Unknown')
                timezone = getattr(job.trigger, 'timezone', 'Unknown')
                logger.info(f"  • Job: {job.id} | Next run: {next_run} | Timezone: {timezone}")
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

# --- Scheduler Health Check Endpoint ---
@api_router.get("/scheduler/health")
async def get_scheduler_health():
    """
    Scheduler health check endpoint for monitoring.
    Returns scheduler status and list of active jobs.
    """
    try:
        jobs = scheduler.get_jobs()
        
        return {
            "scheduler_running": scheduler.running,
            "total_jobs": len(jobs),
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger)
                }
                for job in jobs
            ],
            "timestamp": datetime.now().isoformat(),
            "jobstore_type": "SQLAlchemyJobStore (SQLite)",
            "jobstore_path": scheduler_db_path
        }
    except Exception as e:
        logger.error(f"Error getting scheduler health: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving scheduler health: {str(e)}"
        )

# --- System Stats Endpoint ---
@api_router.get("/system/stats")
async def get_system_stats():
    """
    Get comprehensive system statistics for status dashboard.
    Returns database stats, pipeline metrics, and system health.
    """
    try:
        from src.database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get database statistics
        cursor.execute("SELECT COUNT(*) FROM powerball_draws")
        total_draws = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM predictions_log")
        total_predictions = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
        premium_users = cursor.fetchone()[0]
        
        # Get latest pipeline execution
        cursor.execute("""
            SELECT created_at, prize_description 
            FROM predictions_log 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        latest_prediction = cursor.fetchone()
        
        # Get latest draw
        cursor.execute("""
            SELECT draw_date, n1, n2, n3, n4, n5, pb 
            FROM powerball_draws 
            ORDER BY draw_date DESC 
            LIMIT 1
        """)
        latest_draw = cursor.fetchone()
        
        # Get predictions with matches
        cursor.execute("""
            SELECT COUNT(*) FROM predictions_log 
            WHERE evaluated = 1 
            AND matches_wb > 0
        """)
        winning_predictions = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "database": {
                "total_draws": total_draws,
                "total_predictions": total_predictions,
                "total_users": total_users,
                "premium_users": premium_users,
                "winning_predictions": winning_predictions
            },
            "pipeline": {
                "last_execution": latest_prediction[0] if latest_prediction else None,
                "last_status": latest_prediction[1] if latest_prediction else None
            },
            "latest_draw": {
                "date": latest_draw[0] if latest_draw else None,
                "numbers": f"{latest_draw[1]}, {latest_draw[2]}, {latest_draw[3]}, {latest_draw[4]}, {latest_draw[5]}" if latest_draw else None,
                "powerball": latest_draw[6] if latest_draw else None
            },
            "system": {
                "version": "6.0.0",
                "model_loaded": predictor is not None and hasattr(predictor, 'model') and predictor.model is not None,
                "generators_loaded": intelligent_generator is not None and deterministic_generator is not None
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving system stats: {str(e)}"
        )

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

# Special route for status dashboard page (Admin only)
@app.get("/status", response_class=Response)
async def status_dashboard_page(request: Request):
    """Serve system status dashboard page (Admin access required)"""
    from fastapi.responses import RedirectResponse
    from src.auth_middleware import get_user_from_request
    
    # Check authentication manually to provide better UX
    user = get_user_from_request(request)
    
    if not user:
        # Not authenticated - redirect to home page and trigger login modal
        return RedirectResponse(url="/?login=required", status_code=302)
    
    # Debug logging
    logger.info(f"User accessing /status: {user.get('username')} - is_admin: {user.get('is_admin', False)}")
    
    if not user.get("is_admin", False):
        # Authenticated but not admin - show friendly error page
        error_html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Access Denied - SHIOL+</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-900 text-white min-h-screen flex items-center justify-center">
            <div class="text-center max-w-md mx-auto px-6">
                <div class="mb-6">
                    <i class="fas fa-lock text-6xl text-red-500"></i>
                </div>
                <h1 class="text-3xl font-bold mb-4">Access Denied</h1>
                <p class="text-gray-400 mb-8">This resource is restricted to administrators only.</p>
                <a href="/" class="inline-block bg-gradient-to-r from-cyan-500 to-pink-500 text-white px-6 py-3 rounded-lg hover:opacity-90 transition">
                    Return to Home
                </a>
            </div>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        </body>
        </html>
        """
        return Response(content=error_html, media_type="text/html", status_code=403)
    
    # User is authenticated and admin - serve status page
    status_path = os.path.join(FRONTEND_DIR, "status.html")
    if os.path.exists(status_path):
        with open(status_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return Response(content=content, media_type="text/html")
    else:
        raise HTTPException(status_code=404, detail="Status page not found")

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

# Add cache control middleware for critical files to prevent caching issues
@app.middleware("http")
async def cache_control_middleware(request, call_next):
    """
    Prevent aggressive caching of HTML, CSS, and JS files to ensure users always get latest version.
    This prevents PWA service worker cache issues and ensures updates are visible immediately.
    """
    response = await call_next(request)
    
    # Apply no-cache headers to HTML, CSS, and JS files
    if request.url.path.endswith(('.html', '.css', '.js')) or request.url.path == '/':
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    
    return response

# Mount frontend last (catch-all for HTML)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")