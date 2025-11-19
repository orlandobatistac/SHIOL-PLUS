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
import json
import signal
import sys

from src.predictor import Predictor
from src.intelligent_generator import IntelligentGenerator, DeterministicGenerator
from src.loader import realtime_draw_polling_unified, daily_full_sync_job
import src.database as db
# from src.adaptive_feedback import initialize_adaptive_system  # REMOVED
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from contextlib import asynccontextmanager
import pytz
from starlette.responses import Response
from fastapi.responses import JSONResponse

# Import remaining API components (simplified)
from src.api_prediction_endpoints import prediction_router, draw_router, set_prediction_components
from src.api_public_endpoints import public_frontend_router, set_public_components
from src.api_ticket_endpoints import ticket_router
from src.api_auth_endpoints import auth_router
from src.api_admin_endpoints import router as admin_router
from src.api_batch_endpoints import batch_router
import psutil
import shutil
import platform

# --- Pipeline Monitoring Global Variables ---
# Global variables for pipeline monitoring
# Pipeline orchestrator deprecated and removed
pipeline_executions = {}  # Track running pipeline executions
pipeline_logs = []  # Store recent pipeline logs
active_pipeline_execution_id = None  # Track currently running pipeline for graceful shutdown

# --- Scheduler and App Lifecycle ---
# Configure persistent jobstore using SQLite
# Use relative path from project root for portability (Replit/VPS)
scheduler_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'scheduler.db')
scheduler_db_url = f'sqlite:///{scheduler_db_path}'

jobstores = {
    'default': SQLAlchemyJobStore(url=scheduler_db_url)
}

# Configure asyncio-aware executor so async jobs are awaited properly
executors = {
    'default': AsyncIOExecutor()
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

# Track scheduler start time for uptime reporting
SCHEDULER_START_TIME_UTC = None

# REMOVED: update_data_automatically() - replaced by daily_full_sync_job in scheduler

def recover_stale_pipelines():
    """Recovery function to clean up pipelines stuck in 'running' state on startup.
    
    This handles cases where:
    - Process was killed by systemd (SIGKILL) during restart
    - Server crashed while pipeline was running
    - Process terminated unexpectedly without updating status
    """
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()
        
        # Find pipelines stuck in 'running' state
        cursor.execute(
            "SELECT execution_id, start_time, current_step FROM pipeline_execution_logs "
            "WHERE status = 'running'"
        )
        stale_pipelines = cursor.fetchall()
        
        if not stale_pipelines:
            logger.info("✅ No stale pipelines found - recovery check passed")
            return
        
        # Mark all stale pipelines as failed (recovered from stuck state)
        for exec_id, start_time, current_step in stale_pipelines:
            cursor.execute(
                "UPDATE pipeline_execution_logs SET status='failed', "
                "end_time=?, error='FAILED: Pipeline stuck in running state - recovered on restart' "
                "WHERE execution_id=?",
                (datetime.now().isoformat(), exec_id)
            )
            logger.warning(
                f"🔧 Recovered stale pipeline {exec_id} (started: {start_time}, "
                f"step: {current_step})"
            )
        
        conn.commit()
        logger.info(f"✅ Recovery complete - cleaned up {len(stale_pipelines)} stale pipeline(s)")
        
    except Exception as e:
        logger.error(f"❌ Pipeline recovery failed: {e}", exc_info=True)

def signal_handler(signum, frame):
    """Handle SIGTERM gracefully by updating pipeline status before shutdown.
    
    This prevents pipelines from getting stuck in 'running' state when systemd
    restarts the service.
    """
    global active_pipeline_execution_id
    
    signal_name = 'SIGTERM' if signum == signal.SIGTERM else f'Signal {signum}'
    logger.warning(f"⚠️  Received {signal_name} - attempting graceful shutdown...")
    
    if active_pipeline_execution_id:
        try:
            conn = db.get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE pipeline_execution_logs SET status='failed', "
                "end_time=?, error='FAILED: Pipeline interrupted by system signal (graceful shutdown)' "
                "WHERE execution_id=?",
                (datetime.now().isoformat(), active_pipeline_execution_id)
            )
            conn.commit()
            logger.info(
                f"✅ Pipeline {active_pipeline_execution_id} marked as FAILED "
                f"(interrupted before shutdown)"
            )
        except Exception as e:
            logger.error(f"❌ Failed to update pipeline status on shutdown: {e}")
    
    # Allow default signal handling to proceed
    sys.exit(0)

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

async def adaptive_learning_update():
    """Update strategy weights based on recent performance using a simple empirical Bayes-like update.

    This reads `strategy_performance` table and updates `current_weight` and `confidence`.
    """
    try:
        with db.get_db_connection() as conn:
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
            logger.info("Adaptive learning update: strategy weights updated")
            return True
    except Exception as e:
        logger.error(f"Adaptive learning update failed: {e}")
        return False


async def evaluate_predictions_for_draw(draw_date: str):
    """Evaluate predictions for a specific draw date and record performance."""
    try:
        with db.get_db_connection() as conn:
            cursor = conn.cursor()

            # Get official result
            cursor.execute("SELECT n1, n2, n3, n4, n5, pb FROM powerball_draws WHERE draw_date = ?", (draw_date,))
            official = cursor.fetchone()
            if not official:
                logger.warning(f"No official draw found for {draw_date}")
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
            logger.info(f"Evaluated {len(preds)} predictions for draw {draw_date}")
            return True
    except Exception as e:
        logger.error(f"Error evaluating predictions for {draw_date}: {e}")
        return False


