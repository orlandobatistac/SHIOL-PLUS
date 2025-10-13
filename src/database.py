import sqlite3
import pandas as pd
from loguru import logger
import configparser
import os
import json
import numpy as np
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
import hashlib
import secrets


def calculate_prize_amount(main_matches: int, powerball_match: bool) -> Tuple[float, str]:
    """
    Calculate prize amount based on main number matches and powerball match.

    Args:
        main_matches: Number of main numbers matched (0-5)
        powerball_match: Whether powerball was matched

    Returns:
        Tuple of (prize_amount, prize_description)
    """
    if main_matches == 5 and powerball_match:
        return 100_000_000.0, "Jackpot"
    elif main_matches == 5:
        return 1_000_000.0, "Match 5"
    elif main_matches == 4 and powerball_match:
        return 50_000.0, "Match 4 + PB"
    elif main_matches == 4:
        return 100.0, "Match 4"
    elif main_matches == 3 and powerball_match:
        return 100.0, "Match 3 + PB"
    elif main_matches == 3:
        return 7.0, "Match 3"
    elif main_matches == 2 and powerball_match:
        return 7.0, "Match 2 + PB"
    elif main_matches == 1 and powerball_match:
        return 4.0, "Match 1 + PB"
    elif powerball_match:
        return 4.0, "Match PB"
    else:
        return 0.0, "No matches"


class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle numpy types."""

    def default(self, o):
        """Override default method with correct parameter name."""
        if isinstance(o, np.integer):
            return int(o)
        elif isinstance(o, np.floating):
            return float(o)
        elif isinstance(o, np.ndarray):
            return o.tolist()
        return super(NumpyEncoder, self).default(o)


def get_db_path() -> str:
    """Reads the database file path from the configuration file."""
    config = configparser.ConfigParser()
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, '..', 'config', 'config.ini')

    try:
        config.read(config_path)
        if config.has_section('paths') and config.has_option('paths', 'database_file'):
            db_file = config["paths"]["database_file"]
        else:
            db_file = "data/shiolplus.db"
            logger.warning(f"Config section 'paths' or 'database_file' option not found, using default: {db_file}")

        db_path = os.path.join(current_dir, '..', db_file)
    except (configparser.Error, OSError) as e:
        logger.error(f"Error reading config file: {e}. Using default database path.")
        db_path = os.path.join(current_dir, '..', 'data', 'shiolplus.db')

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return db_path


def calculate_next_drawing_date() -> str:
    """
    Calculate the next Powerball drawing date using centralized DateManager.

    Returns:
        str: Next drawing date in YYYY-MM-DD format

    Raises:
        ImportError: If DateManager module cannot be imported
    """
    try:
        from src.date_utils import DateManager
        current_et = DateManager.get_current_et_time()
        next_date = DateManager.calculate_next_drawing_date(reference_date=current_et)

        logger.debug(f"Next drawing date calculated: {next_date} (from ET time: {current_et.strftime('%Y-%m-%d %H:%M')})")
        return next_date
    except ImportError as e:
        logger.error(f"Failed to import DateManager: {e}")
        raise
    except Exception as e:
        logger.error(f"Error calculating next drawing date: {e}")
        raise


def get_db_connection() -> sqlite3.Connection:
    """
    Establishes a connection to the SQLite database.

    Returns:
        sqlite3.Connection: A connection object to the database.

    Raises:
        sqlite3.Error: If database connection fails
    """
    db_path = get_db_path()
    try:
        conn = sqlite3.connect(db_path)
        logger.info(f"Successfully connected to database at {db_path}")
        return conn
    except sqlite3.Error as e:
        logger.error(f"Error connecting to database at {db_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error connecting to database: {e}")
        raise sqlite3.Error(f"Database connection failed: {e}") from e


def save_pipeline_execution(execution_data: Dict[str, Any]) -> Optional[str]:
    """Save pipeline execution to SQLite database with duplicate prevention."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            execution_id = execution_data.get('execution_id')

            # Check if execution already exists
            cursor.execute("SELECT id FROM pipeline_executions WHERE execution_id = ?", (execution_id,))
            existing = cursor.fetchone()

            if existing:
                logger.warning(f"Pipeline execution {execution_id} already exists, skipping duplicate creation")
                return execution_id

            cursor.execute(
                """
                INSERT INTO pipeline_executions (
                    execution_id, status, start_time, trigger_type, trigger_source,
                    current_step, steps_completed, total_steps, num_predictions,
                    execution_details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                execution_id,
                execution_data.get('status', 'starting'),
                execution_data.get('start_time'),
                execution_data.get('trigger_type', 'unknown'),
                execution_data.get('trigger_source', 'unknown'),
                execution_data.get('current_step'),
                execution_data.get('steps_completed', 0),
                execution_data.get('total_steps', 5),
                execution_data.get('num_predictions', 100),
                json.dumps(execution_data.get('execution_details', {}), cls=NumpyEncoder)
            ))

            conn.commit()
            logger.info(f"Pipeline execution {execution_id} saved to SQLite")
            return execution_id

    except sqlite3.Error as e:
        logger.error(f"SQLite error saving pipeline execution: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"JSON encoding error in pipeline execution: {e}")
        return None


def update_pipeline_execution(execution_id: str, update_data: Dict[str, Any]) -> bool:
    """Update pipeline execution in SQLite database."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            update_fields = []
            params = []

            field_mappings = {
                'status': 'status = ?',
                'end_time': 'end_time = ?',
                'current_step': 'current_step = ?',
                'steps_completed': 'steps_completed = ?',
                'error_message': 'error_message = ?',
                'subprocess_success': 'subprocess_success = ?',
                'stdout_output': 'stdout_output = ?',
                'stderr_output': 'stderr_output = ?'
            }

            for field, sql_field in field_mappings.items():
                if field in update_data:
                    update_fields.append(sql_field)
                    params.append(update_data[field])

            if not update_fields:
                logger.warning(f"No valid fields to update for execution {execution_id}")
                return False

            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(execution_id)

            query = f"""
                UPDATE pipeline_executions 
                SET {', '.join(update_fields)}
                WHERE execution_id = ?
            """

            cursor.execute(query, params)

            if cursor.rowcount > 0:
                conn.commit()
                logger.info(f"Pipeline execution {execution_id} updated in SQLite")
                return True
            else:
                logger.warning(f"Pipeline execution {execution_id} not found for update")
                return False

    except sqlite3.Error as e:
        logger.error(f"SQLite error updating pipeline execution: {e}")
        return False


def get_pipeline_execution_history(limit: int = 20) -> List[Dict[str, Any]]:
    """Get pipeline execution history from SQLite database."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT 
                    execution_id, status, start_time, end_time,
                    trigger_type, trigger_source, current_step,
                    steps_completed, total_steps, num_predictions,
                    error_message, subprocess_success, created_at
                FROM pipeline_executions
                ORDER BY start_time DESC
                LIMIT ?
            """, (limit,))

            executions = []
            for row in cursor.fetchall():
                execution = {
                    'execution_id': row[0],
                    'status': row[1],
                    'start_time': row[2],
                    'end_time': row[3],
                    'trigger_type': row[4],
                    'trigger_source': row[5],
                    'current_step': row[6],
                    'steps_completed': row[7],
                    'total_steps': row[8],
                    'num_predictions': row[9],
                    'error': row[10],
                    'subprocess_success': row[11] == 1 if row[11] is not None else False,
                    'created_at': row[12]
                }
                executions.append(execution)

            logger.info(f"Retrieved {len(executions)} pipeline executions from SQLite")
            return executions

    except sqlite3.Error as e:
        logger.error(f"SQLite error getting pipeline execution history: {e}")
        return []


def get_pipeline_execution_by_id(execution_id: str) -> Optional[Dict[str, Any]]:
    """Get specific pipeline execution by ID from SQLite."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT 
                    execution_id, status, start_time, end_time,
                    trigger_type, trigger_source, current_step,
                    steps_completed, total_steps, num_predictions,
                    error_message, execution_details, subprocess_success,
                    stdout_output, stderr_output, created_at, updated_at
                FROM pipeline_executions
                WHERE execution_id = ?
            """, (execution_id,))

            row = cursor.fetchone()
            if row:
                execution = {
                    'execution_id': row[0],
                    'status': row[1],
                    'start_time': row[2],
                    'end_time': row[3],
                    'trigger_type': row[4],
                    'trigger_source': row[5],
                    'current_step': row[6],
                    'steps_completed': row[7],
                    'total_steps': row[8],
                    'num_predictions': row[9],
                    'error': row[10],
                    'execution_details': json.loads(row[11]) if row[11] else {},
                    'subprocess_success': row[12] == 1 if row[12] is not None else False,
                    'stdout_output': row[13],
                    'stderr_output': row[14],
                    'created_at': row[15],
                    'updated_at': row[16]
                }

                logger.info(f"Retrieved pipeline execution {execution_id} from SQLite")
                return execution
            else:
                logger.warning(f"Pipeline execution {execution_id} not found in SQLite")
                return None

    except sqlite3.Error as e:
        logger.error(f"Error getting pipeline execution by ID from SQLite: {e}")
        return None


