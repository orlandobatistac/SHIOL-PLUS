#!/usr/bin/env python3
"""
Manual pipeline trigger for SHIOL-PLUS.

This script initializes the database (idempotent) and then invokes the
enhanced end-to-end pipeline defined in src/api.py.

Usage:
    python scripts/run_pipeline.py
"""
import os
import sys
import asyncio

from loguru import logger

# Load environment variables from .env if available
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


def ensure_project_root_on_path() -> None:
    """Ensure repository root is on sys.path when running from subdirs."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


def main() -> int:
    try:
        ensure_project_root_on_path()

        # Ensure database schema exists (safe to call multiple times)
        from src.database import initialize_database
        initialize_database()

        # Mark execution source for observability
        os.environ.setdefault("PIPELINE_EXECUTION_SOURCE", "manual_script")

        # Import the pipeline entry and execute
        from src.api import trigger_full_pipeline_automatically

        logger.info("Starting manual pipeline run...")
        result = asyncio.run(trigger_full_pipeline_automatically())

        success = bool(result and result.get("success", False))
        if success:
            logger.info(f"Pipeline completed successfully (id={result.get('execution_id')}, elapsed={result.get('elapsed_seconds')}s)")
            return 0
        else:
            logger.error(f"Pipeline reported failure: {result}")
            return 1

    except KeyboardInterrupt:
        logger.warning("Pipeline execution interrupted by user")
        return 130
    except Exception as e:
        logger.exception(f"Manual pipeline run failed: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
