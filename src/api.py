from fastapi import FastAPI, APIRouter, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
import os
from datetime import datetime, timezone, timedelta
import uuid
from typing import Dict, List
import traceback
import subprocess
import zlib
import re

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
from starlette.responses import Response

# Import remaining API components (simplified)
from src.api_prediction_endpoints import prediction_router, draw_router, set_prediction_components
from src.api_public_endpoints import public_frontend_router, set_public_components
from src.api_ticket_endpoints import ticket_router
from src.api_auth_endpoints import auth_router
from src.api_admin_endpoints import router as admin_router
import psutil
import shutil
import platform

# --- Pipeline Monitoring Global Variables ---
# Global variables for pipeline monitoring
# Pipeline orchestrator deprecated and removed
pipeline_executions = {}  # Track running pipeline executions
pipeline_logs = []  # Store recent pipeline logs

# --- Scheduler and App Lifecycle ---
# Configure persistent jobstore using SQLite
# Use relative path from project root for portability (Replit/VPS)
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

async def adaptive_learning_update():
    """Update strategy weights based on recent performance using a simple empirical Bayes-like update.

    This reads `strategy_performance` table and updates `current_weight` and `confidence`.
    """
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT strategy_name, total_plays, total_wins FROM strategy_performance")
        rows = cursor.fetchall()

        # Compute raw scores (win_rate with small prior) and normalize
        scores = {}
        for name, plays, wins in rows:
            plays = plays or 0
            wins = wins or 0
            win_rate = (wins / plays) if plays > 0 else 0.01
            # Add small prior to avoid zero
            scores[name] = win_rate + 0.01

        total_score = sum(scores.values()) if scores else 0.0

        for name, raw in scores.items():
            new_weight = (raw / total_score) if total_score > 0 else (1.0 / max(1, len(scores)))
            # Confidence increases with number of plays, bounded [0.1, 0.95]
            cursor.execute("SELECT total_plays FROM strategy_performance WHERE strategy_name = ?", (name,))
            tp = cursor.fetchone()
            plays = tp[0] if tp and tp[0] is not None else 0
            confidence = min(0.95, 0.1 + (plays / (plays + 100)) if plays >= 0 else 0.1)

            cursor.execute(
                "UPDATE strategy_performance SET current_weight = ?, confidence = ?, last_updated = CURRENT_TIMESTAMP WHERE strategy_name = ?",
                (float(new_weight), float(confidence), name)
            )

        conn.commit()
        conn.close()
        logger.info("Adaptive learning update: strategy weights updated")
        return True
    except Exception as e:
        logger.error(f"Adaptive learning update failed: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return False


async def evaluate_predictions_for_draw(draw_date: str):
    """Evaluate predictions for a specific draw date and record performance."""
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()

        # Get official result
        cursor.execute("SELECT n1, n2, n3, n4, n5, pb FROM powerball_draws WHERE draw_date = ?", (draw_date,))
        official = cursor.fetchone()
        if not official:
            logger.warning(f"No official draw found for {draw_date}")
            conn.close()
            return False

        winning_nums = [official[0], official[1], official[2], official[3], official[4]]
        winning_pb = official[5]

        # Find predictions for this draw that haven't been evaluated
        cursor.execute(
            "SELECT id, n1, n2, n3, n4, n5, powerball FROM generated_tickets WHERE draw_date = ? AND evaluated = 0",
            (draw_date,)
        )

        preds = cursor.fetchall()

        for row in preds:
            pred_id = row[0]
            pred_nums = [row[1], row[2], row[3], row[4], row[5]]
            pred_pb = row[6]

            matches_main = len(set(pred_nums) & set(winning_nums))
            matches_pb = 1 if pred_pb == winning_pb else 0

            prize_amount, prize_description = db.calculate_prize_amount(matches_main, bool(matches_pb))

            # Insert into performance_tracking using the SAME connection/cursor to avoid locks
            try:
                db.save_performance_tracking(
                    pred_id,
                    draw_date,
                    winning_nums,
                    winning_pb,
                    matches_main,
                    matches_pb,
                    prize_description or 'Non-winning',
                    0.0,
                    {},
                    cursor=cursor,
                )
            except Exception as ex:
                logger.error(f"Failed to save performance tracking for prediction {pred_id}: {ex}")

            # Update predictions_log evaluated fields
            try:
                cursor.execute(
                    "UPDATE generated_tickets SET evaluated = 1, matches_wb = ?, matches_pb = ?, prize_won = ?, prize_description = ?, evaluation_date = CURRENT_TIMESTAMP WHERE id = ?",
                    (matches_main, matches_pb, float(prize_amount), prize_description or '', pred_id)
                )
            except Exception as ex:
                logger.error(f"Failed to update prediction {pred_id}: {ex}")

            # Commit per prediction to release write lock early and avoid contention
            try:
                conn.commit()
            except Exception as ex:
                logger.warning(f"Commit failed after processing prediction {pred_id}: {ex}")

        # Final safety commit (most work committed per-iteration already)
        conn.commit()
        conn.close()
        logger.info(f"Evaluated {len(preds)} predictions for draw {draw_date}")
        return True
    except Exception as e:
        logger.error(f"Error evaluating predictions for {draw_date}: {e}")
        return False


def save_generated_tickets(tickets: List[Dict], draw_date: str):
    """Save generated tickets to `generated_tickets` table."""
    if not tickets:
        logger.info("No generated tickets to save")
        return 0

    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()

        records = []
        for t in tickets:
            whites = t.get('white_balls')
            if not whites or len(whites) != 5:
                continue
            records.append((
                draw_date,
                t.get('strategy'),
                int(whites[0]), int(whites[1]), int(whites[2]), int(whites[3]), int(whites[4]),
                int(t.get('powerball', 0)),
                float(t.get('confidence', 0.5))
            ))

        cursor.executemany(
            """
            INSERT INTO generated_tickets (draw_date, strategy_used, n1, n2, n3, n4, n5, powerball, confidence_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records
        )

        conn.commit()
        inserted = cursor.rowcount
        conn.close()
        logger.info(f"Saved {inserted} generated tickets for {draw_date}")
        return inserted
    except Exception as e:
        logger.error(f"Failed to save generated tickets: {e}")
        return 0


async def trigger_full_pipeline_automatically():
    """
    ENHANCED PIPELINE - Full execution with multi-strategy generation and adaptive learning.

    Steps:
    1. DATA: Download latest draw from MUSL API
    2. ANALYTICS: Update co-occurrence matrix and pattern statistics
    3. EVALUATE: Compare previous predictions vs actual results
    4. ADAPTIVE LEARNING: Update strategy weights based on performance
    5. PREDICT: Generate new predictions using balanced strategies
    """
    logger.info("🚀 ========== ENHANCED PIPELINE STARTING ==========")
    execution_id = str(uuid.uuid4())[:8]
    start_time = datetime.now()

    try:
        # STEP 1: DATA - Download latest draw
        logger.info(f"[{execution_id}] STEP 1/5: Downloading latest Powerball data...")
        try:
            new_draws_count = update_database_from_source()
            logger.info(f"[{execution_id}] ✅ Database updated ({new_draws_count} total draws)")
        except Exception as e:
            logger.error(f"[{execution_id}] ❌ Data download failed: {e}")
            # Continue with existing data

        # STEP 2: ANALYTICS - Update statistical tables
        logger.info(f"[{execution_id}] STEP 2/5: Updating analytics (co-occurrence, patterns)...")
        try:
            from src.analytics_engine import update_analytics
            analytics_success = update_analytics()
            if analytics_success:
                logger.info(f"[{execution_id}] ✅ Analytics updated successfully")
            else:
                logger.warning(f"[{execution_id}] ⚠️ Analytics update had warnings")
        except Exception as e:
            logger.error(f"[{execution_id}] ❌ Analytics update failed: {e}")
            logger.info(f"[{execution_id}] Continuing pipeline without updated analytics")

        # STEP 3: EVALUATE - Check previous predictions
        logger.info(f"[{execution_id}] STEP 3/5: Evaluating previous predictions...")
        try:
            latest_draw = db.get_latest_draw_date()
            if latest_draw:
                await evaluate_predictions_for_draw(latest_draw)
                logger.info(f"[{execution_id}] ✅ Evaluated predictions for {latest_draw}")
            else:
                logger.warning(f"[{execution_id}] No draw to evaluate against")
        except Exception as e:
            logger.error(f"[{execution_id}] ❌ Evaluation failed: {e}")

        # STEP 4: ADAPTIVE LEARNING - Update strategy weights
        logger.info(f"[{execution_id}] STEP 4/5: Adaptive learning - updating strategy weights...")
        try:
            await adaptive_learning_update()
            logger.info(f"[{execution_id}] ✅ Strategy weights updated via Bayesian learning")
        except Exception as e:
            logger.error(f"[{execution_id}] ❌ Adaptive learning failed: {e}")
            logger.info(f"[{execution_id}] Continuing with existing weights")

        # STEP 5: PREDICT - Generate new tickets with strategies
        logger.info(f"[{execution_id}] STEP 5/5: Generating predictions with multi-strategy system...")
        try:
            from src.strategy_generators import StrategyManager
            from src.date_utils import DateManager

            manager = StrategyManager()

            # Generate 200 predictions (40 sets of 5 tickets each)
            all_tickets = []
            for batch in range(40):
                tickets = manager.generate_balanced_tickets(5)
                all_tickets.extend(tickets)
                if (batch + 1) % 10 == 0:
                    logger.info(f"[{execution_id}] Generated {len(all_tickets)}/200 tickets...")

            # Save to database
            next_draw = DateManager.calculate_next_drawing_date()
            saved = save_generated_tickets(all_tickets, next_draw)

            logger.info(f"[{execution_id}] ✅ Generated and saved {saved} tickets for {next_draw}")

            # Get strategy distribution
            strategy_dist = {}
            for ticket in all_tickets:
                strategy = ticket['strategy']
                strategy_dist[strategy] = strategy_dist.get(strategy, 0) + 1

            logger.info(f"[{execution_id}] Strategy distribution: {strategy_dist}")

        except Exception as e:
            logger.error(f"[{execution_id}] ❌ Prediction generation failed: {e}")
            logger.exception("Full traceback:")

        # Pipeline completion
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"[{execution_id}] 🎉 ========== ENHANCED PIPELINE COMPLETED in {elapsed:.2f}s ==========")

        return {
            'success': True,
            'execution_id': execution_id,
            'elapsed_seconds': elapsed,
            'message': 'Enhanced pipeline completed successfully'
        }

    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error(f"[{execution_id}] ❌ ========== PIPELINE FAILED after {elapsed:.2f}s ==========")
        logger.exception("Full pipeline error:")

        return {
            'success': False,
            'execution_id': execution_id,
            'elapsed_seconds': elapsed,
            'error': str(e)
        }

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

        cursor.execute("SELECT COUNT(*) FROM generated_tickets")
        total_predictions = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
        premium_users = cursor.fetchone()[0]

        # Total visits (sum of visit_count across unique devices)
        try:
            cursor.execute("SELECT COALESCE(SUM(visit_count), 0) FROM unique_visits")
            total_visits = cursor.fetchone()[0] or 0
        except Exception:
            total_visits = 0

        # Unique visitors (number of distinct device fingerprints)
        try:
            cursor.execute("SELECT COUNT(*) FROM unique_visits")
            unique_visitors = cursor.fetchone()[0] or 0
        except Exception:
            unique_visitors = 0

        # Get latest pipeline execution
        cursor.execute("""
            SELECT created_at, strategy_used 
            FROM generated_tickets 
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
            SELECT COUNT(*) FROM generated_tickets 
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
                "winning_predictions": winning_predictions,
                "total_visits": total_visits,
                "unique_visitors": unique_visitors
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


@api_router.get("/system/overview")
async def get_system_overview():
    """
    Returns Git deployment info and real-time system resource metrics.
    """
    try:
        # Git information via subprocess
        git_info = {
            'commit_hash': None,
            'branch': None,
            'last_message': None,
            'commit_date': None,
            'commit_url': None
        }

        try:
            # Determine repository root based on this file's location (src/..)
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            # Retrieve both short and full commit hashes
            short_hash = subprocess.check_output(['git', 'rev-parse', '--short=7', 'HEAD'], cwd=repo_root, text=True).strip()
            full_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo_root, text=True).strip()
            branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=repo_root, text=True).strip()
            last_message = subprocess.check_output(['git', 'log', '-1', '--pretty=%B'], cwd=repo_root, text=True).strip()
            commit_date = subprocess.check_output(['git', 'log', '-1', '--pretty=%cI'], cwd=repo_root, text=True).strip()

            git_info.update({
                'commit_hash': short_hash,
                'branch': branch,
                'last_message': last_message,
                'commit_date': commit_date,
                'commit_url': f"https://github.com/orlandobatistac/SHIOL-PLUS/commit/{full_hash}"
            })
        except Exception as git_err:
            logger.warning(f"Git info retrieval failed: {git_err}")
            # Fallback 1: Directly parse .git files if present, no git binary required
            try:
                repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
                dot_git = os.path.join(repo_root, '.git')
                head_path = os.path.join(dot_git, 'HEAD')
                short_hash = None
                full_hash = None
                branch = None
                commit_message = None
                commit_date_iso = None
                
                if os.path.exists(head_path):
                    with open(head_path, 'r', encoding='utf-8') as f:
                        head_content = f.read().strip()
                    if head_content.startswith('ref:'):
                        ref = head_content.split(' ', 1)[1].strip()
                        branch = ref.split('/')[-1]
                        ref_file = os.path.join(dot_git, ref)
                        if os.path.exists(ref_file):
                            with open(ref_file, 'r', encoding='utf-8') as rf:
                                full_hash = rf.read().strip()
                    else:
                        # Detached HEAD contains the hash directly
                        full_hash = head_content
                    if full_hash:
                        short_hash = full_hash[:7]
                        
                        # Try to get commit message and date using git cat-file (works with packed objects)
                        try:
                            cat_file_output = subprocess.check_output(
                                ['git', 'cat-file', 'commit', full_hash],
                                cwd=repo_root,
                                text=True,
                                stderr=subprocess.DEVNULL
                            )
                            # Parse the commit object
                            sep = cat_file_output.find('\n\n')
                            if sep != -1:
                                headers = cat_file_output[:sep]
                                commit_message = cat_file_output[sep+2:].strip()
                                # Extract committer date
                                m = re.search(r"committer .* <.*> (\d+) ([+-]\d{4})", headers)
                                if m:
                                    ts = int(m.group(1))
                                    tzs = m.group(2)
                                    sign = 1 if tzs[0] == '+' else -1
                                    hh = int(tzs[1:3]); mm = int(tzs[3:5])
                                    offset = timedelta(hours=hh*sign, minutes=mm*sign)
                                    dt = datetime.fromtimestamp(ts, timezone(offset))
                                    commit_date_iso = dt.isoformat()
                        except Exception:
                            # If git cat-file fails, try parsing loose object directly
                            try:
                                obj_path = os.path.join(dot_git, 'objects', full_hash[:2], full_hash[2:])
                                if os.path.exists(obj_path):
                                    with open(obj_path, 'rb') as of:
                                        raw = of.read()
                                    data = zlib.decompress(raw)
                                    text = data.decode('utf-8', errors='replace')
                                    sep = text.find('\n\n')
                                    headers = text[:sep] if sep != -1 else text
                                    commit_message = text[sep+2:].strip() if sep != -1 else ''
                                    m = re.search(r"committer .* <.*> (\d+) ([+-]\d{4})", headers)
                                    if m:
                                        ts = int(m.group(1))
                                        tzs = m.group(2)
                                        sign = 1 if tzs[0] == '+' else -1
                                        hh = int(tzs[1:3]); mm = int(tzs[3:5])
                                        offset = timedelta(hours=hh*sign, minutes=mm*sign)
                                        dt = datetime.fromtimestamp(ts, timezone(offset))
                                        commit_date_iso = dt.isoformat()
                            except Exception as obj_err:
                                logger.debug(f"Loose object parse failed: {obj_err}")
                
                if short_hash or full_hash or branch:
                    git_info.update({
                        'commit_hash': short_hash,
                        'branch': branch,
                        'last_message': commit_message or git_info.get('last_message'),
                        'commit_date': commit_date_iso or git_info.get('commit_date'),
                        'commit_url': f"https://github.com/orlandobatistac/SHIOL-PLUS/commit/{full_hash}" if full_hash else None
                    })
                # If we still don't have values, continue to env/build fallbacks
            except Exception as parse_err:
                logger.debug(f".git parse fallback failed: {parse_err}")

            # Fallback 2: Environment variables (useful in production deploys without .git)
            env_commit = os.getenv("GIT_COMMIT") or os.getenv("COMMIT_HASH")
            env_branch = os.getenv("GIT_BRANCH") or os.getenv("BRANCH")
            env_message = os.getenv("GIT_COMMIT_MESSAGE")
            env_date = os.getenv("GIT_COMMIT_DATE")

            if env_commit or env_branch or env_message:
                short_hash = (env_commit[:7] if env_commit else None)
                git_info.update({
                    'commit_hash': short_hash,
                    'branch': env_branch,
                    'last_message': env_message,
                    'commit_date': env_date,
                    'commit_url': f"https://github.com/orlandobatistac/SHIOL-PLUS/commit/{env_commit}" if env_commit else None
                })
            else:
                # Fallback 3: read from build info file if present
                try:
                    build_info_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'build_info.json')
                    if os.path.exists(build_info_path):
                        import json
                        with open(build_info_path, 'r', encoding='utf-8') as f:
                            build = json.load(f)
                        env_commit = build.get('commit')
                        git_info.update({
                            'commit_hash': (env_commit[:7] if env_commit else None),
                            'branch': build.get('branch'),
                            'last_message': build.get('message'),
                            'commit_date': build.get('date'),
                            'commit_url': f"https://github.com/orlandobatistac/SHIOL-PLUS/commit/{env_commit}" if env_commit else None
                        })
                except Exception as build_err:
                    logger.debug(f"No build_info.json present or failed to parse: {build_err}")

        # System metrics using psutil
        try:
            virtual_mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            cpu_percent = psutil.cpu_percent(interval=0.5)
            cpu_count = psutil.cpu_count(logical=True)
            disk = shutil.disk_usage('/')

            system_metrics = {
                'memory': {
                    'total': virtual_mem.total,
                    'used': virtual_mem.used,
                    'free': virtual_mem.available,
                    'percent': virtual_mem.percent
                },
                'swap': {
                    'total': swap.total,
                    'used': swap.used,
                    'free': swap.free,
                    'percent': swap.percent,
                    'active': swap.total > 0
                },
                'cpu': {
                    'percent': cpu_percent,
                    'cores': cpu_count
                },
                'disk': {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': round((disk.used / disk.total) * 100, 1) if disk.total else 0
                },
                'platform': platform.platform()
            }
        except Exception as sys_err:
            logger.warning(f"System metrics retrieval failed: {sys_err}")
            system_metrics = {'error': str(sys_err)}

        return {
            'git': git_info,
            'system_metrics': system_metrics,
            'timestamp': datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in system overview endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
app.include_router(admin_router)  # Admin endpoints
app.include_router(prediction_router, prefix="/api/v1/predictions")
app.include_router(draw_router, prefix="/api/v1/draws")
app.include_router(ticket_router)  # Ticket verification endpoints
app.include_router(public_frontend_router)

# Serve default /favicon.ico from static assets to avoid 404 when not present at root
from fastapi.responses import FileResponse

@app.get("/favicon.ico")
async def favicon_route():
    try:
        icon_path = os.path.join(FRONTEND_DIR, "static", "favicon.ico")
        if os.path.exists(icon_path):
            return FileResponse(icon_path, media_type="image/x-icon")
    except Exception:
        pass
    raise HTTPException(status_code=404, detail="favicon not found")

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

# Legal policy pages (before catch-all mount)
@app.get("/privacy", response_class=Response)
async def privacy_page():
    """Serve privacy policy page"""
    privacy_path = os.path.join(FRONTEND_DIR, "privacy.html")
    if os.path.exists(privacy_path):
        with open(privacy_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return Response(content=content, media_type="text/html")
    else:
        raise HTTPException(status_code=404, detail="Privacy policy page not found")

@app.get("/terms", response_class=Response)
async def terms_page():
    """Serve terms of service page"""
    terms_path = os.path.join(FRONTEND_DIR, "terms.html")
    if os.path.exists(terms_path):
        with open(terms_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return Response(content=content, media_type="text/html")
    else:
        raise HTTPException(status_code=404, detail="Terms of service page not found")

@app.get("/cookies", response_class=Response)
async def cookies_page():
    """Serve cookie policy page"""
    cookies_path = os.path.join(FRONTEND_DIR, "cookies.html")
    if os.path.exists(cookies_path):
        with open(cookies_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return Response(content=content, media_type="text/html")
    else:
        raise HTTPException(status_code=404, detail="Cookie policy page not found")

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
