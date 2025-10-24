import sqlite3

from src.database import get_db_connection, initialize_database


def test_get_db_connection_returns_sqlite_connection():
    conn = get_db_connection()
    assert isinstance(conn, sqlite3.Connection)
    conn.close()


def test_initialize_database_creates_core_tables():
    # Should not raise
    initialize_database()

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}

        # Check a subset of expected tables referenced across the codebase
        expected_subset = {
            "pipeline_executions",  # used by pipeline execution helpers
            "webhook_events",       # used by billing webhook idempotency
            "idempotency_keys",     # used by checkout idempotency
            "premium_passes",       # used by premium pass service
        }
        assert expected_subset.issubset(tables)
    finally:
        conn.close()