def initialize_database():
    """Initialize the database by creating all required tables if they don't exist."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Core tables
            _create_core_tables(cursor)
            _create_prediction_tables(cursor)
            _create_feedback_tables(cursor)
            _create_indexes(cursor)

            conn.commit()

            # Initialize configuration system
            if not is_config_initialized():
                logger.info("Initializing hybrid configuration system...")
                migrate_config_from_file()


            logger.info("Database initialized successfully with all tables and indexes.")

    except sqlite3.Error as e:
        logger.error(f"Database error during initialization: {e}")
        raise


def _create_core_tables(cursor):
    """Create core system tables."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS powerball_draws (
            draw_date DATE PRIMARY KEY,
            n1 INTEGER NOT NULL,
            n2 INTEGER NOT NULL,
            n3 INTEGER NOT NULL,
            n4 INTEGER NOT NULL,
            n5 INTEGER NOT NULL,
            pb INTEGER NOT NULL
        )
    """)

    # Users table for authentication and premium access
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_premium BOOLEAN DEFAULT FALSE,
            premium_expires_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME,
            login_count INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE
        )
    """)
    
    # Migration for is_admin column
    try:
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_admin' not in columns:
            logger.info("Adding is_admin column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE")
            logger.info("is_admin column added successfully")
    except sqlite3.Error as e:
        logger.error(f"Error during is_admin migration: {e}")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            section TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (section, key)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_id TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'starting',
            start_time TEXT NOT NULL,
            end_time TEXT,
            trigger_type TEXT NOT NULL,
            trigger_source TEXT NOT NULL,
            current_step TEXT,
            steps_completed INTEGER DEFAULT 0,
            total_steps INTEGER DEFAULT 7,
            num_predictions INTEGER DEFAULT 100,
            error_message TEXT,
            execution_details TEXT,
            subprocess_success BOOLEAN DEFAULT FALSE,
            stdout_output TEXT,
            stderr_output TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Tabla para visitas únicas por dispositivo
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS unique_visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_fingerprint TEXT UNIQUE NOT NULL,
            first_visit DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_visit DATETIME DEFAULT CURRENT_TIMESTAMP,
            visit_count INTEGER DEFAULT 1
        )
    """)
    
    # Tabla para instalaciones del PWA
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pwa_installs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_fingerprint TEXT UNIQUE NOT NULL,
            install_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Weekly verification limits table for guest and registered users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS weekly_verification_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NULL,
            device_fingerprint TEXT NULL,
            week_start_date DATE NOT NULL,
            verification_count INTEGER DEFAULT 0,
            last_verification DATETIME,
            user_type TEXT NOT NULL DEFAULT 'guest',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, week_start_date),
            UNIQUE(device_fingerprint, week_start_date),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    
    # Stripe billing tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS idempotency_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idempotency_key TEXT UNIQUE NOT NULL,
            endpoint TEXT NOT NULL,
            request_payload TEXT NOT NULL,
            response_data TEXT,
            status_code INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            processed_at DATETIME
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS webhook_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stripe_event_id TEXT UNIQUE NOT NULL,
            event_type TEXT NOT NULL,
            processed BOOLEAN DEFAULT FALSE,
            processed_at DATETIME,
            payload TEXT NOT NULL,
            processing_error TEXT,
            retry_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stripe_customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stripe_customer_id TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            user_id INTEGER NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stripe_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stripe_subscription_id TEXT UNIQUE NOT NULL,
            stripe_customer_id TEXT NOT NULL,
            status TEXT NOT NULL,
            current_period_start DATETIME,
            current_period_end DATETIME,
            canceled_at DATETIME,
            ended_at DATETIME,
            trial_start DATETIME,
            trial_end DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (stripe_customer_id) REFERENCES stripe_customers(stripe_customer_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS premium_passes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pass_token TEXT UNIQUE NOT NULL,
            jti TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            stripe_subscription_id TEXT UNIQUE,
            stripe_customer_id TEXT,
            user_id INTEGER NULL,
            expires_at DATETIME NOT NULL,
            revoked_at DATETIME,
            revoked_reason TEXT,
            device_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (stripe_subscription_id) REFERENCES stripe_subscriptions(stripe_subscription_id),
            FOREIGN KEY (stripe_customer_id) REFERENCES stripe_customers(stripe_customer_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS premium_pass_devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pass_id INTEGER NOT NULL,
            device_fingerprint TEXT NOT NULL,
            first_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(pass_id, device_fingerprint),
            FOREIGN KEY (pass_id) REFERENCES premium_passes(id)
        )
    """)
    
    # IP rate limiting table for abuse protection  
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ip_rate_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            hour_window DATETIME NOT NULL,
            request_count INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ip_address, hour_window)
        )
    """)


def _create_prediction_tables(cursor):
    """Create prediction-related tables."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            n1 INTEGER NOT NULL,
            n2 INTEGER NOT NULL,
            n3 INTEGER NOT NULL,
            n4 INTEGER NOT NULL,
            n5 INTEGER NOT NULL,
            powerball INTEGER NOT NULL,
            score_total REAL NOT NULL,
            model_version TEXT NOT NULL,
            dataset_hash TEXT NOT NULL,
            json_details_path TEXT,
            target_draw_date DATE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            evaluated BOOLEAN DEFAULT FALSE,
            matches_wb INTEGER DEFAULT 0,
            matches_pb BOOLEAN DEFAULT FALSE,
            prize_amount REAL DEFAULT 0.0,
            prize_description TEXT DEFAULT 'Not evaluated',
            evaluation_date DATETIME
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS validation_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_id INTEGER NOT NULL,
            draw_date DATE NOT NULL,
            matches INTEGER NOT NULL,
            prize_amount REAL NOT NULL,
            prize_description TEXT NOT NULL,
            actual_numbers TEXT NOT NULL,
            actual_powerball INTEGER NOT NULL,
            evaluated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prediction_id) REFERENCES predictions_log (id)
        )
    """)

    # Migration for target_draw_date column
    try:
        cursor.execute("PRAGMA table_info(predictions_log)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'target_draw_date' not in columns:
            logger.info("Adding target_draw_date column to existing predictions_log table...")
            cursor.execute("ALTER TABLE predictions_log ADD COLUMN target_draw_date DATE")
            cursor.execute("""
                UPDATE predictions_log
                SET target_draw_date = DATE(created_at)
                WHERE target_draw_date IS NULL
            """)
            logger.info("target_draw_date column added and populated")

        # Migration for evaluation columns
        evaluation_columns = ['evaluated', 'matches_wb', 'matches_pb', 'prize_amount', 'prize_description', 'evaluation_date']
        for col in evaluation_columns:
            if col not in columns:
                logger.info(f"Adding {col} column to predictions_log table...")
                if col == 'evaluated':
                    cursor.execute("ALTER TABLE predictions_log ADD COLUMN evaluated BOOLEAN DEFAULT FALSE")
                elif col == 'matches_wb':
                    cursor.execute("ALTER TABLE predictions_log ADD COLUMN matches_wb INTEGER DEFAULT 0")
                elif col == 'matches_pb':
                    cursor.execute("ALTER TABLE predictions_log ADD COLUMN matches_pb BOOLEAN DEFAULT FALSE")
                elif col == 'prize_amount':
                    cursor.execute("ALTER TABLE predictions_log ADD COLUMN prize_amount REAL DEFAULT 0.0")
                elif col == 'prize_description':
                    cursor.execute("ALTER TABLE predictions_log ADD COLUMN prize_description TEXT DEFAULT 'Not evaluated'")
                elif col == 'evaluation_date':
                    cursor.execute("ALTER TABLE predictions_log ADD COLUMN evaluation_date DATETIME")
                logger.info(f"{col} column added successfully")

    except sqlite3.Error as e:
        logger.error(f"Error during migrations: {e}")


def _create_feedback_tables(cursor):
    """Create adaptive feedback system tables."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS performance_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_id INTEGER NOT NULL,
            draw_date DATE NOT NULL,
            actual_n1 INTEGER NOT NULL,
            actual_n2 INTEGER NOT NULL,
            actual_n3 INTEGER NOT NULL,
            actual_n4 INTEGER NOT NULL,
            actual_n5 INTEGER NOT NULL,
            actual_pb INTEGER NOT NULL,
            matches_main INTEGER NOT NULL,
            matches_pb INTEGER NOT NULL,
            prize_tier TEXT NOT NULL,
            score_accuracy REAL NOT NULL,
            component_accuracy TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prediction_id) REFERENCES predictions_log (id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS adaptive_weights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weight_set_name TEXT NOT NULL,
            probability_weight REAL NOT NULL,
            diversity_weight REAL NOT NULL,
            historical_weight REAL NOT NULL,
            risk_adjusted_weight REAL NOT NULL,
            performance_score REAL NOT NULL,
            optimization_algorithm TEXT NOT NULL,
            dataset_hash TEXT NOT NULL,
            is_active BOOLEAN DEFAULT FALSE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pattern_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT NOT NULL,
            pattern_description TEXT NOT NULL,
            pattern_data TEXT NOT NULL,
            success_rate REAL NOT NULL,
            frequency INTEGER NOT NULL,
            confidence_score REAL NOT NULL,
            date_range_start DATE NOT NULL,
            date_range_end DATE NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reliable_plays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            n1 INTEGER NOT NULL,
            n2 INTEGER NOT NULL,
            n3 INTEGER NOT NULL,
            n4 INTEGER NOT NULL,
            n5 INTEGER NOT NULL,
            pb INTEGER NOT NULL,
            reliability_score REAL NOT NULL,
            performance_history TEXT NOT NULL,
            win_rate REAL NOT NULL,
            avg_score REAL NOT NULL,
            times_generated INTEGER NOT NULL,
            last_generated DATETIME NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS model_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feedback_type TEXT NOT NULL,
            component_name TEXT NOT NULL,
            original_value REAL NOT NULL,
            adjusted_value REAL NOT NULL,
            adjustment_reason TEXT NOT NULL,
            performance_impact REAL NOT NULL,
            dataset_hash TEXT NOT NULL,
            model_version TEXT NOT NULL,
            is_applied BOOLEAN DEFAULT FALSE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            applied_at DATETIME NULL
        )
    """)


def _create_indexes(cursor):
    """Create performance indexes for frequently queried columns."""
    indexes = [
        ("idx_predictions_log_created_at", "predictions_log", "created_at DESC"),
        ("idx_predictions_log_target_date", "predictions_log", "target_draw_date"),
        ("idx_performance_tracking_prediction_id", "performance_tracking", "prediction_id"),
        ("idx_performance_tracking_draw_date", "performance_tracking", "draw_date"),
        ("idx_powerball_draws_date", "powerball_draws", "draw_date"),
        ("idx_pipeline_executions_status", "pipeline_executions", "status"),
        ("idx_pipeline_executions_start_time", "pipeline_executions", "start_time DESC"),
        ("idx_pipeline_executions_trigger_type", "pipeline_executions", "trigger_type"),
        ("idx_pipeline_executions_execution_id", "pipeline_executions", "execution_id"),
        ("idx_validation_results_prediction_id", "validation_results", "prediction_id"),
        ("idx_validation_results_draw_date", "validation_results", "draw_date"),
        # Weekly verification limits indexes
        ("idx_weekly_limits_user_week", "weekly_verification_limits", "user_id, week_start_date"),
        ("idx_weekly_limits_device_week", "weekly_verification_limits", "device_fingerprint, week_start_date"),
        ("idx_weekly_limits_week_start", "weekly_verification_limits", "week_start_date DESC"),
        # IP rate limiting indexes
        ("idx_ip_limits_ip_hour", "ip_rate_limits", "ip_address, hour_window"),
        ("idx_ip_limits_hour_window", "ip_rate_limits", "hour_window DESC"),
        # Stripe billing indexes
        ("idx_idempotency_keys_key", "idempotency_keys", "idempotency_key"),
        ("idx_webhook_events_stripe_id", "webhook_events", "stripe_event_id"),
        ("idx_webhook_events_type", "webhook_events", "event_type"),
        ("idx_webhook_events_processed", "webhook_events", "processed"),
        ("idx_stripe_customers_email", "stripe_customers", "email"),
        ("idx_stripe_customers_stripe_id", "stripe_customers", "stripe_customer_id"),
        ("idx_stripe_subscriptions_customer", "stripe_subscriptions", "stripe_customer_id"),
        ("idx_stripe_subscriptions_status", "stripe_subscriptions", "status"),
        ("idx_premium_passes_email", "premium_passes", "email"),
        ("idx_premium_passes_token", "premium_passes", "pass_token"),
        ("idx_premium_passes_jti", "premium_passes", "jti"),
        ("idx_premium_passes_subscription", "premium_passes", "stripe_subscription_id"),
        ("idx_premium_pass_devices_pass", "premium_pass_devices", "pass_id"),
        ("idx_premium_pass_devices_fingerprint", "premium_pass_devices", "device_fingerprint")
    ]

    for index_name, table_name, columns in indexes:
        try:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns})")
        except sqlite3.Error as e:
            logger.warning(f"Error creating index {index_name}: {e}")

    logger.info("Database performance indexes created successfully")




def get_latest_draw_date() -> Optional[str]:
    """Retrieve the most recent draw date from the database."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(draw_date) FROM powerball_draws")
            result = cursor.fetchone()
            latest_date = result[0] if result else None
            if latest_date:
                logger.info(f"Latest draw date in DB: {latest_date}")
            else:
                logger.info("No existing data found in 'powerball_draws'.")
            return latest_date
    except sqlite3.Error as e:
        logger.error(f"Failed to get latest draw date: {e}")
        return None


