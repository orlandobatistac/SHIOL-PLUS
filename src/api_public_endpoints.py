
"""
SHIOL+ Public API Endpoints
===========================

API endpoints specifically for the public frontend (index.html).
These endpoints provide public access to predictions and historical data.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger
import os
from pathlib import Path

from src.api_utils import convert_numpy_types, format_prediction_response
from src.database import get_all_draws, get_prediction_history, get_grouped_predictions_with_results_comparison
from src.predictor import Predictor
from src.intelligent_generator import IntelligentGenerator, DeterministicGenerator

# Create router for public frontend endpoints
public_frontend_router = APIRouter(tags=["public_frontend"])

# Global components (will be injected from main API)
predictor = None
intelligent_generator = None
deterministic_generator = None

def set_public_components(pred, intel_gen, det_gen):
    """Set the global components for public endpoints."""
    global predictor, intelligent_generator, deterministic_generator
    predictor = pred
    intelligent_generator = intel_gen
    deterministic_generator = det_gen

# Build path to frontend templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
templates = Jinja2Templates(directory=FRONTEND_DIR)

@public_frontend_router.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    """Serve the main public index page"""
    return templates.TemplateResponse("index.html", {"request": request})

@public_frontend_router.get("/public", response_class=HTMLResponse)  
async def serve_public(request: Request):
    """Serve the public static page"""
    return templates.TemplateResponse("static_public.html", {"request": request})

@public_frontend_router.get("/api/v1/public/predictions/smart")
async def get_public_smart_predictions(limit: int = 100):
    """DISABLED: Public smart prediction generation is no longer supported.
    Use database queries for existing pipeline predictions only."""
    logger.warning("Attempt to use disabled public smart prediction generation")
    raise HTTPException(
        status_code=410, 
        detail={
            "error": "Public prediction generation disabled",
            "message": "This endpoint no longer generates new predictions.",
            "alternative": "GET /api/v1/predict/smart (for existing predictions)",
            "reason": "System now only supports pipeline-generated predictions from database"
        }
    )

@public_frontend_router.get("/api/v1/public/history/grouped")
async def get_public_grouped_history():
    """Get grouped prediction history for public access"""
    try:
        grouped_data = get_grouped_predictions_with_results_comparison()
        return {"grouped_dates": convert_numpy_types(grouped_data)}
        
    except Exception as e:
        logger.error(f"Error getting public grouped history: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting history: {str(e)}")

@public_frontend_router.get("/api/v1/public/draws/recent")
async def get_public_recent_draws(limit: int = 10):
    """Get recent draws for public access"""
    try:
        draws = get_all_draws(limit=min(limit, 50))  # Limit to 50 for public
        return {"draws": convert_numpy_types(draws)}
        
    except Exception as e:
        logger.error(f"Error getting public recent draws: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting draws: {str(e)}")
