"""
SHIOL+ PostgreSQL Database Module
=================================

Complete PostgreSQL database implementation.
Handles all database operations through PostgreSQL with connection pooling.
"""

import os
import json
import pandas as pd
from loguru import logger
import configparser
import numpy as np
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
import asyncio
import traceback

# Import PostgreSQL database instance
from src.database_postgresql import postgresql_db


# Custom JSON encoder to handle numpy types
class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle numpy types."""

    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif hasattr(obj, 'item'):  # Handle numpy scalar types
            try:
                return obj.item()
            except (AttributeError, ValueError):
                return str(obj)
        return super(NumpyEncoder, self).default(obj)


# ========================================================================
# DATABASE CONNECTION & INITIALIZATION - POSTGRESQL ONLY
# ========================================================================


def get_database_url() -> str:
    """Get PostgreSQL database URL from environment or config"""
    return postgresql_db.get_database_url()


def get_db_connection():
    """Get synchronous PostgreSQL database connection"""
    try:
        return postgresql_db.get_sync_connection()
    except Exception as e:
        logger.error(f"Failed to get PostgreSQL connection: {e}")
        raise


def is_database_connected() -> bool:
    """Check if PostgreSQL database is connected and available"""
    try:
        import concurrent.futures

        def test_sync_connection():
            """Test connection using sync psycopg2"""
            try:
                import psycopg2
                database_url = postgresql_db.get_database_url()

                with psycopg2.connect(database_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                        result = cur.fetchone()
                        return result and result[0] == 1
            except Exception as sync_error:
                logger.debug(f"Sync connection test failed: {sync_error}")
                return False

        def run_isolated_test():
            """Run test in completely isolated thread"""
            try:
                return test_sync_connection()
            except Exception as e:
                logger.debug(f"Isolated test failed: {e}")
                return False

        # Use thread executor to avoid any event loop conflicts
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_isolated_test)
            return future.result(timeout=8)  # 8 second timeout

    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


def get_async_db_connection():
    """Get asynchronous PostgreSQL database connection context manager"""
    try:
        return postgresql_db.get_async_connection()
    except Exception as e:
        logger.error(f"Failed to get async PostgreSQL connection: {e}")
        raise


def calculate_next_drawing_date() -> str:
    """Calculate the next Powerball drawing date using centralized DateManager."""
    from src.date_utils import DateManager

    # Use native DateManager time without corrections
    current_et = DateManager.get_current_et_time()
    next_date = DateManager.calculate_next_drawing_date(
        reference_date=current_et)

    logger.debug(
        f"Next drawing date calculated: {next_date} (from ET time: {current_et.strftime('%Y-%m-%d %H:%M')})"
    )
    return next_date


# ========================================================================
# DATABASE INITIALIZATION - POSTGRESQL ONLY
# ========================================================================


async def _initialize_database_async() -> bool:
    """
    Asynchronously initialize PostgreSQL database with proper connection handling.

    Returns:
        bool: True if initialization successful, False otherwise
    """
    try:
        logger.info("Initializing PostgreSQL database asynchronously...")

        # Initialize connection pool with proper error handling
        max_init_retries = 2
        for init_attempt in range(max_init_retries):
            try:
                await postgresql_db.initialize_async_pool()
                logger.info("✓ Database connection pool initialized")
                break
            except Exception as pool_error:
                logger.error(
                    f"Pool initialization attempt {init_attempt + 1} failed: {pool_error}"
                )
                if init_attempt < max_init_retries - 1:
                    await asyncio.sleep(2)
                    continue
                else:
                    logger.error(
                        "Failed to initialize connection pool after all attempts"
                    )
                    return False

        # Test database connectivity with retry mechanism
        logger.info("Testing database connectivity...")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with postgresql_db.get_async_connection() as conn:
                    result = await conn.fetchval("SELECT 1")
                    if result != 1:
                        raise Exception("Database connectivity test failed")
                logger.info("✓ Database connectivity test passed")
                break
            except Exception as conn_error:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Connection attempt {attempt + 1} failed: {conn_error}. Retrying..."
                    )
                    await asyncio.sleep(2)
                    continue
                else:
                    logger.error(
                        f"Database connectivity test failed after {max_retries} attempts: {conn_error}"
                    )
                    return False

        # Create tables if they don't exist with separate connection
        logger.info("Creating database tables if they don't exist...")
        create_tables_sql = """
        CREATE TABLE IF NOT EXISTS powerball_draws (
            id SERIAL PRIMARY KEY,
            draw_date DATE NOT NULL,
            n1 INTEGER NOT NULL CHECK (n1 >= 1 AND n1 <= 69),
            n2 INTEGER NOT NULL CHECK (n2 >= 1 AND n2 <= 69),
            n3 INTEGER NOT NULL CHECK (n3 >= 1 AND n3 <= 69),
            n4 INTEGER NOT NULL CHECK (n4 >= 1 AND n4 <= 69),
            n5 INTEGER NOT NULL CHECK (n5 >= 1 AND n5 <= 69),
            pb INTEGER NOT NULL CHECK (pb >= 1 AND pb <= 26),
            multiplier INTEGER DEFAULT 1,
            estimated_jackpot BIGINT,
            actual_jackpot BIGINT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(draw_date)
        );

        CREATE INDEX IF NOT EXISTS idx_powerball_draws_date ON powerball_draws(draw_date);
        CREATE INDEX IF NOT EXISTS idx_powerball_draws_numbers ON powerball_draws(n1, n2, n3, n4, n5, pb);

        CREATE TABLE IF NOT EXISTS prediction_logs (
            id SERIAL PRIMARY KEY,
            prediction_id VARCHAR(100) UNIQUE,
            numbers INTEGER[] NOT NULL,
            powerball INTEGER NOT NULL,
            score_total DECIMAL(10, 6) DEFAULT 0.0,
            score_details JSONB,
            method VARCHAR(100) DEFAULT 'unknown',
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            target_draw_date DATE,
            model_version VARCHAR(50),
            dataset_hash VARCHAR(64),
            play_rank INTEGER DEFAULT 1,
            execution_source VARCHAR(100) DEFAULT 'manual',
            authorized BOOLEAN DEFAULT true
        );

        CREATE INDEX IF NOT EXISTS idx_prediction_logs_date ON prediction_logs(generated_at);
        CREATE INDEX IF NOT EXISTS idx_prediction_logs_target ON prediction_logs(target_draw_date);
        CREATE INDEX IF NOT EXISTS idx_prediction_logs_method ON prediction_logs(method);

        CREATE TABLE IF NOT EXISTS pipeline_executions (
            id SERIAL PRIMARY KEY,
            execution_id VARCHAR(100) UNIQUE NOT NULL,
            status VARCHAR(50) DEFAULT 'pending',
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_time TIMESTAMP,
            steps_completed INTEGER DEFAULT 0,
            total_steps INTEGER DEFAULT 6,
            current_step VARCHAR(100),
            error_message TEXT,
            execution_data JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_pipeline_executions_status ON pipeline_executions(status);
        CREATE INDEX IF NOT EXISTS idx_pipeline_executions_start ON pipeline_executions(start_time);
        """

        try:
            async with postgresql_db.get_async_connection() as conn:
                await conn.execute(create_tables_sql)
            logger.info("✓ Database tables created/verified successfully")
        except Exception as table_error:
            logger.error(f"Failed to create/verify tables: {table_error}")
            return False

        logger.info(
            "✓ PostgreSQL database initialization completed successfully")
        return True

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False


async def initialize_configuration_system():
    """Initialize hybrid configuration system in PostgreSQL"""
    try:
        async with postgresql_db.get_async_connection() as conn:
            # Check if configuration exists
            config_count = await conn.fetchval(
                "SELECT COUNT(*) FROM system_config")

            if config_count == 0:
                logger.info("Initializing configuration system...")
                await migrate_config_from_file()

        logger.info("Configuration system initialized")

    except Exception as e:
        logger.error(f"Error initializing configuration system: {e}")


async def add_sample_data_if_empty():
    """Add sample Powerball draw data if database is empty"""
    try:
        async with postgresql_db.get_async_connection() as conn:
            # Check if we have any historical data
            count = await conn.fetchval("SELECT COUNT(*) FROM powerball_draws")

            if count == 0:
                logger.info("No historical data found. Adding sample data...")

                sample_data = [('2024-01-01', 7, 14, 21, 35, 42, 18),
                               ('2024-01-03', 3, 16, 27, 44, 58, 9),
                               ('2024-01-06', 12, 23, 34, 45, 56, 15),
                               ('2024-01-08', 5, 19, 28, 37, 49, 22),
                               ('2024-01-10', 11, 25, 33, 41, 52, 8),
                               ('2024-01-13', 8, 17, 26, 39, 54, 13),
                               ('2024-01-15', 14, 22, 31, 46, 57, 11),
                               ('2024-01-17', 6, 18, 29, 43, 51, 19),
                               ('2024-01-20', 9, 20, 32, 47, 59, 7),
                               ('2024-01-22', 15, 24, 30, 40, 55, 16),
                               ('2024-01-24', 4, 13, 25, 38, 48, 21),
                               ('2024-01-27', 10, 21, 34, 44, 53, 12),
                               ('2024-01-29', 2, 15, 28, 41, 56, 6),
                               ('2024-01-31', 16, 23, 35, 45, 58, 14),
                               ('2024-02-03', 7, 18, 27, 42, 50, 10),
                               ('2024-02-05', 12, 19, 31, 46, 54, 17),
                               ('2024-02-07', 5, 22, 29, 39, 57, 8),
                               ('2024-02-10', 9, 16, 33, 43, 51, 20),
                               ('2024-02-12', 11, 24, 36, 47, 59, 4),
                               ('2024-02-14', 3, 14, 26, 40, 52, 15),
                               ('2024-02-17', 8, 17, 30, 44, 55, 9),
                               ('2024-02-19', 13, 21, 32, 48, 56, 7),
                               ('2024-02-21', 6, 19, 28, 41, 53, 18),
                               ('2024-02-24', 10, 23, 34, 45, 58, 11),
                               ('2024-02-26', 4, 15, 27, 38, 49, 13),
                               ('2024-02-28', 14, 20, 31, 42, 54, 16),
                               ('2024-03-02', 7, 18, 29, 46, 57, 5),
                               ('2024-03-04', 12, 22, 35, 43, 51, 19),
                               ('2024-03-06', 9, 16, 26, 39, 55, 8),
                               ('2024-03-09', 5, 24, 33, 47, 59, 12),
                               ('2025-08-04', 1, 12, 20, 33, 66, 21),
                               ('2025-08-05', 5, 15, 27, 41, 53, 18),
                               ('2025-08-06', 10, 18, 27, 41, 54, 14),
                               ('2025-08-07', 8, 22, 35, 44, 58, 9)]

                for draw_date, n1, n2, n3, n4, n5, pb in sample_data:
                    await conn.execute(
                        """
                        INSERT INTO powerball_draws (draw_date, n1, n2, n3, n4, n5, pb)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (draw_date) DO NOTHING
                    """, draw_date, n1, n2, n3, n4, n5, pb)

                logger.info(f"Added {len(sample_data)} sample draw records")

    except Exception as e:
        logger.error(f"Error adding sample data: {e}")


# ========================================================================
# POWERBALL DRAWS FUNCTIONS - POSTGRESQL ONLY
# ========================================================================


async def get_latest_draw_date() -> Optional[str]:
    """Get the most recent draw date from PostgreSQL"""
    try:
        async with postgresql_db.get_async_connection() as conn:
            result = await conn.fetchval(
                "SELECT MAX(draw_date) FROM powerball_draws")
            if result:
                logger.info(f"Latest draw date in PostgreSQL: {result}")
                return str(result)
            else:
                logger.info("No draw data found in PostgreSQL")
                return None

    except Exception as e:
        logger.error(f"Failed to get latest draw date from PostgreSQL: {e}")
        return None


async def bulk_insert_draws(df: pd.DataFrame):
    """Insert draw data into PostgreSQL"""
    if df.empty:
        logger.info("No new draws to insert")
        return

    try:
        async with postgresql_db.get_async_connection() as conn:
            async with conn.transaction():
                for _, row in df.iterrows():
                    await conn.execute(
                        """
                        INSERT INTO powerball_draws (draw_date, n1, n2, n3, n4, n5, pb)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (draw_date) DO UPDATE SET
                        n1=$2, n2=$3, n3=$4, n4=$5, n5=$6, pb=$7, updated_at=NOW()
                    """, row['draw_date'], int(row['n1']), int(row['n2']),
                        int(row['n3']), int(row['n4']), int(row['n5']),
                        int(row['pb']))

                logger.info(
                    f"Successfully inserted {len(df)} rows into PostgreSQL")

    except Exception as e:
        logger.error(f"Error during bulk insert to PostgreSQL: {e}")


async def get_all_draws() -> pd.DataFrame:
    """Get all historical draw data from PostgreSQL"""
    try:
        async with postgresql_db.get_async_connection() as conn:
            # First check if the table exists and what columns it has
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'powerball_draws'
                );
            """)

            if not table_exists:
                logger.warning(
                    "powerball_draws table does not exist - initializing database..."
                )
                # Try to initialize the database
                await _initialize_database_async()
                # Check again after initialization
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'powerball_draws'
                    );
                """)
                if not table_exists:
                    logger.error(
                        "powerball_draws table still does not exist after initialization"
                    )
                    return pd.DataFrame()

            # Get column information
            columns = await conn.fetch("""
                SELECT column_name, data_type
                FROM information_schema.columns 
                WHERE table_name = 'powerball_draws' 
                AND table_schema = 'public'
                ORDER BY ordinal_position;
            """)

            available_columns = [col['column_name'] for col in columns]
            logger.debug(
                f"Available columns in powerball_draws: {available_columns}")

            # Check for draw_date column or alternatives
            date_column = 'draw_date'
            if 'draw_date' not in available_columns:
                # Look for alternative date columns
                date_alternatives = [
                    'date', 'drawing_date', 'lottery_date', 'created_at'
                ]
                for alt in date_alternatives:
                    if alt in available_columns:
                        date_column = alt
                        logger.info(
                            f"Using {alt} as date column instead of draw_date")
                        break
                else:
                    logger.error(
                        f"No suitable date column found. Available columns: {available_columns}"
                    )
                    logger.error("Column details:")
                    for col in columns:
                        logger.error(
                            f"  - {col['column_name']}: {col['data_type']}")
                    return pd.DataFrame()

            # Build the query with available columns
            required_cols = ['n1', 'n2', 'n3', 'n4', 'n5', 'pb']
            missing_cols = [
                col for col in required_cols if col not in available_columns
            ]

            if missing_cols:
                logger.error(f"Missing required columns: {missing_cols}")
                logger.error(f"Available columns: {available_columns}")
                return pd.DataFrame()

            # Check if table has any data
            row_count = await conn.fetchval(
                "SELECT COUNT(*) FROM powerball_draws")
            if row_count == 0:
                logger.warning(
                    "powerball_draws table exists but contains no data")
                return pd.DataFrame()

            logger.debug(f"Found {row_count} rows in powerball_draws table")

            # Use explicit column names to avoid ambiguity
            query = f"""
                SELECT {date_column} as draw_date, n1, n2, n3, n4, n5, pb 
                FROM powerball_draws 
                ORDER BY {date_column} ASC
            """

            # Double-check that the query is properly formatted
            logger.debug(f"Using date column: {date_column}")
            logger.debug(f"Final query: {query}")

            logger.debug(f"Executing query: {query}")
            results = await conn.fetch(query)

            if results:
                # Convert asyncpg Records to list of dictionaries to ensure proper column names
                data_rows = []
                for record in results:
                    row_dict = dict(record)
                    data_rows.append(row_dict)

                df = pd.DataFrame(data_rows)

                # Verify that draw_date column exists after the query
                if 'draw_date' not in df.columns:
                    logger.error(
                        f"draw_date column not found in query results. Available columns: {list(df.columns)}"
                    )
                    # Try to debug what we actually got
                    if len(data_rows) > 0:
                        logger.error(f"Sample row data: {data_rows[0]}")
                    return pd.DataFrame()

                # Convert to proper datetime format
                df['draw_date'] = pd.to_datetime(df['draw_date'])
                logger.info(
                    f"Successfully loaded {len(df)} rows from PostgreSQL")
                logger.debug(
                    f"Date range: {df['draw_date'].min()} to {df['draw_date'].max()}"
                )
                return df
            else:
                logger.info(
                    "No draw data found in PostgreSQL - table exists but is empty"
                )
                return pd.DataFrame()

    except Exception as e:
        logger.error(f"Could not retrieve data from PostgreSQL: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return pd.DataFrame()


# ========================================================================
# PREDICTIONS LOG FUNCTIONS - POSTGRESQL ONLY
# ========================================================================


def save_prediction_log(prediction_data: Dict[str, Any],
                        allow_simulated: bool = False,
                        execution_source: str = None) -> Optional[int]:
    """Save prediction to PostgreSQL predictions_log table"""
    try:
        logger.debug(f"Saving prediction data: {prediction_data}")

        # Validate execution source
        authorized_sources = [
            "manual_dashboard", "automatic_scheduler", "pipeline_execution"
        ]
        if execution_source and execution_source not in authorized_sources:
            logger.error(f"Unauthorized prediction source: {execution_source}")
            return None

        # Sanitize prediction data
        sanitized_data = _sanitize_prediction_data(prediction_data,
                                                   allow_simulated)
        if sanitized_data is None:
            logger.error("Prediction data is invalid after sanitization")
            return None

        # Calculate target draw date if not provided
        target_draw_date_str = sanitized_data.get('target_draw_date')
        if not target_draw_date_str:
            target_draw_date_str = calculate_next_drawing_date()
            logger.debug(
                f"Target draw date calculated: {target_draw_date_str}")

        # Validate target draw date
        if not _validate_target_draw_date(target_draw_date_str):
            logger.error(
                f"Invalid target_draw_date format: {target_draw_date_str}")
            raise ValueError(
                f"Invalid target_draw_date format: {target_draw_date_str}")

        # Get created_at timestamp
        created_at_val = sanitized_data.get('created_at')
        if not created_at_val:
            from src.date_utils import DateManager
            created_at_val = DateManager.get_current_et_time().isoformat()

        # Safe type conversion
        def safe_int(value):
            if hasattr(value, 'item'):
                return int(value.item())
            return int(value)

        def safe_float(value):
            if hasattr(value, 'item'):
                return float(value.item())
            return float(value)

        async def _save_to_db():
            async with postgresql_db.get_async_connection() as conn:
                prediction_id = await conn.fetchval(
                    """
                    INSERT INTO predictions_log
                    (timestamp, n1, n2, n3, n4, n5, powerball, score_total,
                     model_version, dataset_hash, json_details_path, target_draw_date)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    RETURNING id
                """, sanitized_data['timestamp'],
                    safe_int(sanitized_data['numbers'][0]),
                    safe_int(sanitized_data['numbers'][1]),
                    safe_int(sanitized_data['numbers'][2]),
                    safe_int(sanitized_data['numbers'][3]),
                    safe_int(sanitized_data['numbers'][4]),
                    safe_int(sanitized_data['powerball']),
                    safe_float(sanitized_data['score_total']),
                    str(sanitized_data['model_version']),
                    str(sanitized_data['dataset_hash']),
                    sanitized_data.get('json_details_path'),
                    target_draw_date_str)
                return prediction_id

        # Execute the async save operation
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _save_to_db())
                    prediction_id = future.result()
            else:
                prediction_id = asyncio.run(_save_to_db())

            if prediction_id:
                logger.info(
                    f"Prediction saved to PostgreSQL with ID {prediction_id}")
                return prediction_id
            else:
                logger.error("Failed to retrieve prediction ID after saving.")
                return None
        except Exception as e:
            logger.error(f"Error executing async save operation: {e}")
            return None

    except Exception as e:
        logger.error(f"Error saving prediction to PostgreSQL: {e}")
        return None


async def get_prediction_history(limit: int = 50) -> pd.DataFrame:
    """Get prediction history from PostgreSQL"""
    try:
        async with postgresql_db.get_async_connection() as conn:
            results = await conn.fetch(
                """
                SELECT id, timestamp, n1, n2, n3, n4, n5, powerball,
                       score_total, model_version, dataset_hash,
                       json_details_path, created_at, target_draw_date
                FROM predictions_log
                ORDER BY created_at DESC
                LIMIT $1
            """, limit)

            if results:
                df = pd.DataFrame(results)
                logger.info(
                    f"Retrieved {len(df)} prediction records from PostgreSQL")
                return df
            else:
                logger.info("No prediction history found in PostgreSQL")
                return pd.DataFrame()

    except Exception as e:
        logger.error(
            f"Error retrieving prediction history from PostgreSQL: {e}")
        return pd.DataFrame()


# ========================================================================
# PIPELINE EXECUTION FUNCTIONS - POSTGRESQL ONLY
# ========================================================================


async def save_pipeline_execution(
        execution_data: Dict[str, Any]) -> Optional[str]:
    """Save pipeline execution to PostgreSQL"""
    try:
        execution_id = execution_data.get('execution_id')

        async with postgresql_db.get_async_connection() as conn:
            await conn.execute(
                """
                INSERT INTO pipeline_executions (
                    execution_id, status, start_time, trigger_type, trigger_source,
                    current_step, steps_completed, total_steps, num_predictions,
                    execution_details
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (execution_id) DO UPDATE SET
                status=EXCLUDED.status, current_step=EXCLUDED.current_step,
                steps_completed=EXCLUDED.steps_completed, updated_at=NOW()
            """, execution_id, execution_data.get('status', 'starting'),
                execution_data.get('start_time'),
                execution_data.get('trigger_type', 'unknown'),
                execution_data.get('execution_source', 'unknown'),
                execution_data.get('current_step'),
                execution_data.get('steps_completed', 0),
                execution_data.get('total_steps', 7),
                execution_data.get('num_predictions', 100),
                json.dumps(execution_data.get('trigger_details', {}),
                           cls=NumpyEncoder))

            logger.info(
                f"Pipeline execution {execution_id} saved to PostgreSQL")
            return execution_id

    except Exception as e:
        logger.error(f"Error saving pipeline execution to PostgreSQL: {e}")
        return None


async def update_pipeline_execution(execution_id: str,
                                    update_data: Dict[str, Any]) -> bool:
    """Update pipeline execution in PostgreSQL"""
    try:
        async with postgresql_db.get_async_connection() as conn:
            # Build dynamic update query
            update_fields = []
            params = []
            param_num = 1

            if 'status' in update_data:
                update_fields.append(f"status = ${param_num}")
                params.append(update_data['status'])
                param_num += 1

            if 'end_time' in update_data:
                update_fields.append(f"end_time = ${param_num}")
                params.append(update_data['end_time'])
                param_num += 1

            if 'current_step' in update_data:
                update_fields.append(f"current_step = ${param_num}")
                params.append(update_data['current_step'])
                param_num += 1

            if 'steps_completed' in update_data:
                update_fields.append(f"steps_completed = ${param_num}")
                params.append(update_data['steps_completed'])
                param_num += 1

            if 'error_message' in update_data:
                update_fields.append(f"error_message = ${param_num}")
                params.append(update_data['error_message'])
                param_num += 1

            if 'subprocess_success' in update_data:
                update_fields.append(f"subprocess_success = ${param_num}")
                params.append(update_data['subprocess_success'])
                param_num += 1

            if 'stdout_output' in update_data:
                update_fields.append(f"stdout_output = ${param_num}")
                params.append(update_data['stdout_output'])
                param_num += 1

            if 'stderr_output' in update_data:
                update_fields.append(f"stderr_output = ${param_num}")
                params.append(update_data['stderr_output'])
                param_num += 1

            if not update_fields:
                logger.warning(
                    f"No valid fields to update for execution {execution_id}")
                return False

            # Add updated_at and execution_id
            update_fields.append("updated_at = NOW()")
            params.append(execution_id)

            query = f"""
                UPDATE pipeline_executions
                SET {', '.join(update_fields)}
                WHERE execution_id = ${param_num}
            """

            result = await conn.execute(query, *params)

            if result == 'UPDATE 1':
                logger.info(
                    f"Pipeline execution {execution_id} updated in PostgreSQL")
                return True
            else:
                logger.warning(
                    f"Pipeline execution {execution_id} not found for update")
                return False

    except Exception as e:
        logger.error(f"Error updating pipeline execution in PostgreSQL: {e}")
        return False


async def get_pipeline_execution_history(
        limit: int = 20) -> List[Dict[str, Any]]:
    """Get pipeline execution history from PostgreSQL"""
    try:
        async with postgresql_db.get_async_connection() as conn:
            results = await conn.fetch(
                """
                SELECT
                    execution_id, status, start_time, end_time,
                    trigger_type, trigger_source, current_step,
                    steps_completed, total_steps, num_predictions,
                    error_message, subprocess_success, created_at
                FROM pipeline_executions
                ORDER BY start_time DESC
                LIMIT $1
            """, limit)

            executions = []
            for row in results:
                execution = {
                    'execution_id':
                    row['execution_id'],
                    'status':
                    row['status'],
                    'start_time':
                    row['start_time'].isoformat()
                    if row['start_time'] else None,
                    'end_time':
                    row['end_time'].isoformat() if row['end_time'] else None,
                    'trigger_type':
                    row['trigger_type'],
                    'trigger_source':
                    row['trigger_source'],
                    'current_step':
                    row['current_step'],
                    'steps_completed':
                    row['steps_completed'],
                    'total_steps':
                    row['total_steps'],
                    'num_predictions':
                    row['num_predictions'],
                    'error':
                    row['error_message'],
                    'subprocess_success':
                    row['subprocess_success'] or False,
                    'created_at':
                    row['created_at'].isoformat()
                    if row['created_at'] else None
                }
                executions.append(execution)

            logger.info(
                f"Retrieved {len(executions)} pipeline executions from PostgreSQL"
            )
            return executions

    except Exception as e:
        logger.error(
            f"Error getting pipeline execution history from PostgreSQL: {e}")
        return []


async def get_pipeline_execution_by_id(
        execution_id: str) -> Optional[Dict[str, Any]]:
    """Get specific pipeline execution by ID from PostgreSQL"""
    try:
        async with postgresql_db.get_async_connection() as conn:
            result = await conn.fetchrow(
                """
                SELECT
                    execution_id, status, start_time, end_time,
                    trigger_type, trigger_source, current_step,
                    steps_completed, total_steps, num_predictions,
                    error_message, subprocess_success, created_at, updated_at
                FROM pipeline_executions
                WHERE execution_id = $1
            """, execution_id)

            if result:
                execution = {
                    'execution_id':
                    result['execution_id'],
                    'status':
                    result['status'],
                    'start_time':
                    result['start_time'].isoformat()
                    if result['start_time'] else None,
                    'end_time':
                    result['end_time'].isoformat()
                    if result['end_time'] else None,
                    'trigger_type':
                    result['trigger_type'],
                    'trigger_source':
                    result['trigger_source'],
                    'current_step':
                    result['current_step'],
                    'steps_completed':
                    result['steps_completed'],
                    'total_steps':
                    result['total_steps'],
                    'num_predictions':
                    result['num_predictions'],
                    'error':
                    result['error_message'],
                    'subprocess_success':
                    result['subprocess_success'] or False,
                    'created_at':
                    result['created_at'].isoformat()
                    if result['created_at'] else None,
                    'updated_at':
                    result['updated_at'].isoformat()
                    if result['updated_at'] else None
                }
                logger.info(
                    f"Retrieved pipeline execution {execution_id} from PostgreSQL"
                )
                return execution
            else:
                logger.warning(
                    f"Pipeline execution {execution_id} not found in PostgreSQL"
                )
                return None

    except Exception as e:
        logger.error(
            f"Error getting pipeline execution {execution_id} from PostgreSQL: {e}"
        )
        return None


# ========================================================================
# CONFIGURATION MANAGEMENT - POSTGRESQL ONLY
# ========================================================================


async def migrate_config_from_file() -> bool:
    """Migrate configuration from config.ini to PostgreSQL"""
    try:
        async with postgresql_db.get_async_connection() as conn:
            # Check if configuration already exists
            config_count = await conn.fetchval(
                "SELECT COUNT(*) FROM system_config")
            if config_count > 0:
                logger.info("Configuration already exists in PostgreSQL")
                return True

            # Read configuration from file
            config = configparser.ConfigParser()
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, '..', 'config',
                                       'config.ini')

            if not os.path.exists(config_path):
                logger.warning(f"Config file not found, using defaults")
                return await _create_default_config_in_db()

            config.read(config_path)

            # Migrate each section to PostgreSQL
            async with conn.transaction():
                for section_name in config.sections():
                    for key, value in config.items(section_name):
                        await conn.execute(
                            """
                            INSERT INTO system_config (section, key, value)
                            VALUES ($1, $2, $3)
                            ON CONFLICT (section, key) DO UPDATE SET value=$3, updated_at=NOW()
                        """, section_name, key, value)

                # Mark migration as completed
                await conn.execute(
                    """
                    INSERT INTO system_config (section, key, value)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (section, key) DO UPDATE SET value=$3, updated_at=NOW()
                """, 'system', 'config_migrated', 'true')

        logger.info("Configuration migrated to PostgreSQL successfully")
        return True

    except Exception as e:
        logger.error(f"Error migrating configuration: {e}")
        return False


async def _create_default_config_in_db() -> bool:
    """Create default configuration in PostgreSQL"""
    try:
        default_config = {
            'paths': {
                'db_file': 'postgresql://database',
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
                'count': '50',
                'method': 'deterministic'
            },
            'weights': {
                'probability': '50',
                'diversity': '20',
                'historical': '20',
                'risk': '10'
            }
        }

        async with postgresql_db.get_async_connection() as conn:
            async with conn.transaction():
                for section_name, section_data in default_config.items():
                    for key, value in section_data.items():
                        await conn.execute(
                            """
                            INSERT INTO system_config (section, key, value)
                            VALUES ($1, $2, $3)
                            ON CONFLICT (section, key) DO UPDATE SET value=$3, updated_at=NOW()
                        """, section_name, key, value)

                # Mark as default configuration
                await conn.execute(
                    """
                    INSERT INTO system_config (section, key, value)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (section, key) DO UPDATE SET value=$3, updated_at=NOW()
                """, 'system', 'config_migrated', 'default')

        logger.info("Default configuration created in PostgreSQL")
        return True

    except Exception as e:
        logger.error(f"Error creating default configuration: {e}")
        return False


async def get_config_value(section: str, key: str, default: Any = None) -> Any:
    """Get configuration value from PostgreSQL"""
    try:
        async with postgresql_db.get_async_connection() as conn:
            result = await conn.fetchval(
                """
                SELECT value FROM system_config
                WHERE section = $1 AND key = $2
            """, section, key)

            if result is not None:
                return result

            return default

    except Exception as e:
        logger.error(f"Error getting config value {section}.{key}: {e}")
        return default


# ========================================================================
# UTILITY FUNCTIONS
# ========================================================================


def _sanitize_prediction_data(prediction_data: Dict[str, Any],
                              allow_simulated: bool = False) -> Dict[str, Any]:
    """Sanitize and validate prediction data"""
    from src.date_utils import DateManager

    sanitized_data = prediction_data.copy()

    # Validate and correct timestamp
    if 'timestamp' not in sanitized_data or not sanitized_data['timestamp']:
        sanitized_data['timestamp'] = DateManager.get_current_et_time(
        ).isoformat()

    # Validate numbers (1-69)
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
                        logger.warning(
                            f"Number {num} is outside valid range 1-69")
                        return None
                except (ValueError, TypeError):
                    logger.error(f"Invalid number format: {num}")
                    return None
            sanitized_data['numbers'] = valid_numbers
        else:
            logger.error(f"Invalid numbers format: {numbers}")
            return None

    # Validate Powerball (1-26)
    if 'powerball' in sanitized_data:
        try:
            pb = int(sanitized_data['powerball'])
            if not (1 <= pb <= 26):
                logger.error(f"Powerball {pb} is outside valid range 1-26")
                return None
            sanitized_data['powerball'] = pb
        except (ValueError, TypeError):
            logger.error(
                f"Invalid powerball format: {sanitized_data['powerball']}")
            return None

    # Validate score
    if 'score_total' in sanitized_data:
        try:
            score = float(sanitized_data['score_total'])
            if score < 0 or score > 1:
                logger.warning(f"Score {score} is outside typical range 0-1")
            sanitized_data['score_total'] = score
        except (ValueError, TypeError):
            logger.error(
                f"Invalid score format: {sanitized_data['score_total']}")
            return None

    # Set defaults
    if 'model_version' not in sanitized_data or not sanitized_data[
            'model_version']:
        sanitized_data['model_version'] = '1.0.0-pipeline'

    if 'dataset_hash' not in sanitized_data or not sanitized_data[
            'dataset_hash']:
        import hashlib
        timestamp_str = str(
            sanitized_data.get('timestamp',
                               datetime.now().isoformat()))
        sanitized_data['dataset_hash'] = hashlib.md5(
            timestamp_str.encode()).hexdigest()[:16]

    return sanitized_data


def _validate_target_draw_date(date_str: str) -> bool:
    """Validate target draw date format"""
    from src.date_utils import DateManager
    return DateManager.validate_date_format(date_str)


# ========================================================================
# SYNCHRONOUS WRAPPER FUNCTIONS FOR COMPATIBILITY
# ========================================================================


def initialize_database_sync():
    """Synchronous wrapper for database initialization"""
    try:
        import concurrent.futures
        import threading

        def run_database_init():
            """Run database initialization in isolated thread"""
            try:
                import asyncio

                # Create completely new event loop for this thread
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)

                try:
                    # Run initialization with reasonable timeout
                    result = new_loop.run_until_complete(
                        asyncio.wait_for(_initialize_database_async(),
                                         timeout=40.0))
                    return result
                except asyncio.TimeoutError:
                    logger.error(
                        "Database initialization timed out after 40 seconds")
                    return False
                except Exception as init_error:
                    logger.error(
                        f"Database initialization error: {init_error}")
                    return False
                finally:
                    # Clean up event loop
                    try:
                        # Cancel any pending tasks
                        pending = asyncio.all_tasks(new_loop)
                        for task in pending:
                            task.cancel()

                        # Close the loop
                        new_loop.close()
                    except Exception as cleanup_error:
                        logger.debug(
                            f"Event loop cleanup error: {cleanup_error}")

            except Exception as thread_error:
                logger.error(f"Thread execution error: {thread_error}")
                return False

        # Execute in isolated thread to prevent event loop conflicts
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_database_init)
            try:
                result = future.result(timeout=50)  # 50 second total timeout
                logger.info(f"Database initialization completed: {result}")
                return result
            except concurrent.futures.TimeoutError:
                logger.error("Database initialization thread timed out")
                return False

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False


def save_prediction_log_sync(prediction_data: Dict[str, Any],
                             allow_simulated: bool = False,
                             execution_source: str = None) -> Optional[int]:
    """Synchronous wrapper for saving prediction log"""

    async def _save_prediction():
        return await save_prediction_log(prediction_data, allow_simulated,
                                         execution_source)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _save_prediction())
                return future.result()
        else:
            return asyncio.run(_save_prediction())
    except Exception as e:
        logger.error(f"Error saving prediction: {e}")
        return None


def get_all_draws_sync():
    """Synchronous version of get_all_draws for use in non-async contexts."""
    try:
        import asyncio
        import concurrent.futures

        def run_async_in_thread():
            """Run async function in completely isolated thread"""
            try:
                # Create fresh event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                try:
                    # Initialize PostgreSQL pool if needed
                    async def init_and_get_draws():
                        try:
                            # Ensure connection pool is initialized
                            await postgresql_db.initialize_async_pool()
                            return await get_all_draws()
                        except Exception as e:
                            logger.error(f"Error in async operation: {e}")
                            return pd.DataFrame()

                    result = loop.run_until_complete(
                        asyncio.wait_for(init_and_get_draws(), timeout=30))
                    return result

                except asyncio.TimeoutError:
                    logger.error("Database operation timed out")
                    return pd.DataFrame()
                except Exception as e:
                    logger.error(f"Database operation failed: {e}")
                    return pd.DataFrame()
                finally:
                    # Clean shutdown
                    try:
                        # Close any remaining tasks
                        pending = asyncio.all_tasks(loop)
                        if pending:
                            for task in pending:
                                task.cancel()
                        loop.close()
                    except Exception:
                        pass

            except Exception as e:
                logger.error(f"Thread error: {e}")
                return pd.DataFrame()

        # Execute in isolated thread to avoid event loop conflicts
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_async_in_thread)
            try:
                return future.result(timeout=40)
            except concurrent.futures.TimeoutError:
                logger.error("get_all_draws_sync completely timed out")
                return pd.DataFrame()

    except Exception as e:
        logger.error(f"Error in get_all_draws_sync: {e}")
        return pd.DataFrame()


def get_prediction_history_sync(limit: int = 10):
    """Synchronous version of get_prediction_history for use in non-async contexts."""
    try:
        import asyncio
        return asyncio.run(get_prediction_history(limit=limit))
    except Exception as e:
        logger.error(f"Error in get_prediction_history_sync: {e}")
        return []


# Performance analytics function
async def get_performance_analytics(days: int = 30) -> Dict[str, Any]:
    """Get performance analytics from PostgreSQL"""
    try:
        async with postgresql_db.get_async_connection() as conn:
            # Get prediction count using proper PostgreSQL syntax
            total_predictions = await conn.fetchval(
                """
                SELECT COUNT(*) FROM predictions_log 
                WHERE created_at >= NOW() - INTERVAL '1 day' * $1
            """, days)

            # Calculate basic metrics
            return {
                'total_predictions': total_predictions or 0,
                'win_rate': 0.0,  # Placeholder for now
                'avg_accuracy': 0.0,  # Placeholder for now
                'recent_performance': {}
            }
    except Exception as e:
        logger.error(f"Error getting performance analytics: {e}")
        return {
            'total_predictions': 0,
            'win_rate': 0.0,
            'avg_accuracy': 0.0,
            'recent_performance': {}
        }


def get_performance_analytics_sync(days: int = 30) -> Dict[str, Any]:
    """Synchronous wrapper for getting performance analytics"""
    try:
        import asyncio
        import concurrent.futures

        def run_async_analytics():
            """Run analytics in isolated thread"""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                try:

                    async def get_analytics_safe():
                        try:
                            await postgresql_db.initialize_async_pool()
                            return await get_performance_analytics(days)
                        except Exception as e:
                            logger.warning(f"Analytics error: {e}")
                            return {
                                'total_predictions': 0,
                                'win_rate': 0.0,
                                'avg_accuracy': 0.0,
                                'recent_performance': {}
                            }

                    result = loop.run_until_complete(
                        asyncio.wait_for(get_analytics_safe(), timeout=15))
                    return result

                except asyncio.TimeoutError:
                    logger.warning("Analytics operation timed out")
                    return {
                        'total_predictions': 0,
                        'win_rate': 0.0,
                        'avg_accuracy': 0.0,
                        'recent_performance': {}
                    }
                finally:
                    try:
                        pending = asyncio.all_tasks(loop)
                        if pending:
                            for task in pending:
                                task.cancel()
                        loop.close()
                    except Exception:
                        pass

            except Exception as e:
                logger.error(f"Analytics thread error: {e}")
                return {
                    'total_predictions': 0,
                    'win_rate': 0.0,
                    'avg_accuracy': 0.0,
                    'recent_performance': {}
                }

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_async_analytics)
            try:
                return future.result(timeout=20)
            except concurrent.futures.TimeoutError:
                logger.warning("Analytics completely timed out")
                return {
                    'total_predictions': 0,
                    'win_rate': 0.0,
                    'avg_accuracy': 0.0,
                    'recent_performance': {}
                }

    except Exception as e:
        logger.error(f"Error getting performance analytics: {e}")
        return {
            'total_predictions': 0,
            'win_rate': 0.0,
            'avg_accuracy': 0.0,
            'recent_performance': {}
        }


def get_pipeline_execution_by_id_sync(
        execution_id: str) -> Optional[Dict[str, Any]]:
    """Synchronous wrapper for getting pipeline execution by ID"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, get_pipeline_execution_by_id(execution_id))
                return future.result()
        else:
            return asyncio.run(get_pipeline_execution_by_id(execution_id))
    except Exception as e:
        logger.error(f"Error getting pipeline execution {execution_id}: {e}")
        return None


# Alias synchronous functions for backward compatibility
# Note: These aliases point to the sync versions for backward compatibility
# The async versions remain available with their original names

# Keep async version available
initialize_database_async = _initialize_database_async

logger.info("PostgreSQL database module loaded successfully")