def bulk_insert_draws(df: pd.DataFrame):
    """Insert or replace a batch of draw data into the database from a DataFrame."""
    if df.empty:
        logger.info("No new draws to insert.")
        return

    try:
        with get_db_connection() as conn:
            df.to_sql('powerball_draws', conn, if_exists='append', index=False)
            logger.info(f"Successfully inserted {len(df)} rows into the database.")
    except sqlite3.IntegrityError as e:
        logger.warning(f"Integrity constraint violation during bulk insert: {e}. Using upsert method.")
        _upsert_draws(df)
    except sqlite3.Error as e:
        logger.error(f"SQLite error during bulk insert: {e}")


def _upsert_draws(df: pd.DataFrame):
    """Slower, row-by-row insert/replace for handling duplicates."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            for _, row in df.iterrows():
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO powerball_draws (draw_date, n1, n2, n3, n4, n5, pb)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, tuple(row))
            conn.commit()
            logger.info(f"Successfully upserted {len(df)} rows.")
    except sqlite3.Error as e:
        logger.error(f"SQLite error during upsert: {e}")


def get_all_draws() -> pd.DataFrame:
    """Retrieve all historical draw data from the database."""
    try:
        with get_db_connection() as conn:
            df = pd.read_sql_query(
                "SELECT * FROM powerball_draws ORDER BY draw_date ASC",
                conn,
                parse_dates=['draw_date']
            )
            logger.info(f"Successfully loaded {len(df)} rows from the database.")
            return df
    except sqlite3.Error as e:
        logger.error(f"SQLite error retrieving draws data: {e}")
        return pd.DataFrame()
    except pd.errors.DatabaseError as e:
        logger.error(f"Pandas database error: {e}")
        return pd.DataFrame()



def save_prediction_log(prediction_data: Dict[str, Any], allow_simulation: bool = False, execution_source: Optional[str] = None) -> Optional[int]:
    """Save a prediction to the predictions_log table."""
    logger.debug(f"Received prediction data: {prediction_data}")

    # Validate execution source
    authorized_sources = ["manual_dashboard", "automatic_scheduler", "pipeline_execution"]

    if execution_source and execution_source not in authorized_sources:
        logger.error(f"UNAUTHORIZED: Rejected prediction from source: {execution_source}")
        return None

    # Process and validate prediction data
    model_version = str(prediction_data.get("model_version", "1.0.0-pipeline"))
    dataset_hash = str(prediction_data.get("dataset_hash", ""))

    if not dataset_hash or len(dataset_hash) < 10:
        import hashlib
        import time
        timestamp_str = str(time.time())
        dataset_hash = hashlib.md5(f"pipeline_{timestamp_str}".encode()).hexdigest()[:16]
        logger.info(f"Generated dataset_hash for pipeline prediction: {dataset_hash}")

    # Validate simulated data
    if not allow_simulation and execution_source != "pipeline_execution":
        if (model_version in ["fallback", "test", "simulated"] or 
            dataset_hash in ["simulated", "test", "fallback"]):
            logger.warning(f"REJECTED: Non-pipeline prediction - model={model_version}, hash={dataset_hash}")
            return None

    # Accept all pipeline_execution predictions
    if execution_source == "pipeline_execution":
        logger.info(f"ACCEPTING pipeline prediction - model={model_version}, hash={dataset_hash}")
        prediction_data["model_version"] = model_version
        prediction_data["dataset_hash"] = dataset_hash

    # Sanitize and validate prediction data
    sanitized_data = _sanitize_prediction_data(prediction_data, allow_simulation)
    if sanitized_data is None:
        logger.error("Prediction data is invalid after sanitization.")
        return None

    # Handle target draw date
    target_draw_date_str = sanitized_data.get('target_draw_date')
    if not target_draw_date_str:
        target_draw_date_str = calculate_next_drawing_date()
        logger.debug(f"Target draw date not provided, calculated: {target_draw_date_str}")

    if not _validate_target_draw_date(target_draw_date_str):
        logger.error(f"Invalid target_draw_date format: {target_draw_date_str}")
        raise ValueError(f"Invalid target_draw_date format: {target_draw_date_str}")

    # Additional validation to prevent data corruption
    if len(target_draw_date_str) != 10 or target_draw_date_str.count('-') != 2:
        logger.error(f"CORRUPTION DETECTED: target_draw_date has invalid format: {target_draw_date_str}")
        raise ValueError(f"Corrupted target_draw_date detected: {target_draw_date_str}")

    if not _is_valid_drawing_date(target_draw_date_str):
        logger.warning(f"Target draw date {target_draw_date_str} is not a valid Powerball drawing day.")

    # Safe type conversion to avoid numpy issues
    def safe_int(value):
        if hasattr(value, 'item'):
            return int(value.item())
        return int(value)

    def safe_float(value):
        if hasattr(value, 'item'):
            return float(value.item())
        return float(value)

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO predictions_log
                (timestamp, n1, n2, n3, n4, n5, powerball, score_total,
                 model_version, dataset_hash, json_details_path, target_draw_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(sanitized_data['timestamp']),
                safe_int(sanitized_data['numbers'][0]),
                safe_int(sanitized_data['numbers'][1]),
                safe_int(sanitized_data['numbers'][2]),
                safe_int(sanitized_data['numbers'][3]),
                safe_int(sanitized_data['numbers'][4]),
                safe_int(sanitized_data['powerball']),
                safe_float(sanitized_data['score_total']),
                str(sanitized_data['model_version']),
                str(sanitized_data['dataset_hash']),
                sanitized_data.get('json_details_path', None),
                target_draw_date_str
            ))

            prediction_id = cursor.lastrowid
            conn.commit()

            logger.info(f"Prediction saved with ID {prediction_id}.")
            return prediction_id

    except sqlite3.Error as e:
        logger.error(f"Error saving prediction log: {e}")
        return None


def get_prediction_history(limit: int = 100):
    """Retrieve prediction history from the database."""
    try:
        with get_db_connection() as conn:
            query = """
                SELECT id, timestamp, n1, n2, n3, n4, n5, powerball,
                       score_total, model_version, dataset_hash,
                       json_details_path, created_at
                FROM predictions_log
                ORDER BY created_at DESC
                LIMIT ?
            """
            df = pd.read_sql(query, conn, params=(limit,))
            logger.info(f"Retrieved {len(df)} prediction records from history")
            return df

    except sqlite3.Error as e:
        logger.error(f"Error retrieving prediction history: {e}")
        return pd.DataFrame()


# Phase 4: Adaptive Feedback System Database Methods

def save_performance_tracking(prediction_id: int, draw_date: str, actual_numbers: List[int], actual_pb: int, matches_main: int, matches_pb: int, prize_tier: str, score_accuracy: float, component_accuracy: Dict) -> Optional[int]:
    """Saves performance tracking data for a prediction against actual draw results."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO performance_tracking
                (prediction_id, draw_date, actual_n1, actual_n2, actual_n3, actual_n4, actual_n5,
                 actual_pb, matches_main, matches_pb, prize_tier, score_accuracy, component_accuracy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (prediction_id, draw_date, actual_numbers[0],
                  actual_numbers[1], actual_numbers[2], actual_numbers[3],
                  actual_numbers[4], actual_pb, matches_main, matches_pb,
                  prize_tier, score_accuracy,
                  json.dumps(component_accuracy, cls=NumpyEncoder)))

            tracking_id = cursor.lastrowid
            conn.commit()

            logger.info(
                f"Performance tracking saved with ID {tracking_id} for prediction {prediction_id}"
            )
            return tracking_id

    except sqlite3.Error as e:
        logger.error(f"Error saving performance tracking: {e}")
        return None


