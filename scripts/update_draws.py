#!/usr/bin/env python3
"""
One-shot script to initialize the SQLite schema and populate/refresh Powerball draws.

Usage (from repo root):
    python scripts/update_draws.py

Data Source Strategy (v6.4 - Current Architecture):
- EMPTY DB: NC Lottery CSV (bulk historical) → fallback MUSL
- STALE DB (>1 day old): NC CSV (full refresh) → fallback MUSL  
- CURRENT DB: MUSL API (incremental check) → fallback Web Scraping

Environment Variables:
- MUSL_API_KEY: Required for MUSL API access (official source)

Output:
- Database path
- Draw count before/after update
- Latest 10 draw dates
"""
from loguru import logger

try:
    from src.database import initialize_database, get_db_connection, get_db_path
    from src.loader import update_database_from_source
except Exception as e:
    raise SystemExit(f"Failed to import project modules. Run from the repo root. Error: {e}")


def main() -> int:
    try:
        db_path = get_db_path()
        logger.info(f"Database path: {db_path}")

        # Ensure schema exists
        initialize_database()

        # Snapshot before
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM powerball_draws")
            before = cur.fetchone()[0] or 0
            logger.info(f"Existing draws before update: {before}")

        # Update from sources
        total_after = update_database_from_source()
        logger.info(f"Total draws after update: {total_after}")

        # Show latest 10 dates
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT draw_date FROM powerball_draws ORDER BY draw_date DESC LIMIT 10")
            rows = [r[0] for r in cur.fetchall()]

        logger.info("Latest 10 draw dates (DESC):")
        for d in rows:
            logger.info(f"  {d}")

        # Return 0 on success
        return 0
    except SystemExit:
        raise
    except Exception as e:
        logger.exception(f"Update failed: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
