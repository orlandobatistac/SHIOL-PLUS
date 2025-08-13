"""
SHIOL+ System API Endpoints
==========================

System monitoring and health check endpoints.
"""

from fastapi import APIRouter, HTTPException
from loguru import logger
from typing import Dict, Any
import os
import sys
import psutil
from datetime import datetime
import sqlite3

from src.database import get_db_connection, get_db_path

# Create router for system endpoints
system_router = APIRouter(prefix="/system", tags=["system"])

@system_router.get("/health")
async def get_system_health() -> Dict[str, Any]:
    """Get comprehensive system health status"""
    try:
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # Database connectivity check
        db_status = "connected"
        try:
            from src.database import get_db_connection
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception as e:
            db_status = f"error: {str(e)}"

        # Model status check
        model_status = "unknown"
        try:
            from src.predictor import Predictor
            predictor = Predictor()
            if hasattr(predictor, 'model') and predictor.model:
                model_status = "loaded"
            else:
                model_status = "not_loaded"
        except Exception as e:
            model_status = f"error: {str(e)}"

        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available": memory.available,
                "disk_percent": disk.percent,
                "disk_free": disk.free
            },
            "database": {
                "status": db_status
            },
            "model": {
                "status": model_status
            },
            "python_version": sys.version,
            "uptime": "running"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@system_router.get("/info")
async def get_system_info() -> Dict[str, Any]:
    """Get basic system information"""
    try:
        return {
            "version": "6.0.0",
            "status": "operational",
            "timestamp": datetime.now().isoformat(),
            "python_version": sys.version.split()[0]
        }
    except Exception as e:
        logger.error(f"System info failed: {e}")
        raise HTTPException(status_code=500, detail=f"System info failed: {str(e)}")

@system_router.get("/status")
async def get_system_status() -> Dict[str, Any]:
    """Get simple system status"""
    return {
        "status": "online",
        "timestamp": datetime.now().isoformat()
    }

@system_router.get("/database/stats")
async def get_database_stats():
    """Get database statistics"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Get table sizes
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()

            stats = {}
            total_records = 0

            for table in tables:
                table_name = table[0]
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                stats[table_name] = count
                total_records += count

            # Get database file size
            db_path = get_db_path()
            file_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

            return {
                "total_records": total_records,
                "tables": stats,
                "file_size_bytes": file_size,
                "file_size_mb": round(file_size / (1024*1024), 2)
            }

    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting database stats: {str(e)}")

@system_router.post("/database/cleanup")
async def cleanup_database(cleanup_options: Dict[str, Any]):
    """Clean up database based on provided options"""
    try:
        logger.info(f"Database cleanup requested with options: {cleanup_options}")

        cleanup_summary = {
            "predictions_removed": 0,
            "pipeline_logs_removed": 0,
            "old_data_removed": 0,
            "vacuum_applied": False
        }

        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Clean predictions if requested
            if cleanup_options.get("predictions", False):
                cursor.execute("DELETE FROM predictions_log WHERE created_at < datetime('now', '-7 days')")
                cleanup_summary["predictions_removed"] = cursor.rowcount
                logger.info(f"Removed {cursor.rowcount} old predictions")

            # Clean pipeline logs if requested
            if cleanup_options.get("pipeline_logs", False):
                cursor.execute("DELETE FROM pipeline_executions WHERE start_time < datetime('now', '-30 days')")
                cleanup_summary["pipeline_logs_removed"] = cursor.rowcount
                logger.info(f"Removed {cursor.rowcount} old pipeline executions")

            # Clean general old data if requested
            if cleanup_options.get("logs", False):
                # Clean old performance tracking data
                cursor.execute("DELETE FROM performance_tracking WHERE created_at < datetime('now', '-30 days')")
                cleanup_summary["old_data_removed"] = cursor.rowcount
                logger.info(f"Removed {cursor.rowcount} old performance tracking records")

            conn.commit()

        # Apply VACUUM if requested (outside the context manager)
        if cleanup_options.get("vacuum", True):
            try:
                with get_db_connection() as vacuum_conn:
                    vacuum_conn.execute("VACUUM")
                cleanup_summary["vacuum_applied"] = True
                logger.info("VACUUM applied successfully")
            except Exception as vacuum_error:
                logger.warning(f"VACUUM failed: {vacuum_error}")

        logger.info(f"Database cleanup completed: {cleanup_summary}")
            return {
                "success": True,
                "message": "Database cleanup completed successfully",
                "summary": cleanup_summary
            }

    except Exception as e:
        logger.error(f"Error during database cleanup: {e}")
        raise HTTPException(status_code=500, detail=f"Database cleanup failed: {str(e)}")