def save_adaptive_weights(weight_set_name: str, weights: Dict[str, float], performance_score: float, optimization_algorithm: str, dataset_hash: str, is_active: bool = False) -> Optional[int]:
    """Saves adaptive weight configuration."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            if is_active:
                cursor.execute("UPDATE adaptive_weights SET is_active = FALSE")

            cursor.execute(
                """
                INSERT INTO adaptive_weights
                (weight_set_name, probability_weight, diversity_weight, historical_weight,
                 risk_adjusted_weight, performance_score, optimization_algorithm, dataset_hash, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (weight_set_name, weights.get('probability', 0.4),
                  weights.get('diversity', 0.25), weights.get('historical', 0.2), weights.get('risk_adjusted', 0.15), performance_score,
                  optimization_algorithm, dataset_hash, is_active))

            weights_id = cursor.lastrowid
            conn.commit()

            logger.info(
                f"Adaptive weights saved with ID {weights_id}: {weight_set_name}"
            )
            return weights_id

    except sqlite3.Error as e:
        logger.error(f"Error saving adaptive weights: {e}")
        return None


def get_active_adaptive_weights() -> Optional[Dict]:
    """Retrieves the currently active adaptive weights."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT weight_set_name, probability_weight, diversity_weight, historical_weight,
                       risk_adjusted_weight, performance_score, optimization_algorithm, dataset_hash
                FROM adaptive_weights
                WHERE is_active = TRUE
                ORDER BY created_at DESC
                LIMIT 1
            """)

            result = cursor.fetchone()
            if result:
                return {
                    'weight_set_name': result[0],
                    'weights': {
                        'probability': result[1],
                        'diversity': result[2],
                        'historical': result[3],
                        'risk_adjusted': result[4]
                    },
                    'performance_score': result[5],
                    'optimization_algorithm': result[6],
                    'dataset_hash': result[7]
                }
            return None

    except sqlite3.Error as e:
        logger.error(f"Error retrieving active adaptive weights: {e}")
        return None


def save_pattern_analysis(pattern_type: str, pattern_description: str, pattern_data: Dict, success_rate: float, frequency: int, confidence_score: float, date_range_start: str, date_range_end: str) -> Optional[int]:
    """Saves pattern analysis results."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO pattern_analysis
                (pattern_type, pattern_description, pattern_data, success_rate, frequency,
                 confidence_score, date_range_start, date_range_end)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (pattern_type, pattern_description,
                  json.dumps(pattern_data, cls=NumpyEncoder), success_rate, frequency,
                  confidence_score, date_range_start, date_range_end))

            pattern_id = cursor.lastrowid
            conn.commit()

            logger.info(
                f"Pattern analysis saved with ID {pattern_id}: {pattern_type}")
            return pattern_id

    except sqlite3.Error as e:
        logger.error(f"Error saving pattern analysis: {e}")
        return None


def save_reliable_play(numbers: List[int], powerball: int, reliability_score: float, performance_history: Dict, win_rate: float, avg_score: float) -> Optional[int]:
    """Saves or updates a reliable play combination."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, times_generated FROM reliable_plays
                WHERE n1 = ? AND n2 = ? AND n3 = ? AND n4 = ? AND n5 = ? AND pb = ?
            """, tuple(numbers + [powerball]))

            existing = cursor.fetchone()

            if existing:
                cursor.execute(
                    """
                    UPDATE reliable_plays
                    SET reliability_score = ?, performance_history = ?, win_rate = ?,
                        avg_score = ?, times_generated = ?, last_generated = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (reliability_score,
                      json.dumps(performance_history, cls=NumpyEncoder),
                      win_rate, avg_score, existing[1] + 1, existing[0]))
                play_id = existing[0]
                logger.info(f"Updated reliable play ID {play_id}")
            else:
                cursor.execute(
                    """
                    INSERT INTO reliable_plays
                    (n1, n2, n3, n4, n5, pb, reliability_score, performance_history,
                     win_rate, avg_score, times_generated, last_generated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (numbers[0], numbers[1], numbers[2], numbers[3],
                      numbers[4], powerball, reliability_score,
                      json.dumps(performance_history, cls=NumpyEncoder), win_rate, avg_score, 1))
                play_id = cursor.lastrowid
                logger.info(f"Saved new reliable play ID {play_id}")

            conn.commit()
            return play_id

    except sqlite3.Error as e:
        logger.error(f"Error saving reliable play: {e}")
        return None


def get_reliable_plays(limit: int = 20, min_reliability_score: float = 0.7) -> pd.DataFrame:
    """Retrieves reliable plays ranked by reliability score."""
    try:
        with get_db_connection() as conn:
            query = """
                SELECT id, n1, n2, n3, n4, n5, pb, reliability_score, win_rate,
                       avg_score, times_generated, last_generated, created_at
                FROM reliable_plays
                WHERE reliability_score >= ?
                ORDER BY reliability_score DESC, times_generated DESC
                LIMIT ?
            """
            # Load reliable plays from database with filtering on reliability score and limit
            df = pd.read_sql(query, conn, params=(min_reliability_score, limit))
            logger.info(f"Retrieved {len(df)} reliable plays")
            return df
    except sqlite3.Error as e:
        logger.error(f"Error retrieving reliable plays: {e}")
        return pd.DataFrame()


def save_model_feedback(feedback_type: str, component_name: str, original_value: float, adjusted_value: float, adjustment_reason: str, performance_impact: float, dataset_hash: str, model_version: str) -> Optional[int]:
    """Saves model feedback for adaptive learning."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO model_feedback
                (feedback_type, component_name, original_value, adjusted_value,
                 adjustment_reason, performance_impact, dataset_hash, model_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (feedback_type, component_name, original_value,
                  adjusted_value, adjustment_reason, performance_impact,
                  dataset_hash, model_version))

            feedback_id = cursor.lastrowid
            conn.commit()

            logger.info(
                f"Model feedback saved with ID {feedback_id}: {feedback_type}")
            return feedback_id

    except sqlite3.Error as e:
        logger.error(f"Error saving model feedback: {e}")
        return None


def get_performance_analytics(days_back: int = 30) -> Dict:
    """Retrieves performance analytics for the specified time period."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    COUNT(*) as total_predictions,
                    AVG(pt.score_accuracy) as avg_accuracy,
                    AVG(pt.matches_main) as avg_main_matches,
                    AVG(pt.matches_pb) as avg_pb_matches,
                    COUNT(CASE WHEN pt.prize_tier != 'Non-winning' THEN 1 END) as winning_predictions
                FROM performance_tracking pt
                JOIN predictions_log pl ON pt.prediction_id = pl.id
                WHERE pt.created_at >= datetime('now', '-' || ? || ' days')
            """, (days_back,))

            overall_stats = cursor.fetchone()

            cursor.execute(
                """
                SELECT pt.prize_tier, COUNT(*) as count
                FROM performance_tracking pt
                JOIN predictions_log pl ON pt.prediction_id = pl.id
                WHERE pt.created_at >= datetime('now', '-' || ? || ' days')
                GROUP BY pt.prize_tier
                ORDER BY count DESC
            """, (days_back,))

            prize_distribution = dict(cursor.fetchall())

            cursor.execute(
                """
                SELECT DATE(pt.created_at) as date, AVG(pt.score_accuracy) as avg_accuracy
                FROM performance_tracking pt
                JOIN predictions_log pl ON pt.prediction_id = pl.id
                WHERE pt.created_at >= datetime('now', '-' || ? || ' days')
                GROUP BY DATE(pt.created_at)
                ORDER BY date
            """, (days_back,))

            accuracy_trends = dict(cursor.fetchall())

            analytics = {
                'period_days': days_back,
                'total_predictions': overall_stats[0] if overall_stats and overall_stats[0] else 0,
                'avg_accuracy': overall_stats[1] if overall_stats and overall_stats[1] else 0.0,
                'avg_main_matches': overall_stats[2] if overall_stats and overall_stats[2] else 0.0,
                'avg_pb_matches': overall_stats[3] if overall_stats and overall_stats[3] else 0.0,
                'winning_predictions': overall_stats[4] if overall_stats and overall_stats[4] else 0,
                'win_rate': (overall_stats[4] / overall_stats[0] * 100) if overall_stats and overall_stats[0] > 0 else 0.0,
                'prize_distribution': prize_distribution,
                'accuracy_trends': accuracy_trends
            }

            logger.info(
                f"Retrieved performance analytics for {days_back} days")
            return analytics

    except sqlite3.Error as e:
        logger.error(f"Error retrieving performance analytics: {e}")
        return {
            'total_predictions': 0,
            'total_winnings': 0.0,
            'average_score': 0.0,
            'accuracy_rate': 0.0,
            'predictions_by_date': [],
            'performance_by_rank': []
        }


