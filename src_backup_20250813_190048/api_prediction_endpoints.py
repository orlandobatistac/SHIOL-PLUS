
"""
SHIOL+ Prediction API Endpoints
==============================

All prediction-related API endpoints separated from main API file.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger

from src.api_utils import convert_numpy_types, format_prediction_response, safe_database_operation
from src.predictor import Predictor
from src.intelligent_generator import IntelligentGenerator, DeterministicGenerator
from src.database import save_prediction_log, get_prediction_history
import src.database as db

# Fix for calculate_next_drawing_date function
def calculate_next_drawing_date():
    """Calculate next Powerball drawing date (Mon, Wed, Sat)"""
    from datetime import datetime, timedelta
    today = datetime.now()
    # Powerball drawings: Monday (0), Wednesday (2), Saturday (5)
    drawing_days = [0, 2, 5]
    
    for i in range(7):  # Check next 7 days
        check_date = today + timedelta(days=i)
        if check_date.weekday() in drawing_days:
            return check_date.strftime('%Y-%m-%d')
    
    # Fallback to next Monday
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    next_drawing = today + timedelta(days=days_until_monday)
    return next_drawing.strftime('%Y-%m-%d')

# Create router for prediction endpoints
prediction_router = APIRouter(prefix="/api/v1", tags=["predictions"])

# Global components (will be injected from main API)
predictor = None
intelligent_generator = None
deterministic_generator = None


def set_prediction_components(pred, intel_gen, det_gen):
    """Set global prediction components."""
    global predictor, intelligent_generator, deterministic_generator
    predictor = pred
    intelligent_generator = intel_gen
    deterministic_generator = det_gen


@prediction_router.get("/predict")
async def get_prediction(deterministic: bool = Query(False, description="Use deterministic method")):
    """
    DISABLED: Individual prediction generation is no longer supported.
    Use pipeline execution instead for generating predictions.
    """
    logger.warning("Attempt to use disabled individual prediction endpoint")
    raise HTTPException(
        status_code=410, 
        detail={
            "error": "Individual prediction generation disabled",
            "message": "This endpoint has been disabled. Use pipeline execution instead.",
            "alternative": "POST /api/v1/pipeline/trigger",
            "reason": "System now only supports full pipeline execution for prediction generation"
        }
    )


@prediction_router.get("/predict-multiple")
async def get_multiple_predictions(count: int = Query(1, ge=1, le=10)):
    """
    DISABLED: Multiple prediction generation is no longer supported.
    Use pipeline execution instead for generating predictions.
    """
    logger.warning("Attempt to use disabled multiple prediction endpoint")
    raise HTTPException(
        status_code=410, 
        detail={
            "error": "Multiple prediction generation disabled",
            "message": "This endpoint has been disabled. Use pipeline execution instead.",
            "alternative": "POST /api/v1/pipeline/trigger?num_predictions=100",
            "reason": "System now only supports full pipeline execution for prediction generation"
        }
    )


@prediction_router.get("/predict-deterministic")
async def get_deterministic_prediction():
    """
    DISABLED: Deterministic prediction generation is no longer supported.
    Use pipeline execution instead for generating predictions.
    """
    logger.warning("Attempt to use disabled deterministic prediction endpoint")
    raise HTTPException(
        status_code=410, 
        detail={
            "error": "Deterministic prediction generation disabled",
            "message": "This endpoint has been disabled. Use pipeline execution instead.",
            "alternative": "POST /api/v1/pipeline/trigger?num_predictions=100",
            "reason": "System now only supports full pipeline execution for prediction generation"
        }
    )


@prediction_router.get("/predict/smart")
async def get_smart_predictions(limit: int = Query(100, ge=1, le=100, description="Number of Smart AI predictions")):
    """
    Get Smart AI predictions from database with next drawing information.
    """
    try:
        logger.info(f"Received request for {limit} Smart AI predictions from database")

        # Calculate next drawing date
        next_drawing_date = calculate_next_drawing_date()
        current_date = datetime.now()
        next_date = datetime.strptime(next_drawing_date, '%Y-%m-%d')
        days_until_drawing = (next_date - current_date).days
        is_drawing_day = current_date.weekday() in [0, 2, 5]

        # Get ONLY real pipeline predictions from database (no simulated data)
        predictions_df = db.get_prediction_history(limit=limit)

        smart_predictions = []
        if not predictions_df.empty:
            # STRICT FILTER: Only process real pipeline predictions
            for i, pred in enumerate(predictions_df.to_dict('records')):
                try:
                    # Validate this is a real prediction from pipeline
                    model_version = str(pred.get("model_version", ""))
                    dataset_hash = str(pred.get("dataset_hash", ""))
                    
                    # REJECT simulated, test, or fallback data completely
                    if (model_version in ["fallback", "test", "simulated", "1.0.0-test"] or
                        dataset_hash in ["simulated", "test", "fallback"] or
                        len(dataset_hash) < 10):  # Reject short/invalid hashes
                        logger.debug(f"Rejecting non-pipeline prediction: model={model_version}, hash={dataset_hash}")
                        continue
                    
                    numbers = [int(pred.get(f"n{j}", 0)) for j in range(1, 6)]
                    powerball = int(pred.get("powerball", 0))
                    total_score = float(pred.get("score_total", 0.0))
                    
                    # Validate number ranges
                    if not all(1 <= num <= 69 for num in numbers) or not (1 <= powerball <= 26):
                        logger.debug(f"Rejecting prediction with invalid number ranges")
                        continue

                    smart_pred = {
                        "rank": i + 1,
                        "numbers": numbers,
                        "powerball": powerball,
                        "total_score": total_score,
                        "score_details": {
                            "probability": total_score * 0.4,
                            "diversity": total_score * 0.25,
                            "historical": total_score * 0.2,
                            "risk_adjusted": total_score * 0.15
                        },
                        "model_version": model_version,
                        "dataset_hash": dataset_hash,
                        "prediction_id": int(pred.get("id", 0)),
                        "generated_at": str(pred.get("timestamp", "")),
                        "method": "smart_ai_pipeline"
                    }
                    smart_predictions.append(smart_pred)
                except Exception as e:
                    logger.warning(f"Error converting prediction record {i}: {e}")
                    continue

        # NO FALLBACK DATA: If no real predictions exist, return empty
        if not smart_predictions:
            logger.info("No real Smart AI predictions available - pipeline must be executed first")

        # Calculate statistics
        avg_score = sum(p["total_score"] for p in smart_predictions) / len(smart_predictions) if smart_predictions else 0.0
        best_score = max(p["total_score"] for p in smart_predictions) if smart_predictions else 0.0

        return {
            "method": "smart_ai_database",
            "smart_predictions": smart_predictions,
            "total_predictions": len(smart_predictions),
            "average_score": avg_score,
            "best_score": best_score,
            "data_source": "database" if smart_predictions else "empty",
            "next_drawing": {
                "date": next_drawing_date,
                "formatted_date": next_date.strftime('%B %d, %Y'),
                "days_until": days_until_drawing,
                "is_today": days_until_drawing == 0,
                "is_drawing_day": is_drawing_day
            },
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error retrieving Smart AI predictions: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving Smart AI predictions.")


@prediction_router.get("/predict-diverse")
async def get_diverse_predictions(num_plays: int = Query(5, ge=1, le=10)):
    """
    DISABLED: Diverse prediction generation is no longer supported.
    Use pipeline execution instead for generating predictions.
    """
    logger.warning("Attempt to use disabled diverse prediction endpoint")
    raise HTTPException(
        status_code=410, 
        detail={
            "error": "Diverse prediction generation disabled",
            "message": "This endpoint has been disabled. Use pipeline execution instead.",
            "alternative": "POST /api/v1/pipeline/trigger?num_predictions=100",
            "reason": "System now only supports full pipeline execution for prediction generation"
        }
    )
