#!/usr/bin/env python3
"""
SHIOL-PLUS FastAPI Application Entrypoint

The scheduler and all business logic is in src/api.py
This file is just a simple entrypoint for uvicorn.
Now reads HOST, PORT, LOG_LEVEL from environment (loaded from .env when available).
"""
import os

# Load environment variables from .env if available
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    # dotenv is optional; proceed if not installed
    pass

from src.api import app

if __name__ == "__main__":
    import uvicorn

    # Read server configuration from environment with sensible defaults
    host = os.getenv("HOST", "0.0.0.0")

    port_str = os.getenv("PORT", "8000")
    try:
        port = int(port_str)
    except ValueError:
        port = 8000

    log_level = os.getenv("LOG_LEVEL", "info").lower()
    # Uvicorn supported levels: critical, error, warning, info, debug, trace
    if log_level not in {"critical", "error", "warning", "info", "debug", "trace"}:
        log_level = "info"

    uvicorn.run(app, host=host, port=port, log_level=log_level)