def get_prediction_details(prediction_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve complete prediction details from the JSON file."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT json_details_path FROM predictions_log WHERE id = ?",
                (prediction_id,))

            result = cursor.fetchone()
            if not result:
                logger.warning(f"Prediction with ID {prediction_id} not found")
                return None

            json_path = result[0]

            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    details = json.load(f)
                return details
            else:
                logger.warning(f"JSON file not found: {json_path}")
                return None

    except (sqlite3.Error, FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error retrieving prediction details for ID {prediction_id}: {e}")
        return None

def get_evaluated_predictions_count(execution_id: str) -> int:
    """Get count of evaluated predictions for a specific execution"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Count evaluated predictions for this execution timeframe
            cursor.execute("""
                SELECT COUNT(*) 
                FROM predictions_log 
                WHERE evaluated = 1 
                AND target_draw_date IS NOT NULL
                AND prize_amount IS NOT NULL
                AND created_at >= (
                    SELECT start_time FROM pipeline_executions 
                    WHERE execution_id = ?
                )
                AND created_at <= COALESCE((
                    SELECT end_time FROM pipeline_executions 
                    WHERE execution_id = ?
                ), datetime('now'))
            """, (execution_id, execution_id))

            count = cursor.fetchone()[0] or 0
            logger.info(f"Found {count} evaluated predictions for execution {execution_id}")
            return count

    except Exception as e:
        logger.error(f"Error counting evaluated predictions for execution {execution_id}: {e}")
        return 0

def get_evaluated_predictions_for_execution(execution_id: str) -> Optional[Dict[str, Any]]:
    """Get evaluation results for a specific execution"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Get predictions that were evaluated for this execution
            cursor.execute("""
                SELECT 
                    numbers, powerball, prize_amount, matches, target_draw_date, rank
                FROM predictions_log 
                WHERE evaluated = 1 
                AND target_draw_date IS NOT NULL
                AND created_at >= (
                    SELECT start_time FROM pipeline_executions 
                    WHERE execution_id = ?
                )
                AND created_at <= COALESCE((
                    SELECT end_time FROM pipeline_executions 
                    WHERE execution_id = ?
                ), datetime('now'))
                ORDER BY rank ASC, prize_amount DESC
                LIMIT 100
            """, (execution_id, execution_id))

            predictions_data = cursor.fetchall()

            if not predictions_data:
                return None

            # Get target draw date (should be same for all)
            target_draw_date = predictions_data[0][4] if predictions_data else None

            # Format predictions
            predictions = []
            for row in predictions_data:
                try:
                    numbers = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                    predictions.append({
                        'numbers': numbers,
                        'powerball': row[1],
                        'prize_amount': row[2] or 0,
                        'matches': row[3] or 0,
                        'rank': row[5] or 0
                    })
                except Exception as e:
                    logger.warning(f"Error parsing prediction data: {e}")
                    continue

            return {
                'predictions': predictions,
                'target_draw_date': target_draw_date,
                'execution_id': execution_id
            }

    except Exception as e:
        logger.error(f"Error getting evaluated predictions for execution {execution_id}: {e}")
        return None

def get_predictions_by_dataset_hash(dataset_hash: str) -> pd.DataFrame:
    """Retrieve all predictions associated with a specific dataset hash."""
    try:
        with get_db_connection() as conn:
            query = """
                SELECT id, timestamp, n1, n2, n3, n4, n5, powerball,
                       score_total, model_version, created_at
                FROM predictions_log
                WHERE dataset_hash = ?
                ORDER BY created_at DESC
            """
            df = pd.read_sql(query, conn, params=(dataset_hash,))
            logger.debug(f"Executed query with dataset_hash={dataset_hash}")
            logger.info(
                f"Retrieved {len(df)} predictions for dataset hash {dataset_hash}"
            )
            return df
    except sqlite3.Error as e:
        logger.error(f"Error retrieving predictions by dataset hash: {e}")
        return pd.DataFrame()


def get_predictions_grouped_by_date(limit_dates: int = 25) -> List[Dict]:
    """
    Get predictions grouped by date for draws that have already occurred.
    Only includes REAL pipeline predictions for draws with official results.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT DISTINCT
                    pd.draw_date as target_date,
                    COUNT(pl.id) as total_predictions,
                    COUNT(CASE WHEN pl.evaluated = 1 AND pl.prize_amount > 0 THEN 1 END) as winning_predictions,
                    COUNT(CASE WHEN pl.evaluated = 1 THEN 1 END) as evaluated_predictions,
                    SUM(CASE WHEN pl.evaluated = 1 THEN pl.prize_amount ELSE 0 END) as total_prizes
                FROM powerball_draws pd
                INNER JOIN predictions_log pl ON COALESCE(pl.target_draw_date, DATE(pl.created_at)) = pd.draw_date
                WHERE pl.created_at IS NOT NULL 
                    AND pl.model_version NOT IN ('fallback', 'test', 'simulated', '1.0.0-test', 'default')
                    AND pl.dataset_hash NOT IN ('simulated', 'test', 'fallback', 'default')
                    AND pl.score_total > 0
                    AND LENGTH(pl.dataset_hash) >= 16
                    AND pl.json_details_path IS NOT NULL
                    AND pl.target_draw_date IS NOT NULL
                GROUP BY pd.draw_date
                HAVING COUNT(pl.id) > 0
                ORDER BY pd.draw_date DESC
                LIMIT ?
            """, (limit_dates,))

            date_groups = cursor.fetchall()

            grouped_results = []

            spanish_months = {
                1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun',
                7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic'
            }

            for date_row in date_groups:
                target_date = date_row[0]
                total_predictions_for_date = date_row[1]

                cursor.execute(
                    """
                    SELECT
                        pl.id, pl.timestamp, pl.n1, pl.n2, pl.n3, pl.n4, pl.n5, pl.powerball,
                        pt.matches_main, pt.matches_pb, pt.prize_tier,
                        COALESCE(pl.target_draw_date, DATE(pl.created_at)) as target_draw_date,
                        pl.created_at
                    FROM predictions_log pl
                    LEFT JOIN performance_tracking pt ON pl.id = pt.prediction_id
                    WHERE COALESCE(pl.target_draw_date, DATE(pl.created_at)) = ?
                    ORDER BY pl.score_total DESC
                """, (target_date,))

                predictions_data = cursor.fetchall()

                predictions = []
                total_prize = 0.0
                winning_predictions = 0
                best_prize_amount = 0.0
                best_prize_description = "No matches"

                for pred_row in predictions_data:
                    prediction_numbers = [pred_row[2], pred_row[3], pred_row[4], pred_row[5], pred_row[6]]
                    prediction_pb = pred_row[7]
                    prediction_target_date = pred_row[11] or target_date
                    prediction_created_at = pred_row[12]

                    cursor.execute(
                        "SELECT n1, n2, n3, n4, n5, pb FROM powerball_draws WHERE draw_date = ?",
                        (prediction_target_date,))
                    official_result = cursor.fetchone()

                    matches_main = 0
                    powerball_match = False
                    prize_amount = 0.0
                    prize_description = "No matches"

                    if official_result:
                        winning_numbers = [official_result[0], official_result[1], official_result[2], official_result[3], official_result[4]]
                        winning_pb = official_result[5]

                        matches_main = len(set(prediction_numbers) & set(winning_numbers))
                        powerball_match = prediction_pb == winning_pb

                        try:
                            prize_amount, prize_description = calculate_prize_amount(matches_main, powerball_match)
                        except Exception as e:
                            logger.error(f"Error calculating prize amount: {e}")
                            prize_amount, prize_description = 0.0, "Error calculating prize"

                    total_prize += prize_amount
                    if prize_amount > 0:
                        winning_predictions += 1

                    if prize_amount > best_prize_amount:
                        best_prize_amount = prize_amount
                        best_prize_description = prize_description

                    prediction_detail = {
                        "prediction_id": pred_row[0],
                        "timestamp": pred_row[1],
                        "numbers": prediction_numbers,
                        "powerball": prediction_pb,
                        "score": float(pred_row[8]),
                        "model_version": pred_row[9],
                        "dataset_hash": pred_row[10],
                        "target_draw_date": prediction_target_date,
                        "created_at": prediction_created_at,
                        "matches_main": matches_main,
                        "powerball_match": powerball_match,
                        "prize_amount": prize_amount,
                        "prize_description": prize_description,
                        "has_prize": prize_amount > 0
                    }
                    predictions.append(prediction_detail)

                try:
                    date_obj = datetime.strptime(target_date, '%Y-%m-%d')
                    formatted_date = f"{date_obj.day} {spanish_months[date_obj.month]} {date_obj.year}"
                except Exception as e:
                    logger.warning(f"Failed to format date: {e}")
                    formatted_date = target_date

                if best_prize_amount >= 100000000:
                    total_prize_display = "JACKPOT!"
                elif total_prize >= 1000000:
                    total_prize_display = f"${total_prize/1000000:.1f}M"
                elif total_prize >= 1000:
                    total_prize_display = f"${total_prize/1000:.0f}K"
                elif total_prize > 0:
                    total_prize_display = f"${total_prize:.0f}"
                else:
                    total_prize_display = "$0"

                win_rate = (winning_predictions / total_predictions_for_date * 100) if total_predictions_for_date > 0 else 0.0

                grouped_result = {
                    "date": target_date,
                    "formatted_date": formatted_date,
                    "total_plays": total_predictions_for_date,
                    "winning_plays": winning_predictions,
                    "win_rate_percentage": f"{win_rate:.1f}%",
                    "best_prize": best_prize_description,
                    "best_prize_amount": best_prize_amount,
                    "total_prize_amount": total_prize,
                    "total_prize_display": total_prize_display,
                    "predictions": predictions,
                    "is_target_draw_date": True,
                    "context": f"Predictions generated for drawing on {formatted_date}"
                }
                grouped_results.append(grouped_result)

            logger.info(
                f"Retrieved {len(grouped_results)} grouped prediction dates with {sum(g['total_plays'] for g in grouped_results)} total predictions"
            )
            return grouped_results

    except sqlite3.Error as e:
        logger.error(f"Error retrieving grouped predictions by date: {e}")
        return []


