"""
SHIOL+ Prediction API Endpoints
==============================

All prediction-related API endpoints separated from main API file.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger

from src.api_utils import convert_numpy_types, format_prediction_response, safe_database_operation
from src.predictor import Predictor
from src.intelligent_generator import IntelligentGenerator, DeterministicGenerator
from src.database import save_prediction_log, get_prediction_history
import src.database as db
from src.auth import User, get_current_user # Assuming auth module and User model exist

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

@prediction_router.get("/evaluation-by-date/{date}")
async def get_evaluation_by_date(date: str):
    """Get evaluation results for predictions on a specific date"""
    try:
        from src.database import get_db_connection
        from datetime import datetime
        
        # Validate date format
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get evaluation summary for the date
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_predictions,
                    COUNT(CASE WHEN evaluated = 1 THEN 1 END) as predictions_evaluated,
                    COUNT(CASE WHEN evaluated = 1 AND prize_amount > 0 THEN 1 END) as winning_predictions,
                    SUM(CASE WHEN evaluated = 1 THEN prize_amount ELSE 0 END) as total_prizes_won,
                    MAX(CASE WHEN evaluated = 1 THEN prize_amount ELSE 0 END) as best_prize,
                    AVG(CASE WHEN evaluated = 1 THEN matches_main ELSE 0 END) as average_matches
                FROM predictions_log pl
                WHERE COALESCE(pl.target_draw_date, DATE(pl.created_at)) = ?
                    AND pl.model_version NOT IN ('fallback', 'test', 'simulated')
                    AND pl.dataset_hash NOT IN ('simulated', 'test', 'fallback')
            """, (date,))
            
            summary_row = cursor.fetchone()
            
            if not summary_row or summary_row[0] == 0:
                raise HTTPException(status_code=404, detail="No predictions found for this date")
            
            total_predictions, predictions_evaluated, winning_predictions, total_prizes_won, best_prize, average_matches = summary_row
            
            win_rate = (winning_predictions / predictions_evaluated * 100) if predictions_evaluated > 0 else 0
            
            # Get prize winners for the date
            cursor.execute("""
                SELECT 
                    pl.numbers,
                    pl.powerball,
                    pl.prize_amount as prize_won,
                    pl.matches_main || CASE WHEN pl.powerball_match = 1 THEN ' + PB' ELSE '' END as matches,
                    pl.rank
                FROM predictions_log pl
                WHERE COALESCE(pl.target_draw_date, DATE(pl.created_at)) = ?
                    AND pl.evaluated = 1 
                    AND pl.prize_amount > 0
                    AND pl.model_version NOT IN ('fallback', 'test', 'simulated')
                ORDER BY pl.prize_amount DESC, pl.matches_main DESC
                LIMIT 20
            """, (date,))
            
            winners_rows = cursor.fetchall()
            
            prize_winners = []
            for row in winners_rows:
                try:
                    numbers_str = row[0]
                    if isinstance(numbers_str, str):
                        # Parse JSON array or comma-separated string
                        if numbers_str.startswith('['):
                            import json
                            numbers = json.loads(numbers_str)
                        else:
                            numbers = [int(n.strip()) for n in numbers_str.split(',')]
                    else:
                        numbers = [1, 2, 3, 4, 5]  # fallback
                    
                    prize_winners.append({
                        'numbers': numbers,
                        'powerball': row[1],
                        'prize_won': row[2],
                        'matches': row[3],
                        'rank': row[4] or len(prize_winners) + 1
                    })
                except Exception as parse_error:
                    logger.warning(f"Could not parse winner data: {parse_error}")
                    continue
            
            evaluation_summary = {
                'target_draw_date': date,
                'total_predictions': total_predictions,
                'predictions_evaluated': predictions_evaluated,
                'winning_predictions': winning_predictions,
                'total_prizes_won': total_prizes_won or 0,
                'best_prize': best_prize or 0,
                'win_rate': win_rate,
                'average_matches': average_matches or 0
            }
            
            return {
                'evaluation_summary': evaluation_summary,
                'prize_winners': prize_winners,
                'timestamp': datetime.now().isoformat()
            }
            
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error getting evaluation by date {date}: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting evaluation data: {str(e)}")


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


@prediction_router.get("/evaluation-results")
async def get_evaluation_results(
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """Get evaluation results showing predictions with their prize outcomes."""
    try:
        from src.database import get_db_connection

        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Get evaluated predictions with their results
            cursor.execute("""
                SELECT 
                    pl.id, pl.timestamp, pl.n1, pl.n2, pl.n3, pl.n4, pl.n5, pl.powerball,
                    pl.score_total, pl.target_draw_date, pl.matches_wb, pl.matches_pb,
                    pl.prize_amount, pl.prize_description, pl.evaluation_date,
                    pd.n1 as actual_n1, pd.n2 as actual_n2, pd.n3 as actual_n3,
                    pd.n4 as actual_n4, pd.n5 as actual_n5, pd.pb as actual_pb
                FROM predictions_log pl
                LEFT JOIN powerball_draws pd ON pl.target_draw_date = pd.draw_date
                WHERE pl.evaluated = TRUE
                ORDER BY pl.evaluation_date DESC, pl.score_total DESC
                LIMIT ?
            """, (limit,))

            results = cursor.fetchall()

            evaluation_results = []
            for row in results:
                result = {
                    "prediction_id": row[0],
                    "generated_at": row[1],
                    "prediction": {
                        "numbers": [row[2], row[3], row[4], row[5], row[6]],
                        "powerball": row[7],
                        "score": row[8],
                        "target_date": row[9]
                    },
                    "evaluation": {
                        "matches_main": row[10],
                        "matches_powerball": bool(row[11]),
                        "prize_amount": row[12],
                        "prize_description": row[13],
                        "evaluation_date": row[14]
                    },
                    "actual_result": {
                        "numbers": [row[15], row[16], row[17], row[18], row[19]] if row[15] else None,
                        "powerball": row[20] if row[20] else None
                    } if row[15] else None
                }
                evaluation_results.append(result)

            # Get summary statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN prize_amount > 0 THEN 1 END) as winning,
                    SUM(prize_amount) as total_prizes,
                    MAX(prize_amount) as best_prize
                FROM predictions_log
                WHERE evaluated = TRUE
            """)

            stats = cursor.fetchone()
            summary = {
                "total_evaluated": stats[0],
                "winning_predictions": stats[1],
                "win_rate_percentage": round((stats[1] / stats[0] * 100) if stats[0] > 0 else 0, 1),
                "total_prize_amount": stats[2] or 0.0,
                "best_prize_amount": stats[3] or 0.0
            }

            return {
                "evaluation_results": evaluation_results,
                "summary": summary,
                "count": len(evaluation_results),
                "method": "evaluation_results"
            }

    except Exception as e:
        logger.error(f"Error getting evaluation results: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting evaluation results: {str(e)}")