def save_generated_tickets(tickets: List[Dict], draw_date: str):
    """
    Save generated tickets to `generated_tickets` table.
    
    Behavior: Does NOT delete existing tickets - appends to them.
    This allows batch-wise saving during pipeline execution.
    Note: The pipeline itself deletes old tickets BEFORE starting generation.
    """
    if not tickets:
        logger.debug(f"No tickets to save for {draw_date}")
        return 0

    try:
        with db.get_db_connection() as conn:
            cursor = conn.cursor()

            # Prepare new records
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

            # Insert new tickets
            cursor.executemany(
                """
                INSERT INTO generated_tickets (draw_date, strategy_used, n1, n2, n3, n4, n5, powerball, confidence_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                records
            )

            conn.commit()
            inserted = cursor.rowcount
            logger.debug(f"Saved {inserted} tickets for {draw_date}")
            return inserted
    except Exception as e:
        logger.error(f"Failed to save generated tickets: {e}")
        return 0


# ========== PIPELINE VALIDATION FUNCTIONS ==========

def validate_step_1_data_download(new_draws_count: int, execution_id: str) -> Dict:
    """
    Validate STEP 1: Data download from NC Lottery sources.
    
    Success criteria:
    - new_draws_count > 0 (new data fetched)
    - OR latest_draw_date is same day as today (re-run scenario, data already fresh)
    
    Returns:
        dict: {'success': bool, 'error': str or None, 'details': dict}
    """
    try:
        latest_draw = db.get_latest_draw_date()
        from src.date_utils import DateManager
        current_et = DateManager.get_current_et_time()
        current_date_et = current_et.date()
        
        if new_draws_count > 0:
            logger.info(f"[{execution_id}] ✅ STEP 1 VALID: {new_draws_count} total draws in DB")
            return {
                'success': True,
                'error': None,
                'details': {
                    'new_draws_count': new_draws_count,
                    'latest_draw': latest_draw,
                    'validation': 'new_data_fetched'
                }
            }
        
        # Check if latest draw is same-day (re-run scenario)
        if latest_draw:
            from datetime import datetime
            latest_draw_dt = datetime.strptime(latest_draw, "%Y-%m-%d").date()
            
            # Same-day scenario: pipeline re-run with fresh data already in DB
            if latest_draw_dt == current_date_et:
                logger.info(f"[{execution_id}] ✅ STEP 1 VALID: Latest draw {latest_draw} is same-day (re-run scenario)")
                return {
                    'success': True,
                    'error': None,
                    'details': {
                        'new_draws_count': new_draws_count,
                        'latest_draw': latest_draw,
                        'validation': 'same_day_rerun'
                    }
                }
        
        # Failure: no new draws and not a same-day scenario
        error_msg = f"No new draws fetched and latest draw {latest_draw} is stale (API delay or network issue)"
        logger.error(f"[{execution_id}] ❌ STEP 1 FAILED: {error_msg}")
        return {
            'success': False,
            'error': error_msg,
            'details': {
                'new_draws_count': new_draws_count,
                'latest_draw': latest_draw,
                'current_date_et': str(current_date_et)
            }
        }
        
    except Exception as e:
        error_msg = f"Validation exception: {str(e)}"
        logger.error(f"[{execution_id}] ❌ STEP 1 VALIDATION ERROR: {error_msg}")
        return {
            'success': False,
            'error': error_msg,
            'details': {'exception': str(e)}
        }


def validate_step_2_analytics(execution_id: str) -> Dict:
    """
    Validate STEP 2: Analytics update (co-occurrence matrix + pattern statistics).
    
    Success criteria:
    - cooccurrences table has rows (> 0)
    - pattern_stats table has rows (> 0)
    
    Returns:
        dict: {'success': bool, 'error': str or None, 'details': dict}
    """
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM cooccurrences")
        cooccurrence_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM pattern_stats")
        pattern_count = cursor.fetchone()[0]
        
        conn.close()
        
        if cooccurrence_count > 0 and pattern_count > 0:
            logger.info(f"[{execution_id}] ✅ STEP 2 VALID: {cooccurrence_count} co-occurrences, {pattern_count} patterns")
            return {
                'success': True,
                'error': None,
                'details': {
                    'cooccurrence_count': cooccurrence_count,
                    'pattern_count': pattern_count
                }
            }
        else:
            error_msg = f"Analytics tables empty: cooccurrences={cooccurrence_count}, patterns={pattern_count}"
            logger.error(f"[{execution_id}] ❌ STEP 2 FAILED: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'details': {
                    'cooccurrence_count': cooccurrence_count,
                    'pattern_count': pattern_count
                }
            }
    except Exception as e:
        error_msg = f"Validation exception: {str(e)}"
        logger.error(f"[{execution_id}] ❌ STEP 2 VALIDATION ERROR: {error_msg}")
        return {
            'success': False,
            'error': error_msg,
            'details': {'exception': str(e)}
        }


def validate_step_3_evaluation(execution_id: str, latest_draw: str) -> Dict:
    """
    Validate STEP 3: Prediction evaluation.
    
    Success criteria:
    - Step always succeeds (evaluation is informational, not critical)
    - Log warning if no predictions to evaluate
    
    Returns:
        dict: {'success': bool, 'error': str or None, 'details': dict}
    """
    try:
        if not latest_draw:
            logger.warning(f"[{execution_id}] ⚠️ STEP 3: No draw to evaluate against (informational)")
            return {
                'success': True,
                'error': None,
                'details': {'latest_draw': None, 'note': 'No draw available for evaluation'}
            }
        
        logger.info(f"[{execution_id}] ✅ STEP 3 VALID: Evaluation completed for {latest_draw}")
        return {
            'success': True,
            'error': None,
            'details': {'latest_draw': latest_draw}
        }
    except Exception as e:
        error_msg = f"Validation exception: {str(e)}"
        logger.error(f"[{execution_id}] ❌ STEP 3 VALIDATION ERROR: {error_msg}")
        return {
            'success': False,
            'error': error_msg,
            'details': {'exception': str(e)}
        }


def validate_step_4_adaptive_learning(execution_id: str) -> Dict:
    """
    Validate STEP 4: Adaptive learning (strategy weight updates).
    
    Success criteria:
    - strategy_performance table has rows (> 0)
    - All strategies have current_weight between 0.0 and 1.0
    
    Returns:
        dict: {'success': bool, 'error': str or None, 'details': dict}
    """
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM strategy_performance")
        strategy_count = cursor.fetchone()[0]
        
        if strategy_count == 0:
            conn.close()
            error_msg = "strategy_performance table is empty"
            logger.error(f"[{execution_id}] ❌ STEP 4 FAILED: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'details': {'strategy_count': 0}
            }
        
        cursor.execute("SELECT strategy_name, current_weight FROM strategy_performance")
        strategies = cursor.fetchall()
        conn.close()
        
        invalid_weights = [s for s in strategies if not (0.0 <= s[1] <= 1.0)]
        if invalid_weights:
            error_msg = f"Invalid strategy weights detected: {invalid_weights}"
            logger.error(f"[{execution_id}] ❌ STEP 4 FAILED: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'details': {'invalid_weights': [s[0] for s in invalid_weights]}
            }
        
        logger.info(f"[{execution_id}] ✅ STEP 4 VALID: {strategy_count} strategies with valid weights")
        return {
            'success': True,
            'error': None,
            'details': {'strategy_count': strategy_count}
        }
    except Exception as e:
        error_msg = f"Validation exception: {str(e)}"
        logger.error(f"[{execution_id}] ❌ STEP 4 VALIDATION ERROR: {error_msg}")
        return {
            'success': False,
            'error': error_msg,
            'details': {'exception': str(e)}
        }


def validate_step_5_prediction(saved_count: int, expected_count: int, execution_id: str) -> Dict:
    """
    Validate STEP 5: Prediction generation and saving.
    
    Success criteria:
    - saved_count == expected_count (all tickets saved successfully)
    
    Returns:
        dict: {'success': bool, 'error': str or None, 'details': dict}
    """
    try:
        if saved_count == expected_count:
            logger.info(f"[{execution_id}] ✅ STEP 5 VALID: {saved_count}/{expected_count} tickets saved")
            return {
                'success': True,
                'error': None,
                'details': {
                    'saved_count': saved_count,
                    'expected_count': expected_count
                }
            }
        else:
            error_msg = f"Ticket count mismatch: saved {saved_count}/{expected_count}"
            logger.error(f"[{execution_id}] ❌ STEP 5 FAILED: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'details': {
                    'saved_count': saved_count,
                    'expected_count': expected_count
                }
            }
    except Exception as e:
        error_msg = f"Validation exception: {str(e)}"
        logger.error(f"[{execution_id}] ❌ STEP 5 VALIDATION ERROR: {error_msg}")
        return {
            'success': False,
            'error': error_msg,
            'details': {'exception': str(e)}
        }


async def trigger_full_pipeline_automatically():
    """
    SYNC-FIRST PIPELINE v5.0 - Enhanced with pre-sync and comprehensive evaluation
    
    NEW ARCHITECTURE (November 2025 v5.0):
    - STEP 1A: Daily sync FIRST (ensures DB is updated before polling)
    - STEP 1B: Check if draw exists in DB (skip polling if already there)
    - STEP 1C: Adaptive polling only if needed (Web → MUSL → NC CSV)
    - STEP 4: Comprehensive evaluation of ALL draws (with and without predictions)
    - 7 total steps vs 6 in v4.0
    
    Benefits over v4.0:
    - More efficient: Avoids unnecessary polling if CSV already has data
    - More complete: Evaluates ALL historical draws, not just latest
    - More robust: Daily sync catches gaps before attempting real-time polling
    
    Pipeline halts immediately if any critical step fails validation.
    All errors are logged to pipeline_execution_logs with detailed context.

    Steps:
    1A. DAILY SYNC: Download complete CSV and update DB (PRE-POLLING)
    1B. DB CHECK: Verify if expected draw already exists in DB
    1C. ADAPTIVE POLLING: Only if draw NOT in DB (Web → MUSL → NC CSV)
    2. DATA INSERT: Insert draw from polling if needed (CRITICAL if from polling)
    3. ANALYTICS: Update co-occurrence matrix and pattern statistics (CRITICAL)
    4. COMPREHENSIVE EVALUATION: Evaluate ALL draws with/without predictions (NOW PRIORITIZED)
    5. ADAPTIVE LEARNING: Update strategy weights based on performance (CRITICAL)
    6. PREDICT: Generate new predictions using balanced strategies (CRITICAL)
    """
    global active_pipeline_execution_id
    
    logger.info("🚀 ========== SYNC-FIRST PIPELINE v5.0 STARTING ==========")
    execution_id = str(uuid.uuid4())[:8]
    active_pipeline_execution_id = execution_id  # Track for graceful shutdown
    start_time = datetime.now()
    start_time_iso = start_time.isoformat()
    
    # Calculate expected draw date for polling
    from src.date_utils import DateManager
    
    # Get the last draw in database
    last_draw_in_db = db.get_latest_draw_date()
    
    # Determine which draw the pipeline should fetch
    # This will return the most recent draw that should exist but might be missing from DB
    expected_draw_date = DateManager.get_expected_draw_for_pipeline(last_draw_in_db)
    
    if not expected_draw_date:
        logger.error(f"[{execution_id}] 🚨 PIPELINE STATUS: FAILED")
        logger.error(f"[{execution_id}] ❌ Could not determine expected draw date")
        db.insert_pipeline_execution_log(
            execution_id=execution_id,
            start_time=start_time_iso,
            status="failed",
            current_step="❌ FAILED",
            error="FAILED: Could not determine expected draw date",
            metadata=json.dumps({"trigger": "automated", "version": "v5.0-sync-first"})
        )
        active_pipeline_execution_id = None
        return {
            'success': False,
            'status': 'failed',
            'execution_id': execution_id,
            'error': 'Could not determine expected draw date'
        }
    
    logger.info(f"[{execution_id}] Last draw in DB: {last_draw_in_db}, Expected draw: {expected_draw_date}")
    
    # Insert initial log entry
    db.insert_pipeline_execution_log(
        execution_id=execution_id,
        start_time=start_time_iso,
        metadata=json.dumps({
            "trigger": "automated",
            "version": "v4.0-unified-polling",
            "expected_draw_date": expected_draw_date
        })
    )

    try:
        # ========== STEP 1A: DAILY SYNC FIRST (ENSURE DB IS UPDATED) ==========
        logger.info(f"[{execution_id}] 🔄 STEP 1A/7: Daily Sync - Update DB with CSV...")
        logger.info(f"[{execution_id}]   Downloading complete NC Lottery CSV before polling")
        
        db.update_pipeline_execution_log(
            execution_id=execution_id,
            current_step="STEP 1A/7: Daily Sync (pre-polling)",
            steps_completed=0
        )
        
        sync_start = datetime.now()
        
        try:
            # Execute daily sync to ensure DB has latest draws
            sync_result = daily_full_sync_job()
            sync_elapsed = (datetime.now() - sync_start).total_seconds()
            
            logger.info(
                f"[{execution_id}] ✅ STEP 1A Complete: Daily sync finished "
                f"({sync_result.get('draws_inserted', 0)} draws inserted, {sync_elapsed:.1f}s)"
            )
            
            # Update metadata
            metadata = {
                "trigger": "automated",
                "version": "v5.0-sync-first-polling",
                "expected_draw_date": expected_draw_date,
                "daily_sync_summary": {
                    "success": sync_result.get('success', False),
                    "draws_fetched": sync_result.get('draws_fetched', 0),
                    "draws_inserted": sync_result.get('draws_inserted', 0),
                    "elapsed_seconds": sync_elapsed
                }
            }
            
        except Exception as e:
            # Daily sync failed, but continue with polling (non-critical)
            logger.warning(f"[{execution_id}] ⚠️ STEP 1A Daily Sync failed (continuing): {e}")
            sync_elapsed = (datetime.now() - sync_start).total_seconds()
            metadata = {
                "trigger": "automated",
                "version": "v5.0-sync-first-polling",
                "expected_draw_date": expected_draw_date,
                "daily_sync_summary": {
                    "success": False,
                    "error": str(e),
                    "elapsed_seconds": sync_elapsed
                }
            }
        
        # ========== STEP 1B: CHECK IF DRAW ALREADY IN DB ==========
        logger.info(f"[{execution_id}] 🔍 STEP 1B/7: Checking if draw {expected_draw_date} exists in DB...")
        
        db.update_pipeline_execution_log(
            execution_id=execution_id,
            current_step="STEP 1B/7: Check DB for draw",
            steps_completed=0,
            metadata=json.dumps(metadata)
        )
        
        # Check if draw exists in database
        from src.database import get_db_connection
        draw_in_db = None
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT draw_date, n1, n2, n3, n4, n5, pb FROM powerball_draws WHERE draw_date = ?",
                (expected_draw_date,)
            )
            result = cursor.fetchone()
            if result:
                draw_in_db = {
                    'draw_date': result[0],
                    'n1': result[1],
                    'n2': result[2],
                    'n3': result[3],
                    'n4': result[4],
                    'n5': result[5],
                    'pb': result[6],
                    'source': 'database'
                }
        
        if draw_in_db:
            # Draw already in DB - skip polling
            logger.info(
                f"[{execution_id}] ✅ STEP 1B Complete: Draw {expected_draw_date} already in DB (skip polling)"
            )
            logger.info(
                f"[{execution_id}]   Draw: [{draw_in_db['n1']}, {draw_in_db['n2']}, {draw_in_db['n3']}, "
                f"{draw_in_db['n4']}, {draw_in_db['n5']}] + PB {draw_in_db['pb']}"
            )
            
            draw_data = draw_in_db
            data_source = 'database'
            
            # Update metadata
            metadata['polling_summary'] = {
                "enabled": False,
                "result": "skipped",
                "source": "database",
                "reason": "Draw already exists in DB after daily sync",
                "elapsed_seconds": 0
            }
            
            db.update_pipeline_execution_log(
                execution_id=execution_id,
                current_step="STEP 1B/7: Draw found in DB",
                steps_completed=1,
                metadata=json.dumps(metadata)
            )
            
        else:
            # Draw NOT in DB - validate draw time has passed before polling
            logger.info(f"[{execution_id}] 🔍 STEP 1C/7: Draw not in DB, validating draw time...")
            
            # Validate that the expected draw time has passed
            # If it hasn't, skip polling and exit gracefully
            from datetime import datetime as dt_class
            current_et = DateManager.get_current_et_time()
            expected_draw_dt = dt_class.strptime(expected_draw_date, '%Y-%m-%d')
            
            # Draw time is 10:59 PM ET on the draw date
            draw_time_et = DateManager.POWERBALL_TIMEZONE.localize(
                expected_draw_dt.replace(hour=22, minute=59, second=0)
            )
            
            time_until_draw = (draw_time_et - current_et).total_seconds()
            
            if time_until_draw > 0:
                # Draw hasn't happened yet - skip polling and exit gracefully
                hours_until = time_until_draw / 3600
                logger.warning(f"[{execution_id}] ⏰ STEP 1C SKIPPED: Draw {expected_draw_date} hasn't occurred yet")
                logger.warning(f"[{execution_id}]   Current time: {current_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                logger.warning(f"[{execution_id}]   Draw time: {draw_time_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                logger.warning(f"[{execution_id}]   Time until draw: {hours_until:.1f} hours")
                logger.warning(f"[{execution_id}]   Pipeline will exit gracefully - scheduler will retry after draw")
                
                elapsed = (datetime.now() - start_time).total_seconds()
                
                metadata['polling_summary'] = {
                    "enabled": False,
                    "result": "skipped_future_draw",
                    "reason": f"Draw time not reached - {hours_until:.1f} hours until draw",
                    "current_time_et": current_et.isoformat(),
                    "draw_time_et": draw_time_et.isoformat(),
                    "hours_until_draw": hours_until
                }
                
                db.update_pipeline_execution_log(
                    execution_id=execution_id,
                    status="completed",
                    current_step="✅ COMPLETED (draw not ready yet)",
                    end_time=datetime.now().isoformat(),
                    elapsed_seconds=elapsed,
                    steps_completed=1,
                    metadata=json.dumps(metadata)
                )
                
                active_pipeline_execution_id = None
                logger.info(f"[{execution_id}] 🚀 PIPELINE STATUS: COMPLETED (graceful exit - draw not ready)")
                
                return {
                    'success': True,
                    'status': 'completed',
                    'execution_id': execution_id,
                    'result': 'draw_not_ready',
                    'message': f'Draw {expected_draw_date} has not occurred yet - will retry after draw time',
                    'hours_until_draw': hours_until,
                    'elapsed_seconds': elapsed
                }
            
            # Draw time has passed - proceed with polling
            logger.info(f"[{execution_id}] ✅ Draw time validation passed - draw {expected_draw_date} should be available")
            logger.info(f"[{execution_id}]   Draw was {abs(time_until_draw) / 3600:.1f} hours ago")
            logger.info(f"[{execution_id}]   Starting adaptive polling...")
            logger.info(f"[{execution_id}]   Strategy: NC Lottery Scraping → MUSL API → NC CSV (3-layer fallback)")
            
            db.update_pipeline_execution_log(
                execution_id=execution_id,
                current_step="STEP 1C/7: Adaptive Polling",
                steps_completed=0,
                metadata=json.dumps(metadata)
            )
            
            polling_start = datetime.now()
            
            try:
                # Define callback function to update pipeline status during polling
                def update_polling_status(exec_id, status_msg):
                    """Update pipeline execution log with current polling status."""
                    db.update_pipeline_execution_log(
                        execution_id=exec_id,
                        current_step=status_msg,
                        metadata=json.dumps(metadata)
                    )
                
                # Execute unified adaptive polling with status updates
                polling_result = realtime_draw_polling_unified(
                    expected_draw_date=expected_draw_date,
                    execution_id=execution_id,
                    update_status_callback=update_polling_status
                )
                
                polling_elapsed = (datetime.now() - polling_start).total_seconds()
                
                # Check if polling succeeded
                if not polling_result['success']:
                    # Polling timeout - HALT PIPELINE
                    error_detail = f"Polling timeout after {polling_elapsed/60:.1f} minutes"
                    logger.error(f"[{execution_id}] 🚨 PIPELINE STATUS: FAILED")
                    logger.error(f"[{execution_id}] ❌ STEP 1C TIMEOUT: {error_detail}")
                    
                    elapsed = (datetime.now() - start_time).total_seconds()
                    db.update_pipeline_execution_log(
                        execution_id=execution_id,
                        status="failed",
                        current_step="❌ FAILED at STEP 1C/7",
                        end_time=datetime.now().isoformat(),
                        error=f"FAILED: STEP 1C TIMEOUT - {error_detail}",
                        elapsed_seconds=elapsed,
                        metadata=json.dumps(metadata)
                    )
                    
                    active_pipeline_execution_id = None
                    return {
                        'success': False,
                        'status': 'failed',
                        'execution_id': execution_id,
                        'failed_step': 'STEP 1C: Adaptive Polling',
                        'error': error_detail,
                        'elapsed_seconds': elapsed
                    }
                
                # Polling SUCCESS - extract draw data
                draw_data = polling_result['draw_data']
                data_source = polling_result['source']
                
                logger.info(
                    f"[{execution_id}] ✅ STEP 1C Complete: Data fetched from {data_source.upper()} "
                    f"after {polling_result['attempts']} attempts ({polling_elapsed:.1f}s / {polling_elapsed/60:.1f}min)"
                )
                logger.info(
                    f"[{execution_id}]   Draw {expected_draw_date}: "
                    f"[{draw_data['n1']}, {draw_data['n2']}, {draw_data['n3']}, {draw_data['n4']}, {draw_data['n5']}] + PB {draw_data['pb']}"
                )
                
                # Update metadata with polling summary
                metadata['polling_summary'] = {
                    "enabled": True,
                    "result": polling_result['result'],
                    "source": data_source,
                    "attempts": polling_result['attempts'],
                    "elapsed_seconds": polling_elapsed,
                    "started_at": polling_start.isoformat(),
                    "completed_at": datetime.now().isoformat()
                }
                
                db.update_pipeline_execution_log(
                    execution_id=execution_id,
                    current_step="STEP 1C/7: Polling complete",
                    steps_completed=1,
                    metadata=json.dumps(metadata)
                )
                
            except Exception as e:
                # STEP 1C POLLING EXCEPTION - HALT PIPELINE
                logger.error(f"[{execution_id}] 🚨 STEP 1C POLLING EXCEPTION: {e}")
                logger.exception("Full traceback:")
                
                elapsed = (datetime.now() - start_time).total_seconds()
                db.update_pipeline_execution_log(
                    execution_id=execution_id,
                    status="failed",
                    current_step="FAILED at STEP 1C/7",
                    end_time=datetime.now().isoformat(),
                    error=f"STEP 1C EXCEPTION: {str(e)}",
                    elapsed_seconds=elapsed
                )
                
                return {
                    'success': False,
                    'execution_id': execution_id,
                    'failed_step': 'STEP 1C: Adaptive Polling',
                    'error': str(e),
                    'elapsed_seconds': elapsed
                }

        # ========== STEP 2: INSERT DRAW INTO DATABASE (CRITICAL IF FROM POLLING) ==========
        logger.info(f"[{execution_id}] STEP 2/7: Inserting draw into database...")
        db.update_pipeline_execution_log(
            execution_id=execution_id,
            current_step="STEP 2/7: Database insert",
            steps_completed=1
        )
        
        try:
            # Only insert if draw came from polling (not from DB)
            if data_source != 'database':
                # Insert the fetched draw (convert to DataFrame first)
                from src.database import bulk_insert_draws
                import pandas as pd
                
                # Filter to only include columns that exist in powerball_draws table
                # (remove 'multiplier' and 'source' which are metadata fields)
                required_columns = ['draw_date', 'n1', 'n2', 'n3', 'n4', 'n5', 'pb']
                draw_record = {k: draw_data[k] for k in required_columns if k in draw_data}
                
                draw_df = pd.DataFrame([draw_record])
                inserted_count = bulk_insert_draws(draw_df)
                
                logger.info(f"[{execution_id}] ✅ STEP 2 Complete: Inserted {inserted_count} draw(s) into database")
            else:
                # Draw was already in DB, skip insert
                inserted_count = 0
                logger.info(f"[{execution_id}] ✅ STEP 2 Complete: Draw already in database (skipped insert)")
            
            # Update metadata
            metadata['inserted_draws'] = inserted_count
            
            db.update_pipeline_execution_log(
                execution_id=execution_id,
                steps_completed=2,
                metadata=json.dumps(metadata)
            )
            
        except Exception as e:
            # EXCEPTION DURING STEP 2 - HALT PIPELINE
            logger.error(f"[{execution_id}] 🚨 PIPELINE STATUS: FAILED")
            logger.error(f"[{execution_id}] ❌ STEP 2 EXCEPTION: {e}")
            logger.exception("Full traceback:")
            
            elapsed = (datetime.now() - start_time).total_seconds()
            db.update_pipeline_execution_log(
                execution_id=execution_id,
                status="failed",
                current_step="❌ FAILED at STEP 2/6",
                end_time=datetime.now().isoformat(),
                error=f"FAILED: STEP 2 EXCEPTION - {str(e)}",
                elapsed_seconds=elapsed
            )
            
            active_pipeline_execution_id = None
            return {
                'success': False,
                'status': 'failed',
                'execution_id': execution_id,
                'failed_step': 'STEP 2: Database insert',
                'error': str(e),
                'elapsed_seconds': elapsed
            }

        # ========== STEP 3: ANALYTICS UPDATE (CRITICAL) ==========
        logger.info(f"[{execution_id}] STEP 3/6: Updating analytics (co-occurrence, patterns)...")
        db.update_pipeline_execution_log(
            execution_id=execution_id,
            current_step="STEP 3/6: Analytics update",
            steps_completed=2  # STEP 1 (polling) + STEP 2 (insert) = 2 steps completed before this
        )
        
        try:
            from src.analytics_engine import update_analytics
            analytics_success = update_analytics()
            
            if not analytics_success:
                logger.warning(f"[{execution_id}] Analytics update returned False")
            
            # VALIDATION GATE 2
            validation_result = validate_step_2_analytics(execution_id)
            
            if not validation_result['success']:
                # CRITICAL FAILURE - HALT PIPELINE
                error_detail = validation_result['error']
                logger.error(f"[{execution_id}] 🚨 PIPELINE STATUS: FAILED")
                logger.error(f"[{execution_id}] ❌ STEP 3 VALIDATION FAILED: {error_detail}")
                
                elapsed = (datetime.now() - start_time).total_seconds()
                db.update_pipeline_execution_log(
                    execution_id=execution_id,
                    status="failed",
                    current_step="❌ FAILED at STEP 3/6",
                    end_time=datetime.now().isoformat(),
                    error=f"FAILED: STEP 3 VALIDATION - {error_detail}",
                    elapsed_seconds=elapsed
                )
                
                active_pipeline_execution_id = None
                return {
                    'success': False,
                    'status': 'failed',
                    'execution_id': execution_id,
                    'failed_step': 'STEP 3: Analytics update',
                    'error': error_detail,
                    'elapsed_seconds': elapsed
                }
            
            # Success - continue
            db.update_pipeline_execution_log(
                execution_id=execution_id,
                steps_completed=3
            )
            
        except Exception as e:
            # EXCEPTION DURING STEP 3 - HALT PIPELINE
            logger.error(f"[{execution_id}] 🚨 PIPELINE STATUS: FAILED")
            logger.error(f"[{execution_id}] ❌ STEP 3 EXCEPTION: {e}")
            logger.exception("Full traceback:")
            
            elapsed = (datetime.now() - start_time).total_seconds()
            db.update_pipeline_execution_log(
                execution_id=execution_id,
                status="failed",
                current_step="❌ FAILED at STEP 3/6",
                end_time=datetime.now().isoformat(),
                error=f"FAILED: STEP 3 EXCEPTION - {str(e)}",
                elapsed_seconds=elapsed
            )
            
            active_pipeline_execution_id = None
            return {
                'success': False,
                'status': 'failed',
                'execution_id': execution_id,
                'failed_step': 'STEP 3: Analytics update',
                'error': str(e),
                'elapsed_seconds': elapsed
            }

        # ========== STEP 4: COMPREHENSIVE EVALUATION (CRITICAL - NOW PRIORITIZED) ==========
        logger.info(f"[{execution_id}] STEP 4/7: Evaluation - Recent draws with predictions...")
        logger.info(f"[{execution_id}]   Evaluating draws that have pending predictions")
        db.update_pipeline_execution_log(
            execution_id=execution_id,
            current_step="STEP 4/7: Evaluation of pending predictions",
            steps_completed=3
        )
        
        try:
            # Get ONLY draws that have UNEVALUATED predictions (not all draws)
            # This prevents the pipeline from processing thousands of historical draws
            from src.database import get_db_connection
            
            with get_db_connection() as conn:
                cursor = conn.cursor()
                # Get draws with PENDING/UNEVALUATED predictions only (evaluated = 0)
                cursor.execute("""
                    SELECT DISTINCT draw_date
                    FROM generated_tickets 
                    WHERE evaluated = 0
                    ORDER BY draw_date DESC
                    LIMIT 100
                """)
                draws_with_pending = cursor.fetchall()
            
            logger.info(f"[{execution_id}] Found {len(draws_with_pending)} draws with pending predictions to evaluate")
            
            evaluated_count = 0
            error_count = 0
            
            # Process only draws with pending predictions (timeout: 5 mins max for this step)
            step_start = datetime.now()
            step_timeout = 300  # 5 minutes
            
            for draw_tuple in draws_with_pending:
                draw_date = draw_tuple[0]
                
                # Check timeout
                step_elapsed = (datetime.now() - step_start).total_seconds()
                if step_elapsed > step_timeout:
                    logger.warning(f"[{execution_id}] ⏱️ STEP 4 TIMEOUT: {step_elapsed/60:.1f}min - halting remaining evaluations")
                    break
                
                try:
                    # Evaluate predictions for this draw
                    await evaluate_predictions_for_draw(draw_date)
                    evaluated_count += 1
                    if evaluated_count <= 5:  # Log first 5
                        logger.info(f"[{execution_id}]   ✅ Evaluated {draw_date}")
                    
                except Exception as e:
                    error_count += 1
                    if error_count <= 3:  # Log first 3 errors
                        logger.warning(f"[{execution_id}]   ⚠️ Error evaluating {draw_date}: {e}")
            
            step_elapsed = (datetime.now() - step_start).total_seconds()
            
            # Summary
            logger.info(f"[{execution_id}] ✅ STEP 4 Complete: Evaluation summary")
            logger.info(f"[{execution_id}]   Draws with pending predictions: {len(draws_with_pending)}")
            logger.info(f"[{execution_id}]   Actually evaluated: {evaluated_count}")
            logger.info(f"[{execution_id}]   Elapsed time: {step_elapsed:.1f}s")
            if error_count > 0:
                logger.warning(f"[{execution_id}]   Errors encountered: {error_count}")
            
            # VALIDATION GATE 3 (informational)
            validation_result = {
                'success': True,
                'evaluated_count': evaluated_count,
                'error_count': error_count,
                'step_duration_seconds': step_elapsed
            }
            
            # Success - continue
            db.update_pipeline_execution_log(
                execution_id=execution_id,
                steps_completed=4
            )
            
        except Exception as e:
            # EXCEPTION DURING STEP 4 - LOG BUT CONTINUE (still non-critical for pipeline flow)
            logger.warning(f"[{execution_id}] ⚠️ STEP 4 EXCEPTION (continuing): {e}")
            logger.exception("Full traceback:")
            db.update_pipeline_execution_log(
                execution_id=execution_id,
                steps_completed=3,
                error=f"STEP 4 warning: {str(e)}"
            )

        # ========== STEP 5: ADAPTIVE LEARNING (CRITICAL) ==========
        logger.info(f"[{execution_id}] STEP 5/7: Adaptive learning - updating strategy weights...")
        db.update_pipeline_execution_log(
            execution_id=execution_id,
            current_step="STEP 5/7: Adaptive learning",
            steps_completed=4
        )
        
        try:
            step_start = datetime.now()
            await adaptive_learning_update()
            step_elapsed = (datetime.now() - step_start).total_seconds()
            logger.info(f"[{execution_id}] ✅ Strategy weights updated via Bayesian learning ({step_elapsed:.1f}s)")
            
            # VALIDATION GATE 4
            validation_result = validate_step_4_adaptive_learning(execution_id)
            
            if not validation_result['success']:
                # CRITICAL FAILURE - HALT PIPELINE
                error_detail = validation_result['error']
                logger.error(f"[{execution_id}] 🚨 PIPELINE HALTED at STEP 5: {error_detail}")
                
                elapsed = (datetime.now() - start_time).total_seconds()
                db.update_pipeline_execution_log(
                    execution_id=execution_id,
                    status="failed",
                    current_step="FAILED at STEP 5/7",
                    end_time=datetime.now().isoformat(),
                    error=f"STEP 5 VALIDATION FAILED: {error_detail}",
                    elapsed_seconds=elapsed
                )
                
                active_pipeline_execution_id = None
                return {
                    'success': False,
                    'execution_id': execution_id,
                    'failed_step': 'STEP 5: Adaptive learning',
                    'error': error_detail,
                    'elapsed_seconds': elapsed
                }
            
            # Success - continue
            db.update_pipeline_execution_log(
                execution_id=execution_id,
                steps_completed=5
            )
            
        except Exception as e:
            # EXCEPTION DURING STEP 5 - HALT PIPELINE
            logger.error(f"[{execution_id}] 🚨 PIPELINE STATUS: FAILED")
            logger.error(f"[{execution_id}] ❌ STEP 5 EXCEPTION: {e}")
            logger.exception("Full traceback:")
            
            elapsed = (datetime.now() - start_time).total_seconds()
            db.update_pipeline_execution_log(
                execution_id=execution_id,
                status="failed",
                current_step="❌ FAILED at STEP 5/7",
                end_time=datetime.now().isoformat(),
                error=f"FAILED: STEP 5 EXCEPTION - {str(e)}",
                elapsed_seconds=elapsed
            )
            
            active_pipeline_execution_id = None
            return {
                'success': False,
                'status': 'failed',
                'execution_id': execution_id,
                'failed_step': 'STEP 5: Adaptive learning',
                'error': str(e),
                'elapsed_seconds': elapsed
            }

        # ========== STEP 6: PREDICTION GENERATION (CRITICAL) ==========
        logger.info(f"[{execution_id}] STEP 6/7: Generating predictions with multi-strategy system...")
        db.update_pipeline_execution_log(
            execution_id=execution_id,
            current_step="STEP 6/7: Prediction generation",
            steps_completed=5
        )
        
        try:
            import gc
            from src.prediction_engine import UnifiedPredictionEngine
            from src.date_utils import DateManager

            engine = UnifiedPredictionEngine()

            # Get next draw date early (before generation)
            next_draw = DateManager.calculate_next_drawing_date()
            
            # Delete old predictions for this draw BEFORE generating new ones
            # This prevents duplicate accumulation
            with db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM generated_tickets WHERE draw_date = ?", (next_draw,))
                deleted_count = cursor.rowcount
                conn.commit()
            
            if deleted_count > 0:
                logger.info(f"[{execution_id}] Deleted {deleted_count} old predictions for {next_draw}")

            # Generate and save predictions in BATCHES (5 batches of 40 tickets each)
            # This reduces memory footprint and prevents OOM kills
            total_saved = 0
            strategy_dist = {}
            batch_size = 40  # Save every 40 tickets
            
            for batch_num in range(5):
                batch_tickets = []
                
                # Generate 40 tickets per batch
                for _ in range(8):  # 8 sets of 5 = 40 tickets
                    tickets = engine.generate_tickets(5)
                    batch_tickets.extend(tickets)
                    
                    # Track strategy distribution
                    for ticket in tickets:
                        strategy = ticket['strategy']
                        strategy_dist[strategy] = strategy_dist.get(strategy, 0) + 1
                
                # Save this batch to database immediately (don't hold in memory)
                batch_saved = save_generated_tickets(batch_tickets, next_draw)
                total_saved += batch_saved
                
                logger.info(f"[{execution_id}] Batch {batch_num + 1}/5: Saved {batch_saved} tickets ({total_saved}/200 total)")
                
                # Clear batch from memory immediately
                del batch_tickets
                
                # Force garbage collection every 40 tickets to prevent memory bloat
                gc.collect()
            
            logger.info(f"[{execution_id}] Generated and saved {total_saved} tickets for {next_draw}")
            logger.info(f"[{execution_id}] Strategy distribution: {strategy_dist}")
            
            # VALIDATION GATE 5
            expected_count = 200
            validation_result = validate_step_5_prediction(total_saved, expected_count, execution_id)
            
            if not validation_result['success']:
                # CRITICAL FAILURE - HALT PIPELINE
                error_detail = validation_result['error']
                logger.error(f"[{execution_id}] 🚨 PIPELINE HALTED at STEP 6: {error_detail}")
                
                elapsed = (datetime.now() - start_time).total_seconds()
                db.update_pipeline_execution_log(
                    execution_id=execution_id,
                    status="failed",
                    current_step="FAILED at STEP 6/7",
                    end_time=datetime.now().isoformat(),
                    error=f"STEP 6 VALIDATION FAILED: {error_detail}",
                    total_tickets_generated=total_saved,
                    target_draw_date=next_draw,
                    elapsed_seconds=elapsed
                )
                
                active_pipeline_execution_id = None
                return {
                    'success': False,
                    'execution_id': execution_id,
                    'failed_step': 'STEP 6: Prediction generation',
                    'error': error_detail,
                    'elapsed_seconds': elapsed
                }
            
            # ========== PIPELINE COMPLETED SUCCESSFULLY ==========
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # Extract data_source from metadata and normalize names
            final_data_source = metadata.get('polling_summary', {}).get('source', 'UNKNOWN')
            
            # Normalize source names for frontend display
            source_mapping = {
                'database': 'CSV',
                'web_scraping': 'SCRAPING',
                'musl_api': 'MUSL_API',
                'nclottery_csv': 'CSV',
                'csv': 'CSV'
            }
            final_data_source = source_mapping.get(final_data_source.lower(), final_data_source.upper())
            
            db.update_pipeline_execution_log(
                execution_id=execution_id,
                status="completed",
                current_step="✅ COMPLETED",
                steps_completed=7,
                total_steps=7,
                end_time=datetime.now().isoformat(),
                total_tickets_generated=total_saved,
                target_draw_date=next_draw,
                elapsed_seconds=elapsed,
                data_source=final_data_source
            )
            
            logger.info(f"[{execution_id}] 🎉 ========== PIPELINE STATUS: COMPLETED ==========")
            logger.info(f"[{execution_id}] ✅ All 7 steps executed successfully in {elapsed:.2f}s")
            logger.info(f"[{execution_id}] 📊 Generated {total_saved} tickets for draw {next_draw}")
            logger.info(f"[{execution_id}] 📡 Data source: {final_data_source}")
            logger.info(f"[{execution_id}] =====================================")
            
            # ========== BATCH TICKET PRE-GENERATION (BACKGROUND, NON-BLOCKING) ==========
            # Trigger batch generation in background (doesn't block pipeline completion)
            try:
                from src.batch_generator import BatchTicketGenerator
                
                logger.info(f"[{execution_id}] 🔄 Triggering batch ticket pre-generation in background...")
                
                # Initialize batch generator with configured modes
                batch_generator = BatchTicketGenerator(
                    batch_size=100,  # Generate 100 tickets per mode
                    modes=['random_forest', 'lstm', 'v1', 'v2', 'hybrid'],  # All 5 prediction modes
                    auto_cleanup=True,  # Auto-cleanup old tickets
                    cleanup_days=7  # Keep tickets for 7 days
                )
                
                # Generate batch in background (async, non-blocking)
                batch_result = batch_generator.generate_batch(
                    pipeline_run_id=execution_id,
                    async_mode=True  # Run in background thread
                )
                
                if batch_result.get('started'):
                    logger.info(
                        f"[{execution_id}] ✓ Batch generation started in background: "
                        f"modes={batch_result['modes']}, batch_size={batch_result['batch_size']}"
                    )
                else:
                    logger.warning(
                        f"[{execution_id}] ⚠ Batch generation skipped: "
                        f"{batch_result.get('error', 'unknown error')}"
                    )
            except Exception as e:
                # Log error but don't fail pipeline (batch generation is non-critical)
                logger.warning(f"[{execution_id}] ⚠ Batch generation failed (non-critical): {e}")
                logger.debug("Batch generation exception:", exc_info=True)

            active_pipeline_execution_id = None  # Clear tracking on completion
            return {
                'success': True,
                'status': 'completed',
                'execution_id': execution_id,
                'elapsed_seconds': elapsed,
                'tickets_generated': total_saved,
                'target_draw': next_draw,
                'message': 'Pipeline completed successfully - all steps executed'
            }

        except Exception as e:
            # EXCEPTION DURING STEP 6 - HALT PIPELINE
            logger.error(f"[{execution_id}] 🚨 PIPELINE STATUS: FAILED")
            logger.error(f"[{execution_id}] ❌ STEP 6 EXCEPTION: {e}")
            logger.exception("Full traceback:")
            
            elapsed = (datetime.now() - start_time).total_seconds()
            db.update_pipeline_execution_log(
                execution_id=execution_id,
                status="failed",
                current_step="❌ FAILED at STEP 6/7",
                end_time=datetime.now().isoformat(),
                error=f"FAILED: STEP 6 EXCEPTION - {str(e)}",
                elapsed_seconds=elapsed
            )
            
            active_pipeline_execution_id = None
            return {
                'success': False,
                'status': 'failed',
                'execution_id': execution_id,
                'failed_step': 'STEP 6: Prediction generation',
                'error': str(e),
                'elapsed_seconds': elapsed
            }

    except Exception as e:
        # UNEXPECTED TOP-LEVEL EXCEPTION
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error(f"[{execution_id}] 🚨 PIPELINE STATUS: FAILED")
        logger.error(f"[{execution_id}] ❌ TOP-LEVEL EXCEPTION after {elapsed:.2f}s")
        logger.exception("Full pipeline error:")
        
        # Final update: failed
        db.update_pipeline_execution_log(
            execution_id=execution_id,
            status="failed",
            current_step="❌ FAILED (top-level)",
            end_time=datetime.now().isoformat(),
            error=f"FAILED: TOP-LEVEL EXCEPTION - {str(e)}",
            elapsed_seconds=elapsed
        )

        active_pipeline_execution_id = None  # Clear tracking on failure
        return {
            'success': False,
            'status': 'failed',
            'execution_id': execution_id,
            'failed_step': 'Unknown (top-level)',
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

# ============================================================================
# SCHEDULER JOB FUNCTIONS (must be module-level for serialization)
# ============================================================================

def run_daily_full_sync():
    """
    Wrapper for daily sync job with error handling.
    MUST be module-level function (not nested) for APScheduler serialization.
    """
    try:
        logger.info("🔄 [scheduler] Starting Daily Full Sync Job...")
        result = daily_full_sync_job()
        if result['success']:
            logger.info(
                f"🔄 [scheduler] Daily sync complete: "
                f"{result['draws_inserted']} draws inserted, "
                f"latest: {result['latest_date']}"
            )
        else:
            logger.error(f"🔄 [scheduler] Daily sync failed: {result.get('error')}")
    except Exception as e:
        logger.error(f"🔄 [scheduler] Daily sync exception: {e}", exc_info=True)

# ============================================================================

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
    
    # Recover any stale pipelines from previous runs
    try:
        recover_stale_pipelines()
    except Exception as e:
        logger.error(f"Pipeline recovery check failed: {e}")

    # Pipeline orchestrator removed - deprecated system that caused inconsistent results

    # ============================================================================
    # SCHEDULER CONFIGURATION - Unified Adaptive Polling System (v4.0)
    # ============================================================================
    # NEW ARCHITECTURE (November 2025):
    # - Job #1: Daily Full Sync at 6:00 AM ET (safety net for completeness)
    # - Job #2: Real-time Unified Polling at 11:05 PM ET on drawing days
    # - Removed: Legacy smart polling and maintenance retry jobs
    # ============================================================================
    
    # Job #1: DAILY FULL SYNC - Runs at 6:00 AM ET every day
    # Purpose: Safety net that ensures database completeness
    # - Fetches historical draws from NC Lottery CSV
    # - Finds and inserts any missing draws
    # - Catches draws missed by real-time polling (network outages, service downtime)
    # NOTE: run_daily_full_sync() is defined at module level for APScheduler serialization
    
    scheduler.add_job(
        func=run_daily_full_sync,
        trigger="cron",
        hour=6,                       # 6:00 AM ET
        minute=0,
        timezone="America/New_York",  # EXPLICIT TIMEZONE
        id="daily_full_sync",
        name="Daily Full Sync 6:00 AM ET (safety net)",
        max_instances=1,
        coalesce=True,
        replace_existing=True
    )

    # Job #2: REAL-TIME UNIFIED POLLING - Runs at 11:05 PM ET on drawing days
    # Purpose: Fetch new draw via 3-layer fallback and execute full pipeline
    # - 11:05 PM = 6 minutes after 10:59 PM draw
    # - Unified adaptive polling (NC Scraping → MUSL → NC CSV)
    # - Adaptive intervals: 2min → 5min → 10min
    # - Timeout at 6:00 AM (Daily Full Sync takes over)
    scheduler.add_job(
        func=trigger_full_pipeline_automatically,
        trigger="cron",
        day_of_week="mon,wed,sat",   # Powerball drawing days (Monday, Wednesday, Saturday)
        hour=23,                      # 11:05 PM ET (6 minutes after 10:59 PM draw)
        minute=5,
        timezone="America/New_York",  # EXPLICIT TIMEZONE
        id="post_drawing_pipeline",
        name="Real-time Unified Polling 11:05 PM ET",
        max_instances=1,              # Prevent overlapping executions
        coalesce=True,                # Merge multiple pending executions into one
        replace_existing=True         # Update job on restart instead of duplicating
    )

    # REMOVED Jobs:
    # - maintenance_data_update: Redundant with Daily Full Sync
    # - maintenance_data_retry: Redundant with adaptive polling timeout

    # Start scheduler after configuration
    try:
        scheduler.start()
        logger.info("✅ Scheduler started successfully with persistent jobstore (SQLite)")
        logger.info(f"📁 Jobstore location: {scheduler_db_path}")

        # Record scheduler start time for uptime metrics
        global SCHEDULER_START_TIME_UTC
        SCHEDULER_START_TIME_UTC = datetime.now(pytz.UTC)

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
        # Check if scheduler is running
        if not scheduler or not scheduler.running:
            return {
                "status": "stopped",
                "scheduler_running": False,
                "message": "Scheduler is not running. It may have failed to start or been stopped.",
                "jobs": [],
                "current_time_utc": datetime.now(pytz.UTC).isoformat(),
                "current_time_et": datetime.now(pytz.UTC).astimezone(pytz.timezone('America/New_York')).isoformat()
            }
        
        jobs = scheduler.get_jobs()

        # Compute current times
        utc_now = datetime.now(pytz.UTC)
        try:
            et_tz = pytz.timezone('America/New_York')
        except Exception:
            et_tz = pytz.UTC
        et_now = utc_now.astimezone(et_tz)

        # Extract summaries for key jobs and readiness info
        def summarize_job(job):
            if not job:
                return None
            nrt = getattr(job, 'next_run_time', None)
            nrt_utc = None
            nrt_et = None
            seconds_until = None
            minutes_until = None
            if nrt:
                # APScheduler stores timezone-aware datetimes
                try:
                    nrt_utc = nrt.astimezone(pytz.UTC).isoformat()
                    nrt_et = nrt.astimezone(et_tz).isoformat()
                    seconds_until = max(0, int((nrt.astimezone(pytz.UTC) - utc_now).total_seconds()))
                    minutes_until = round(seconds_until / 60.0, 2)
                except Exception:
                    pass
            return {
                "job_id": job.id,
                "name": job.name,
                "next_run_time_utc": nrt_utc,
                "next_run_time_et": nrt_et,
                "seconds_until_next_run": seconds_until,
                "minutes_until_next_run": minutes_until,
                "trigger": str(job.trigger)
            }

        job_by_id = {j.id: j for j in jobs}
        
        # v4.0 jobs
        daily_sync_summary = summarize_job(job_by_id.get("daily_full_sync"))
        post_draw_summary = summarize_job(job_by_id.get("post_drawing_pipeline"))
        
        # Legacy jobs (removed in v4.0)
        retry_summary = summarize_job(job_by_id.get("maintenance_data_retry"))

        # Optional: include latest pipeline execution summary for monitoring
        latest_pipeline = None
        try:
            conn = db.get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT execution_id, status, start_time, end_time, steps_completed, total_tickets_generated, metadata
                FROM pipeline_execution_logs
                ORDER BY start_time DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                # Compute age in minutes from end_time when available, else from start_time
                try:
                    ref = row[3] or row[2]
                    dt = datetime.fromisoformat(ref)
                    age_minutes = round((datetime.now() - dt).total_seconds() / 60.0, 2)
                except Exception:
                    age_minutes = None

                # Parse metadata JSON to extract data_source
                data_source = "UNKNOWN"
                try:
                    if row[6]:  # metadata column
                        metadata_obj = json.loads(row[6])
                        data_source = metadata_obj.get("data_source", "UNKNOWN")
                except Exception:
                    pass

                latest_pipeline = {
                    "execution_id": row[0],
                    "status": row[1],
                    "start_time": row[2],
                    "end_time": row[3],
                    "steps_completed": row[4],
                    "total_tickets_generated": row[5],
                    "data_source": data_source,
                    "age_minutes": age_minutes,
                }
        except Exception as _e:
            # Do not fail the endpoint if DB lookup fails
            latest_pipeline = None

        # Determine scheduler readiness: running, with at least one future run scheduled
        has_future = any(
            getattr(j, 'next_run_time', None) and getattr(j, 'next_run_time') > utc_now
            for j in jobs
        )
        scheduler_ready = bool(scheduler.running and has_future)

        response = {
            "scheduler_running": scheduler.running,
            "scheduler_ready": scheduler_ready,
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
            "jobstore_path": scheduler_db_path,
            "now": {
                "utc": utc_now.isoformat(),
                "et": et_now.isoformat(),
            },
            "daily_sync_summary": daily_sync_summary,      # v4.0: Daily Full Sync at 6 AM
            "post_drawing_summary": post_draw_summary,     # v4.0: Real-time Polling at 11:05 PM
            "retry_summary": retry_summary,                # Legacy (removed in v4.0)
            "latest_pipeline": latest_pipeline,
            "config": {
                "timezone": "America/New_York",
                "job_defaults": job_defaults,
            },
            "notes": {
                "version": "v4.0 - Unified Adaptive Polling System",
                "architecture": "3-layer fallback: NC Lottery Scraping → MUSL API → NC CSV",
                "jobs": "Daily Full Sync (6 AM) + Real-time Polling (11:05 PM mon/wed/sat)",
                "removed_jobs": "maintenance_data_update, maintenance_data_retry (deprecated)"
            }
        }

        # Include scheduler uptime if available
        try:
            if SCHEDULER_START_TIME_UTC is not None:
                response["scheduler_started_at"] = SCHEDULER_START_TIME_UTC.isoformat()
                response["scheduler_uptime_seconds"] = int((utc_now - SCHEDULER_START_TIME_UTC).total_seconds())
        except Exception:
            pass

        return response
    except AttributeError as e:
        # Scheduler may not be initialized or missing attributes
        logger.warning(f"Scheduler not fully initialized: {e}")
        return {
            "status": "error",
            "scheduler_running": False,
            "message": f"Scheduler not initialized: {str(e)}",
            "jobs": [],
            "current_time_utc": datetime.now(pytz.UTC).isoformat(),
            "current_time_et": datetime.now(pytz.UTC).astimezone(pytz.timezone('America/New_York')).isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting scheduler health: {e}", exc_info=True)
        return {
            "status": "error",
            "scheduler_running": False,
            "message": f"Error retrieving scheduler health: {str(e)}",
            "jobs": [],
            "current_time_utc": datetime.now(pytz.UTC).isoformat(),
            "current_time_et": datetime.now(pytz.UTC).astimezone(pytz.timezone('America/New_York')).isoformat()
        }

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

        # Get predictions with matches
        cursor.execute("""
            SELECT COUNT(*) FROM generated_tickets 
            WHERE evaluated = 1 
            AND matches_wb > 0
        """)
        winning_predictions = cursor.fetchone()[0]

        conn.close()

        # Try to get Google Analytics data
        ga_stats = {}
        try:
            from src.google_analytics_service import get_ga_service
            ga_service = get_ga_service()
            
            if ga_service.is_enabled():
                # Get GA4 traffic stats (last 7 days)
                ga_traffic = ga_service.get_traffic_stats(days_back=7)
                # Get real-time stats
                ga_realtime = ga_service.get_realtime_stats()
                # Get device breakdown
                ga_devices = ga_service.get_device_breakdown()
                
                ga_stats = {
                    "enabled": True,
                    "unique_visitors_7d": ga_traffic.get("unique_visitors", 0),
                    "total_sessions_7d": ga_traffic.get("total_sessions", 0),
                    "total_pageviews_7d": ga_traffic.get("total_pageviews", 0),
                    "avg_session_duration_sec": ga_traffic.get("avg_session_duration_sec", 0),
                    "pages_per_session": ga_traffic.get("pages_per_session", 0.0),
                    "new_visitors_7d": ga_traffic.get("new_visitors", 0),
                    "active_users_now": ga_realtime.get("active_users", 0),
                    "pageviews_30min": ga_realtime.get("pageviews_30min", 0),
                    "devices": ga_devices.get("devices", {}),
                }
            else:
                ga_stats = {"enabled": False}
        except Exception as e:
            logger.warning(f"Could not fetch Google Analytics data: {e}")
            ga_stats = {"enabled": False, "error": str(e)}

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
            "analytics": ga_stats,
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


@api_router.get("/analytics/ga4")
async def get_google_analytics_stats(days_back: int = 7):
    """
    Get Google Analytics 4 statistics (traffic, sessions, devices)
    
    Args:
        days_back: Number of days to look back (default 7, max 90)
    
    Returns:
        GA4 metrics including traffic, real-time data, and daily breakdown
    """
    try:
        from src.google_analytics_service import get_ga_service
        
        # Validate days_back
        if days_back < 1 or days_back > 90:
            raise HTTPException(status_code=400, detail="days_back must be between 1 and 90")
        
        ga_service = get_ga_service()
        
        if not ga_service.is_enabled():
            return {
                "enabled": False,
                "message": "Google Analytics integration not configured. Set GA4_PROPERTY_ID and GA4_CREDENTIALS_PATH environment variables."
            }
        
        # Fetch all GA4 data
        traffic_stats = ga_service.get_traffic_stats(days_back=days_back)
        realtime_stats = ga_service.get_realtime_stats()
        daily_breakdown = ga_service.get_daily_breakdown(days_back=days_back)
        device_breakdown = ga_service.get_device_breakdown()
        
        return {
            "enabled": True,
            "period_days": days_back,
            "traffic": {
                "unique_visitors": traffic_stats.get("unique_visitors", 0),
                "total_sessions": traffic_stats.get("total_sessions", 0),
                "total_pageviews": traffic_stats.get("total_pageviews", 0),
                "new_visitors": traffic_stats.get("new_visitors", 0),
                "returning_visitors": traffic_stats.get("unique_visitors", 0) - traffic_stats.get("new_visitors", 0),
                "avg_session_duration_sec": traffic_stats.get("avg_session_duration_sec", 0),
                "avg_session_duration_min": round(traffic_stats.get("avg_session_duration_sec", 0) / 60, 1),
                "pages_per_session": traffic_stats.get("pages_per_session", 0.0),
            },
            "realtime": {
                "active_users_now": realtime_stats.get("active_users", 0),
                "pageviews_last_30min": realtime_stats.get("pageviews_30min", 0),
            },
            "daily_breakdown": daily_breakdown.get("daily_stats", []),
            "devices": device_breakdown.get("devices", {}),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error fetching Google Analytics data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving Google Analytics data: {str(e)}"
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
app.include_router(batch_router, prefix="/api/v1/tickets")  # Batch ticket endpoints
app.include_router(public_frontend_router)

# Import and mount v3 analytics router (SHIOL+ v2)
try:
    from src.v2.analytics_api import analytics_router
    app.include_router(analytics_router)  # Analytics v3 endpoints
    logger.info("SHIOL+ v2 analytics router mounted at /api/v3/analytics")
except Exception as e:
    logger.warning(f"Could not mount v3 analytics router: {e}")

# Import and mount v3 prediction engine router
try:
    from src.api_v3_endpoints import router as v3_router
    app.include_router(v3_router)  # Prediction engine v3 endpoints
    logger.info("API v3 prediction engine router mounted at /api/v3")
except Exception as e:
    logger.warning(f"Could not mount v3 prediction router: {e}")

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

# --- PLP v2 HTTPException handler to standardize error shape even for dependency errors ---
@app.exception_handler(HTTPException)
async def plp_v2_http_exception_handler(request: Request, exc: HTTPException):
    try:
        path = str(request.url.path)
    except Exception:
        path = ""
    if path.startswith("/api/v2"):
        status = exc.status_code
        detail = exc.detail
        payload = {
            "error": detail if isinstance(detail, str) else "request_error",
            "code": status,
            "details": None if isinstance(detail, str) else detail,
        }
        headers = getattr(exc, "headers", None) or {}
        return JSONResponse(status_code=status, content=payload, headers=headers)
    # Fallback to default FastAPI style for non-v2
    headers = getattr(exc, "headers", None) or {}
    content = {"detail": exc.detail}
    return JSONResponse(status_code=exc.status_code, content=content, headers=headers)

# --- PLP v2 Error Normalization Middleware ---
@app.middleware("http")
async def plp_v2_error_middleware(request: Request, call_next):
    """Standardize error shape for /api/v2 endpoints only.

    Returns JSON: { error, code, details } preserving status codes.
    """
    try:
        return await call_next(request)
    except HTTPException as he:  # type: ignore
        try:
            path = str(request.url.path)
        except Exception:
            path = ""
        if path.startswith("/api/v2"):
            status = he.status_code
            detail = he.detail
            payload = {
                "error": detail if isinstance(detail, str) else "request_error",
                "code": status,
                "details": None if isinstance(detail, str) else detail,
            }
            # Include any headers provided by the exception (e.g., rate limit headers)
            headers = getattr(he, "headers", None) or {}
            return JSONResponse(status_code=status, content=payload, headers=headers)
        # Not v2: propagate default behavior
        raise
    except Exception as e:  # Unhandled errors -> 500 for v2 only
        try:
            path = str(request.url.path)
        except Exception:
            path = ""
        if path.startswith("/api/v2"):
            logger.error(f"Unhandled error in v2 endpoint {path}: {e}")
            return JSONResponse(status_code=500, content={
                "error": "internal_error",
                "code": 500,
                "details": "An internal server error occurred",
            })
        raise

# --- Optional: Mount PLP v2 API (feature-flagged, non-breaking) ---
try:
    PLP_API_ENABLED = os.getenv("PLP_API_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")
    if PLP_API_ENABLED:
        from src.api_plp_v2 import router as plp_v2_router
        app.include_router(plp_v2_router)
        logger.info("PLP v2 API router mounted under /api/v2 (feature flag enabled)")
    else:
        logger.info("PLP v2 API disabled (set PLP_API_ENABLED=true to enable)")
except Exception as e:
    logger.error(f"Failed to mount PLP v2 API: {e}")

# Mount frontend last (catch-all for HTML) — must be AFTER API routers to avoid intercepting /api/* routes
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