def get_predictions_with_results_comparison(limit: int = 20) -> List[Dict]:
    """
    Obtain historical predictions with comparisons against official results,
    including calculation of prizes won.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT
                    pl.id, pl.timestamp, pl.n1, pl.n2, pl.n3, pl.n4, pl.n5, pl.powerball,
                    pd.draw_date, pd.n1 as actual_n1, pd.n2 as actual_n2, pd.n3 as actual_n3,
                    pd.n4 as actual_n4, pd.n5 as actual_n5, pd.pb as actual_pb,
                    pt.matches_main, pt.matches_pb, pt.prize_tier
                FROM predictions_log pl
                LEFT JOIN performance_tracking pt ON pl.id = pt.prediction_id
                LEFT JOIN powerball_draws pd ON pt.draw_date = pd.draw_date
                WHERE pt.id IS NOT NULL
                ORDER BY pl.created_at DESC
                LIMIT ?
            """

            cursor.execute(query, (limit,))
            results = cursor.fetchall()

            comparisons = []
            for row in results:
                prediction_numbers = [row[2], row[3], row[4], row[5], row[6]]
                prediction_pb = row[7]
                prediction_date = row[1]

                if row[8]:  # If official result exists
                    actual_numbers = [row[9], row[10], row[11], row[12], row[13]]
                    actual_pb = row[14]
                    draw_date = row[8]

                    matched_numbers = []
                    for pred_num in prediction_numbers:
                        if pred_num in actual_numbers:
                            matched_numbers.append(pred_num)

                    powerball_matched = prediction_pb == actual_pb
                    main_matches = len(matched_numbers)
                    try:
                        prize_amount, prize_description = calculate_prize_amount(main_matches, powerball_matched)
                    except Exception as e:
                        logger.error(f"Error calculating prize amount: {e}")
                        prize_amount, prize_description = 0.0, "Error calculating prize"

                    comparison = {
                        "prediction": {
                            "numbers": prediction_numbers,
                            "powerball": prediction_pb,
                            "date": prediction_date
                        },
                        "result": {
                            "numbers": actual_numbers,
                            "powerball": actual_pb,
                            "date": draw_date
                        },
                        "comparison": {
                            "matched_numbers": matched_numbers,
                            "powerball_matched": powerball_matched,
                            "total_matches": main_matches,
                            "prize_amount": prize_amount,
                            "prize_description": prize_description
                        }
                    }
                    comparisons.append(comparison)

            logger.info(
                f"Retrieved {len(comparisons)} prediction comparisons with prize calculations"
            )
            return comparisons

    except sqlite3.Error as e:
        logger.error(
            f"Error retrieving predictions with results comparison: {e}")
        return []


def get_grouped_predictions_with_results_comparison(limit_groups: int = 5) -> List[Dict]:
    """
    Get predictions grouped by official result for the hybrid design.
    Each group contains an official result with its corresponding 5 ADAPTIVE predictions.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT pd.draw_date, pd.n1, pd.n2, pd.n3, pd.n4, pd.n5, pd.pb
                FROM powerball_draws pd
                ORDER BY pd.draw_date DESC
                LIMIT ?
            """, (limit_groups,))

            official_results = cursor.fetchall()

            grouped_comparisons = []

            for result_row in official_results:
                draw_date = result_row[0]
                winning_numbers = [result_row[1], result_row[2], result_row[3], result_row[4], result_row[5]]
                winning_powerball = result_row[6]

                cursor.execute(
                    """
                    SELECT
                        pl.id, pl.timestamp, pl.n1, pl.n2, pl.n3, pl.n4, pl.n5, pl.powerball,
                        pt.matches_main, pt.matches_pb, pt.prize_tier
                    FROM predictions_log pl
                    INNER JOIN performance_tracking pt ON pl.id = pt.prediction_id
                    WHERE pt.draw_date = ?
                    ORDER BY pl.created_at ASC
                    LIMIT 5
                """, (draw_date,))

                predictions_data = cursor.fetchall()

                if not predictions_data:
                    logger.debug(f"No real predictions found for draw date {draw_date}, skipping group")
                    continue

                predictions = []
                total_prize = 0
                total_matches = 0
                winning_predictions = 0

                for i, pred_row in enumerate(predictions_data):
                    prediction_numbers = [pred_row[2], pred_row[3], pred_row[4], pred_row[5], pred_row[6]]
                    prediction_pb = pred_row[7]
                    prediction_date = pred_row[1]

                    number_matches = []
                    for j, pred_num in enumerate(prediction_numbers):
                        is_match = pred_num in winning_numbers
                        number_matches.append({"number": pred_num, "position": j, "is_match": is_match})

                    powerball_match = prediction_pb == winning_powerball
                    main_matches = sum(1 for match in number_matches if match["is_match"])
                    try:
                        prize_amount, prize_description = calculate_prize_amount(main_matches, powerball_match)
                    except Exception as calc_error:
                        logger.error(f"Prize calculation failed: {calc_error}")
                        prize_amount, prize_description = 0.0, "Calculation error"

                    if prize_amount >= 100000000:
                        prize_display = "JACKPOT!"
                    elif prize_amount >= 1000000:
                        prize_display = f"${prize_amount/1000000:.1f}M"
                    elif prize_amount >= 1000:
                        prize_display = f"${prize_amount/1000:.0f}K"
                    elif prize_amount > 0:
                        prize_display = f"${prize_amount:.2f}"
                    else:
                        prize_display = "$0.00"

                    prediction_data = {
                        "prediction_id": pred_row[0],
                        "prediction_date": prediction_date,
                        "prediction_numbers": prediction_numbers,
                        "prediction_powerball": prediction_pb,
                        "winning_numbers": winning_numbers,
                        "winning_powerball": winning_powerball,
                        "number_matches": number_matches,
                        "powerball_match": powerball_match,
                        "total_matches": main_matches,
                        "prize_amount": prize_amount,
                        "prize_description": prize_description,
                        "prize_display": prize_display,
                        "has_prize": prize_amount > 0,
                        "play_number": i + 1
                    }
                    predictions.append(prediction_data)

                    total_prize += prize_amount
                    total_matches += main_matches
                    if prize_amount > 0:
                        winning_predictions += 1

                num_predictions = len(predictions)
                avg_matches = total_matches / num_predictions if num_predictions > 0 else 0
                win_rate = (winning_predictions / num_predictions * 100) if num_predictions > 0 else 0

                jackpot_count = sum(1 for p in predictions if p["prize_amount"] >= 100000000)
                if jackpot_count > 0:
                    total_prize_display = f"{jackpot_count} JACKPOT{'S' if jackpot_count > 1 else ''}"
                elif total_prize >= 1000000:
                    total_prize_display = f"${total_prize/1000000:.1f}M"
                elif total_prize >= 1000:
                    total_prize_display = f"${total_prize/1000:.0f}K"
                elif total_prize > 0:
                    total_prize_display = f"${total_prize:.0f}"
                else:
                    total_prize_display = "$0"

                best_prediction = max(predictions, key=lambda p: (p["total_matches"], p["powerball_match"], p["prize_amount"]))
                if best_prediction["total_matches"] == 5 and best_prediction["powerball_match"]:
                    best_result = "JACKPOT"
                elif best_prediction["total_matches"] == 5:
                    best_result = "5 Numbers"
                elif best_prediction["total_matches"] == 4 and best_prediction["powerball_match"]:
                    best_result = "4 + PB"
                elif best_prediction["total_matches"] == 4:
                    best_result = "4 Numbers"
                elif best_prediction["total_matches"] == 3 and best_prediction["powerball_match"]:
                    best_result = "3 + PB"
                elif best_prediction["total_matches"] == 3:
                    best_result = "3 Numbers"
                elif best_prediction["total_matches"] == 2 and best_prediction["powerball_match"]:
                    best_result = "2 + PB"
                elif best_prediction["total_matches"] == 1 and best_prediction["powerball_match"]:
                    best_result = "1 + PB"
                elif best_prediction["powerball_match"]:
                    best_result = "PB Only"
                else:
                    best_result = "No Match"

                group_data = {
                    "draw_date": draw_date,
                    "winning_numbers": winning_numbers,
                    "winning_powerball": winning_powerball,
                    "prediction_date": predictions[0]["prediction_date"] if predictions else None,
                    "predictions": predictions,
                    "summary": {
                        "total_prize": total_prize,
                        "total_prize_display": total_prize_display,
                        "predictions_with_prizes": winning_predictions,
                        "win_rate_percentage": f"{win_rate:.0f}",
                        "avg_matches": f"{avg_matches:.1f}",
                        "best_result": best_result,
                        "total_predictions": len(predictions)
                    }
                }
                grouped_comparisons.append(group_data)

            logger.info(
                f"Retrieved {len(grouped_comparisons)} grouped prediction comparisons with {sum(len(g['predictions']) for g in grouped_comparisons)} total predictions"
            )
            return grouped_comparisons

    except sqlite3.Error as e:
        logger.error(
            f"Error retrieving grouped predictions with results comparison: {e}")
        return []


