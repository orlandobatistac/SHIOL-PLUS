
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