# Hybrid Configuration System - Simple & Robust

def migrate_config_from_file() -> bool:
    """Migrate configuration from config.ini to database."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM system_config")
            config_count = cursor.fetchone()[0]

            if config_count > 0:
                logger.info("Configuration already exists in database, skipping migration")
                return True

        config = configparser.ConfigParser()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, '..', 'config', 'config.ini')

        if not os.path.exists(config_path):
            logger.warning(f"Config file not found at {config_path}, using default values")
            return _create_default_config_in_db()

        config.read(config_path)

        with get_db_connection() as conn:
            cursor = conn.cursor()

            for section_name in config.sections():
                for key, value in config.items(section_name):
                    cursor.execute(
                        "INSERT OR REPLACE INTO system_config (section, key, value) VALUES (?, ?, ?)",
                        (section_name, key, value)
                    )

            cursor.execute(
                "INSERT OR REPLACE INTO system_config (section, key, value) VALUES ('system', 'config_migrated', 'true')"
            )

            # Add sample predictions for frontend testing
            sample_predictions = [
                ('2025-08-18T03:49:16.657479', 10, 15, 33, 36, 37, 7, 0.491, '1.0.0-sample', 'sample_hash_001', None, '2025-08-23'),
                ('2025-08-18T03:49:16.657479', 9, 19, 24, 27, 34, 5, 0.478, '1.0.0-sample', 'sample_hash_002', None, '2025-08-23'),
                ('2025-08-18T03:49:16.657479', 13, 17, 20, 29, 38, 5, 0.465, '1.0.0-sample', 'sample_hash_003', None, '2025-08-23'),
                ('2025-08-18T03:49:16.657479', 6, 11, 22, 31, 45, 12, 0.452, '1.0.0-sample', 'sample_hash_004', None, '2025-08-23'),
                ('2025-08-18T03:49:16.657479', 14, 25, 30, 42, 58, 8, 0.439, '1.0.0-sample', 'sample_hash_005', None, '2025-08-23')
            ]

            cursor.executemany("""
                INSERT OR IGNORE INTO predictions_log 
                (timestamp, n1, n2, n3, n4, n5, powerball, score_total, model_version, dataset_hash, json_details_path, target_draw_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, sample_predictions)

            conn.commit()

        logger.info("Configuration successfully migrated from config.ini to database")
        return True

    except (configparser.Error, sqlite3.Error, OSError) as e:
        logger.error(f"Error migrating configuration from file: {e}")
        return False


def _create_default_config_in_db() -> bool:
    """Create default configuration in database."""
    default_config = {
        'paths': {
            'db_file': 'data/shiolplus.db',
            'model_file': 'models/shiolplus.pkl'
        },
        'pipeline': {
            'execution_days_monday': 'True',
            'execution_days_wednesday': 'True',
            'execution_days_saturday': 'True',
            'execution_time': '02:00',
            'timezone': 'America/New_York',
            'auto_execution': 'True'
        },
        'predictions': {
            'count': '100',
            'method': 'deterministic'
        },
        'weights': {
            'probability': '50',
            'diversity': '20',
            'historical': '20',
            'risk': '10'
        }
    }

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            for section_name, section_data in default_config.items():
                for key, value in section_data.items():
                    cursor.execute(
                        "INSERT OR REPLACE INTO system_config (section, key, value) VALUES (?, ?, ?)",
                        (section_name, key, value)
                    )

            cursor.execute(
                "INSERT OR REPLACE INTO system_config (section, key, value) VALUES ('system', 'config_migrated', 'default')"
            )

            conn.commit()

        logger.info("Default configuration created in database")
        return True

    except sqlite3.Error as e:
        logger.error(f"Error creating default configuration: {e}")
        return False


def load_config_from_db() -> Dict[str, Any]:
    """Load configuration from database with file fallback."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT section, key, value FROM system_config")
            config_rows = cursor.fetchall()

            if not config_rows:
                logger.warning("No configuration found in database, using file fallback")
                return _load_config_from_file()

            config_dict = {}
            for section, key, value in config_rows:
                if section not in config_dict:
                    config_dict[section] = {}
                config_dict[section][key] = value

            logger.info("Configuration loaded successfully from database")
            return config_dict

    except sqlite3.Error as e:
        logger.error(f"Error loading configuration from database: {e}")
        logger.info("Falling back to config file")
        return _load_config_from_file()


def _load_config_from_file() -> Dict[str, Any]:
    """Fallback: load configuration from file."""
    try:
        config = configparser.ConfigParser()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, '..', 'config', 'config.ini')

        config.read(config_path)

        config_dict = {}
        for section in config.sections():
            config_dict[section] = dict(config.items(section))

        logger.info(f"Configuration loaded from {config_path}")
        return config_dict

    except (configparser.Error, OSError) as e:
        logger.error(f"Error loading configuration from file: {e}")
        return {}


def save_config_to_db(config_data: Dict[str, Any]) -> bool:
    """Save configuration to database."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            for section_name, section_data in config_data.items():
                if isinstance(section_data, dict):
                    for key, value in section_data.items():
                        cursor.execute(
                            """
                            INSERT OR REPLACE INTO system_config (section, key, value, updated_at)
                            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                        """, (section_name, key, str(value)))
                else:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO system_config (section, key, value, updated_at)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    """, ('general', section_name, str(section_data)))

            conn.commit()

        logger.info("Configuration saved successfully to database")
        return True

    except sqlite3.Error as e:
        logger.error(f"Error saving configuration to database: {e}")
        return False


def get_config_value(section: str, key: str, default: Any = None) -> Any:
    """Get a specific configuration value with automatic fallback."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value FROM system_config WHERE section = ? AND key = ?",
                (section, key)
            )

            result = cursor.fetchone()
            if result:
                return result[0]

        # Fallback to file if not in DB
        config = configparser.ConfigParser()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, '..', 'config', 'config.ini')

        if os.path.exists(config_path):
            config.read(config_path)
            if config.has_section(section) and config.has_option(section, key):
                return config.get(section, key)

        return default

    except (configparser.Error, sqlite3.Error) as e:
        logger.error(f"Error getting config value {section}.{key}: {e}")
        return default


def is_config_initialized() -> bool:
    """Check if hybrid configuration system is initialized."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value FROM system_config WHERE section = 'system' AND key = 'config_migrated'"
            )

            result = cursor.fetchone()
            return result is not None

    except sqlite3.Error as e:
        logger.error(f"Error checking config initialization: {e}")
        return False


# Phase 2: Date Validation Functions

def _validate_target_draw_date(date_str: str) -> bool:
    """Validate that target_draw_date has correct format."""
    from src.date_utils import DateManager
    return DateManager.validate_date_format(date_str)


def _is_valid_drawing_date(date_str: str) -> bool:
    """Verify that a date corresponds to a drawing day."""
    from src.date_utils import DateManager
    return DateManager.is_valid_drawing_date(date_str)


def _sanitize_prediction_data(prediction_data: Dict[str, Any], allow_simulated: bool = False) -> Optional[Dict[str, Any]]:
    """Sanitize and validate all prediction fields before saving."""
    from src.date_utils import DateManager

    sanitized_data = prediction_data.copy()

    # Validate and correct timestamp using DateManager
    if 'timestamp' not in sanitized_data or not sanitized_data['timestamp']:
        sanitized_data['timestamp'] = DateManager.get_current_et_time().isoformat()

    # Validate main numbers (must be between 1-69)
    if 'numbers' in sanitized_data:
        numbers = sanitized_data['numbers']
        if isinstance(numbers, list) and len(numbers) == 5:
            valid_numbers = []
            for num in numbers:
                try:
                    num_int = int(num)
                    if 1 <= num_int <= 69:
                        valid_numbers.append(num_int)
                    else:
                        logger.warning(f"Number {num} is outside valid range 1-69")
                        return None
                except (ValueError, TypeError):
                    logger.error(f"Invalid number format: {num}")
                    return None
            sanitized_data['numbers'] = valid_numbers
        else:
            logger.error(f"Invalid numbers format: {numbers}")
            return None

    # Validate Powerball (must be between 1-26)
    if 'powerball' in sanitized_data:
        try:
            pb = int(sanitized_data['powerball'])
            if not (1 <= pb <= 26):
                logger.error(f"Powerball {pb} is outside valid range 1-26")
                return None
            sanitized_data['powerball'] = pb
        except (ValueError, TypeError):
            logger.error(f"Invalid powerball format: {sanitized_data['powerball']}")
            return None

    # Validate score_total
    if 'score_total' in sanitized_data:
        try:
            score = float(sanitized_data['score_total'])
            if score < 0 or score > 1:
                logger.warning(f"Score {score} is outside typical range 0-1")
            sanitized_data['score_total'] = score
        except (ValueError, TypeError):
            logger.error(f"Invalid score format: {sanitized_data['score_total']}")
            return None

    # Validate model_version
    if 'model_version' not in sanitized_data or not sanitized_data['model_version']:
        sanitized_data['model_version'] = '1.0.0-pipeline'

    # Validate dataset_hash
    if 'dataset_hash' not in sanitized_data or not sanitized_data['dataset_hash']:
        import hashlib
        timestamp_str = str(sanitized_data.get('timestamp', datetime.now().isoformat()))
        default_hash = hashlib.md5(timestamp_str.encode()).hexdigest()[:16]
        sanitized_data['dataset_hash'] = default_hash

    return sanitized_data


# ===============================================
# USER AUTHENTICATION & PREMIUM ACCESS FUNCTIONS
# ===============================================

# Password hashing moved to api_auth_endpoints.py using bcrypt
# These functions are kept for backwards compatibility but deprecated

def hash_password(password: str) -> str:
    """
    Hash password using SHA-256 with salt.
    DEPRECATED: Use bcrypt from api_auth_endpoints.py instead.
    Kept for backwards compatibility only.
    """
    salt = "powerball_shiol_2024"  # Static salt for backward compatibility
    return hashlib.sha256((password + salt).encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """
    Verify password against SHA-256 hash.
    DEPRECATED: Use bcrypt verification from api_auth_endpoints.py instead.
    Kept for backwards compatibility with legacy users only.
    """
    return hash_password(password) == hashed


def create_user(email: str, username: str, password_or_hash: str) -> Optional[int]:
    """Create a new user account.
    Args:
        password_or_hash: Either a plain password (legacy) or a bcrypt hash (new)
    """
    try:
        # Detect if input is already a bcrypt hash
        if password_or_hash.startswith(("$2a$", "$2b$", "$2y$")):
            password_hash = password_or_hash  # Store bcrypt hash verbatim
        else:
            password_hash = hash_password(password_or_hash)  # Legacy SHA-256 hash
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO users (email, username, password_hash)
                VALUES (?, ?, ?)
            """, (email.lower().strip(), username.strip(), password_hash))
            
            user_id = cursor.lastrowid
            conn.commit()
            
            logger.info(f"New user created: {username} (ID: {user_id})")
            return user_id
            
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed" in str(e):
            logger.warning(f"Duplicate user: {email} / {username}")
            return None
        logger.error(f"Integrity error creating user: {e}")
        raise
    except sqlite3.Error as e:
        logger.error(f"Database error creating user: {e}")
        raise


def authenticate_user(login: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate user by email or username."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Try login as email first, then username
            cursor.execute("""
                SELECT id, email, username, password_hash, is_premium, premium_expires_at, is_active, created_at, login_count, is_admin
                FROM users 
                WHERE (email = ? OR username = ?) AND is_active = TRUE
            """, (login.lower().strip(), login.strip()))
            
            user_data = cursor.fetchone()
            
            if not user_data:
                return None
                
            user_id, email, username, stored_hash, is_premium, premium_expires_at, is_active, created_at, login_count, is_admin = user_data
            
            # Deterministic verification based on hash format
            password_valid = False
            
            if stored_hash.startswith(("$2a$", "$2b$", "$2y$")):
                # Bcrypt hash - use secure verification
                try:
                    from src.api_auth_endpoints import verify_password_secure
                    password_valid = verify_password_secure(password, stored_hash)
                    if password_valid:
                        logger.debug(f"User {login} authenticated with bcrypt hash")
                except Exception as e:
                    logger.error(f"Bcrypt verification failed for {login}: {e}")
            else:
                # Legacy SHA-256 hash - use legacy verification
                password_valid = verify_password(password, stored_hash)
                if password_valid:
                    logger.info(f"User {login} authenticated with legacy hash - consider migration")
            
            if not password_valid:
                logger.warning(f"Authentication failed: invalid password for {login}")
                return None
                
            # Update login statistics
            cursor.execute("""
                UPDATE users 
                SET last_login = CURRENT_TIMESTAMP, login_count = login_count + 1
                WHERE id = ?
            """, (user_id,))
            conn.commit()
            
            # Get updated login count
            updated_login_count = login_count + 1
            
            # Check if premium has expired
            current_premium_status = is_premium
            if is_premium and premium_expires_at:
                try:
                    expiry_date = datetime.fromisoformat(premium_expires_at.replace('Z', '+00:00'))
                    if datetime.now() > expiry_date:
                        current_premium_status = False
                        cursor.execute("""
                            UPDATE users SET is_premium = FALSE WHERE id = ?
                        """, (user_id,))
                        conn.commit()
                except ValueError:
                    pass
            
            logger.info(f"User authenticated: {username} (Premium: {current_premium_status}, Admin: {bool(is_admin)})")
            
            return {
                'id': user_id,
                'email': email,
                'username': username,
                'is_premium': current_premium_status,
                'premium_expires_at': premium_expires_at,
                'created_at': created_at,
                'login_count': updated_login_count,
                'is_admin': bool(is_admin) if is_admin is not None else False
            }
            
    except sqlite3.Error as e:
        logger.error(f"Database error during authentication: {e}")
        return None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user information by ID."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, email, username, is_premium, premium_expires_at, created_at, last_login, login_count, is_admin
                FROM users 
                WHERE id = ? AND is_active = TRUE
            """, (user_id,))
            
            user_data = cursor.fetchone()
            
            if not user_data:
                return None
                
            user_id, email, username, is_premium, premium_expires_at, created_at, last_login, login_count, is_admin = user_data
            
            return {
                'id': user_id,
                'email': email,
                'username': username,
                'is_premium': is_premium,
                'premium_expires_at': premium_expires_at,
                'created_at': created_at,
                'last_login': last_login,
                'login_count': login_count,
                'is_admin': bool(is_admin) if is_admin is not None else False
            }
            
    except sqlite3.Error as e:
        logger.error(f"Database error getting user: {e}")
        return None


def upgrade_user_to_premium(user_id: int, expiry_date: datetime) -> bool:
    """Upgrade user to premium access."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE users 
                SET is_premium = TRUE, premium_expires_at = ?
                WHERE id = ? AND is_active = TRUE
            """, (expiry_date.isoformat(), user_id))
            
            if cursor.rowcount > 0:
                conn.commit()
                logger.info(f"User {user_id} upgraded to premium until {expiry_date}")
                return True
            else:
                logger.warning(f"User {user_id} not found for premium upgrade")
                return False
                
    except sqlite3.Error as e:
        logger.error(f"Database error upgrading user to premium: {e}")
        return False


def get_user_stats() -> Dict[str, int]:
    """Get platform statistics for user counts."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Total users
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = TRUE")
            total_users = cursor.fetchone()[0]
            
            # Premium users
            cursor.execute("""
                SELECT COUNT(*) FROM users 
                WHERE is_premium = TRUE AND is_active = TRUE
                AND (premium_expires_at IS NULL OR premium_expires_at > CURRENT_TIMESTAMP)
            """)
            premium_users = cursor.fetchone()[0]
            
            # Users created in last 30 days
            cursor.execute("""
                SELECT COUNT(*) FROM users 
                WHERE is_active = TRUE 
                AND created_at > datetime('now', '-30 days')
            """)
            new_users = cursor.fetchone()[0]
            
            return {
                'total_users': total_users,
                'premium_users': premium_users,
                'new_users_30d': new_users,
                'free_users': total_users - premium_users
            }
            
    except sqlite3.Error as e:
        logger.error(f"Database error getting user stats: {e}")
        return {
            'total_users': 0,
            'premium_users': 0,
            'new_users_30d': 0,
            'free_users': 0
        }