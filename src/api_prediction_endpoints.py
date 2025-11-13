import traceback
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, Query, APIRouter
from pydantic import BaseModel, Field
from typing import Dict, Any

from loguru import logger
from src.utils import get_latest_draw_date
from src.prediction_evaluator import PredictionEvaluator
from src.database import get_db_connection
# from src.auth import get_current_user, User  # REMOVED - no authentication in simplified version

# Define Pydantic models for response
class Prediction(BaseModel):
    draw_date: str
    numbers_predicted: List[int] = Field(..., description="The numbers predicted.")
    powerball_predicted: int = Field(..., description="The predicted Powerball number.")
    matches: int = Field(..., description="Number of matched numbers.")
    powerball_match: bool = Field(..., description="True if Powerball matched.")
    prize_amount: Optional[float] = Field(None, description="Prize amount for this prediction.")
    ticket_id: Optional[str] = Field(None, description="Unique identifier for the ticket.")

class PredictionResponse(BaseModel):
    draw_date: str
    requested_date: str # Added to show the original requested date
    min_matches: int
    predictions: List[Prediction]
    total_predictions: int
    winning_numbers: Optional[dict] = Field(None, description="The actual winning numbers for the draw.")
    total_prizes: Optional[float] = Field(None, description="Total prize money awarded for the draw.")
    message: Optional[str] = Field(None, description="Informational message about the response.")
    draw_info: Optional[dict] = Field(None, description="Additional information about the draw.") # Changed to dict to be more flexible

class DrawInfo(BaseModel):
    draw_date: str
    winning_numbers: List[int]
    powerball: int
    prize_amount: float

class RecentDrawsResponse(BaseModel):
    draw_date: str
    winning_numbers: List[int]
    powerball: int

# Routers for modular API
prediction_router = APIRouter()
draw_router = APIRouter()

# Global component references (set by main API)
predictor = None
intelligent_generator = None
deterministic_generator = None

def set_prediction_components(pred, intel_gen, det_gen):
    """Set prediction components from main API"""
    global predictor, intelligent_generator, deterministic_generator
    predictor = pred
    intelligent_generator = intel_gen
    deterministic_generator = det_gen

def validate_date_format(date_string: str) -> bool:
    """Validates if the date string is in YYYY-MM-DD format."""
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
        return True
    except ValueError:
        return False

@prediction_router.get(
    "/predictions/by-draw/{draw_date}",
    response_model=PredictionResponse,
    summary="Get predictions for a specific draw date",
    description="Retrieves predictions for a given draw date, optionally filtered by minimum matched numbers.",
)
async def get_predictions_by_draw(
    draw_date: str,
    min_matches: int = Query(0, description="Minimum number of matches to include"),
    limit: int = Query(100, description="Maximum number of predictions to return"),

):
    """
    Get all predictions for a specific draw date with match analysis.
    Enhanced with comprehensive statistics and performance metrics.
    """
    try:
        # Clean and validate the draw_date input
        cleaned_draw_date = draw_date.strip()

        logger.info(f"Raw input draw_date: '{draw_date}' -> cleaned: '{cleaned_draw_date}'")
        logger.info(f"Getting predictions for draw date: {cleaned_draw_date} (min_matches: {min_matches}, limit: {limit})")

        # Validate date format
        if not validate_date_format(cleaned_draw_date):
            raise HTTPException(status_code=400, detail=f"Invalid date format: {cleaned_draw_date}. Expected YYYY-MM-DD")

        # Get database connection
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get the actual draw results for this date with flexible date matching
        cursor.execute("""
            SELECT n1, n2, n3, n4, n5, powerball, jackpot_amount, draw_date
            FROM draws 
            WHERE draw_date = ? OR DATE(draw_date) = ?
            ORDER BY draw_date DESC
            LIMIT 1
        """, (cleaned_draw_date, cleaned_draw_date))

        draw_result = cursor.fetchone()
        winning_numbers = None
        winning_powerball = None
        jackpot_amount = None
        actual_draw_date = cleaned_draw_date

        if draw_result:
            winning_numbers = [draw_result[0], draw_result[1], draw_result[2], draw_result[3], draw_result[4]]
            winning_powerball = draw_result[5]
            jackpot_amount = draw_result[6]
            actual_draw_date = draw_result[7] if draw_result[7] else cleaned_draw_date
            logger.info(f"Found winning numbers for {actual_draw_date}: {winning_numbers} + PB: {winning_powerball}")
        else:
            logger.warning(f"No draw results found for date: {cleaned_draw_date}")

        # Get predictions for this draw date with enhanced date matching
        prediction_query = """
            SELECT 
                id, created_at, n1, n2, n3, n4, n5, powerball, 
                confidence_score, strategy_used, strategy_used, confidence_score,
                draw_date, created_at
            FROM generated_tickets 
            WHERE draw_date = ?
            ORDER BY confidence_score DESC
            LIMIT ?
        """

        cursor.execute(prediction_query, (cleaned_draw_date, limit * 2))
        predictions = cursor.fetchall()

        logger.info(f"Found {len(predictions)} total predictions for {cleaned_draw_date}")

        # Process predictions to calculate matches and filter by min_matches
        formatted_predictions = []
        for pred in predictions:
            pred_numbers = [pred[2], pred[3], pred[4], pred[5], pred[6]]
            pred_powerball = pred[7]

            matches_main = 0
            if winning_numbers:
                matches_main = sum(1 for num in pred_numbers if num in winning_numbers)

            matches_powerball = False
            if winning_powerball is not None:
                matches_powerball = (pred_powerball == winning_powerball)

            if matches_main >= min_matches or (matches_powerball and min_matches <= 5): # Adjust condition for powerball match
                prize_amount = 0 # Placeholder for prize calculation logic

                formatted_predictions.append({
                    "draw_date": pred[12],  # Use draw_date
                    "numbers_predicted": pred_numbers,
                    "powerball_predicted": pred_powerball,
                    "matches": matches_main,
                    "powerball_match": matches_powerball,
                    "prize_amount": prize_amount,
                    "ticket_id": f"pred_{pred[0]}"
                })

        # Sort and limit final predictions
        formatted_predictions.sort(key=lambda x: (-x['matches'], -x['prize_amount'])) # Sort by matches descending, then prize amount descending
        final_predictions = formatted_predictions[:limit]


        conn.close()

        return {
            "draw_date": actual_draw_date,  # Use the actual draw date from database
            "requested_date": cleaned_draw_date,  # Original requested date
            "min_matches": min_matches,
            "predictions": final_predictions,
            "total_predictions": len(final_predictions),
            "winning_numbers": {
                "main_numbers": winning_numbers,
                "powerball": winning_powerball
            },
            "summary": {
                "total_with_matches": len([p for p in final_predictions if p.get('matches', 0) > 0 or p.get('powerball_match', False)]),
                "total_prizes": sum(p.get('prize_amount', 0) for p in final_predictions),
                "best_performance": max([p.get('matches', 0) for p in final_predictions] or [0])
            },
            "draw_info": {
                "winning_numbers": winning_numbers,
                "winning_powerball": winning_powerball,
                "jackpot_amount": jackpot_amount,
                "has_results": draw_result is not None,
                "actual_draw_date": actual_draw_date
            },
            "message": f"Found {len(final_predictions)} predictions with {min_matches}+ matches" if final_predictions else f"No predictions found with {min_matches}+ matches"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting predictions by draw {cleaned_draw_date}: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@prediction_router.get(
    "/all/{draw_date}",
    response_model=List[Prediction],
    summary="Get all predictions for a specific draw date",
    description="Retrieves all predictions for a given draw date, regardless of matches.",
)
async def get_all_predictions(draw_date: str):
    """
    Get all predictions for a specific draw date.
    """
    logger.info(f"Getting all predictions for draw date: {draw_date}")
    try:
        # Validate date format
        from datetime import datetime
        try:
            datetime.strptime(draw_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        evaluator = PredictionEvaluator()
        predictions_data = evaluator.get_all_predictions_for_draw(draw_date)

        if not predictions_data:
            logger.warning(f"No predictions found for draw date: {draw_date}")
            return []

        return predictions_data

    except Exception as e:
        logger.error(f"Error getting all predictions for draw {draw_date}: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@draw_router.get(
    "/latest",
    response_model=DrawInfo,
    summary="Get the latest Powerball draw information",
    description="Retrieves the most recent Powerball draw date, winning numbers, and prize amount.",
)
async def get_latest_draw():
    """
    Get the latest Powerball draw information.
    """
    logger.info("Getting the latest Powerball draw information.")
    try:
        latest_draw_date = get_latest_draw_date()
        if not latest_draw_date:
            logger.error("Could not retrieve the latest draw date.")
            raise HTTPException(status_code=404, detail="Latest draw information not found.")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT draw_date, n1, n2, n3, n4, n5, pb
            FROM powerball_draws 
            WHERE draw_date = ?
        """, (latest_draw_date,))
        draw_data = cursor.fetchone()
        conn.close()

        if not draw_data:
            logger.error(f"Draw data not found for the latest draw date: {latest_draw_date}")
            raise HTTPException(status_code=404, detail="Latest draw data not found.")

        return DrawInfo(
            draw_date=draw_data[0],
            winning_numbers=[draw_data[1], draw_data[2], draw_data[3], draw_data[4], draw_data[5]],
            powerball=draw_data[6],
            prize_amount=0.0,  # Set default since column doesn't exist
        )

    except Exception as e:
        logger.error(f"Error getting latest draw information: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@draw_router.get(
    "/recent",
    response_model=List[RecentDrawsResponse],
    summary="Get recent Powerball draws",
    description="Retrieves a list of the most recent Powerball draws.",
)
async def get_recent_draws(limit: int = Query(default=5, ge=1, le=10, description="Number of recent draws to retrieve.")):
    """
    Get a list of recent Powerball draws.
    """
    logger.info(f"Getting {limit} recent Powerball draws.")
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Could not establish database connection")
            raise HTTPException(status_code=500, detail="Database connection failed")

        cursor = conn.cursor()
        cursor.execute(
            "SELECT draw_date, n1, n2, n3, n4, n5, pb FROM draws ORDER BY draw_date DESC LIMIT ?",
            (limit,),
        )
        draw_data = cursor.fetchall()
        conn.close()

        if not draw_data:
            logger.warning("No recent draw data found.")
            return []

        recent_draws = []
        for draw in draw_data:
            recent_draws.append(
                RecentDrawsResponse(
                    draw_date=draw[0],
                    winning_numbers=[draw[1], draw[2], draw[3], draw[4], draw[5]],
                    powerball=draw[6],
                )
            )
        return recent_draws

    except Exception as e:
        logger.error(f"Error getting recent draws: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@prediction_router.get(
    "/detailed/{draw_date}",
    response_model=PredictionResponse,
    summary="Get comprehensive predictions analysis for a specific draw date (authenticated)",
    description="Retrieves detailed predictions analysis for a given draw date with full details. Requires authentication.",
)
async def get_detailed_predictions_by_draw(
    draw_date: str,
    min_matches: int = Query(default=0, ge=0, le=6),

):
    """Get comprehensive predictions analysis for a specific draw date (authenticated)"""
    try:
        # Validate date format
        try:
            datetime.strptime(draw_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Get predictions from database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get draw info first
        cursor.execute("""
            SELECT draw_date, n1, n2, n3, n4, n5, pb
            FROM draws 
            WHERE draw_date = ?
        """, (draw_date,))

        draw_info = cursor.fetchone()
        if not draw_info:
            # Check if we have predictions for this date even without official draw results
            cursor.execute("""
                SELECT COUNT(*) FROM generated_tickets 
                WHERE draw_date = ?
            """, (draw_date,))

            pred_count = cursor.fetchone()[0]

            if pred_count == 0:
                conn.close()
                raise HTTPException(status_code=404, detail=f"No data found for date {draw_date}")

            # We have predictions but no official draw results yet
            winning_numbers = {"main_numbers": [], "powerball": None}
            jackpot_amount = 0
        else:
            winning_numbers = {
                "main_numbers": [draw_info[1], draw_info[2], draw_info[3], draw_info[4], draw_info[5]],
                "powerball": draw_info[6]
            }
            jackpot_amount = 0

        # Get all predictions for this date
        cursor.execute("""
            SELECT id, created_at, n1, n2, n3, n4, n5, powerball, confidence_score, strategy_used
            FROM generated_tickets 
            WHERE draw_date = ?
            ORDER BY confidence_score DESC
        """, (draw_date,))

        all_predictions = cursor.fetchall()
        conn.close()

        # Format predictions with enhanced details
        formatted_predictions = []
        for i, pred in enumerate(all_predictions):
            prediction_data = {
                "rank": i + 1,
                "prediction_id": f"pred_{pred[0]}",
                "numbers": [pred[2], pred[3], pred[4], pred[5], pred[6]],
                "powerball": pred[7],
                "confidence_score": pred[8] if pred[8] is not None else 0,
                "ai_method": pred[9] or "standard",
                "matches_main": 0,
                "matches_powerball": False,
                "prize_amount": 0
            }
            formatted_predictions.append(prediction_data)

        return {
            "draw_date": draw_date,
            "requested_date": draw_date,
            "min_matches": min_matches,
            "predictions": formatted_predictions,
            "total_predictions": len(formatted_predictions),
            "winning_numbers": {
                "main_numbers": winning_numbers["main_numbers"],
                "powerball": winning_numbers["powerball"]
            },
            "summary": {
                "total_predictions_with_matches": 0,
                "predictions_with_prizes": 0,
                "total_prize_won": 0,
                "best_match": 0,
                "average_score": sum(p["total_score"] for p in formatted_predictions) / len(formatted_predictions) if formatted_predictions else 0
            },
            "draw_info": {
                "winning_numbers": winning_numbers["main_numbers"],
                "winning_powerball": winning_numbers["powerball"],
                "jackpot_amount": jackpot_amount,
                "has_results": bool(draw_info),
                "actual_draw_date": draw_date
            },
            "message": "No predictions found with specified criteria" if not formatted_predictions else f"Found {len(formatted_predictions)} predictions"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting detailed predictions by draw: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving predictions: {str(e)}")

# Import the official prize calculator
from src.prize_calculator import calculate_prize_amount

@prediction_router.get("/by-draw/{draw_date}")
async def get_predictions_by_draw_date(
    draw_date: str,
    min_matches: int = Query(0, ge=0, description="Minimum number of matches required"),
    limit: int = Query(20, ge=1, le=500, description="Maximum number of predictions to return")
):
    """Get predictions for a specific draw date with match analysis"""
    try:
        logger.info(f"Getting predictions for draw date: {draw_date}, min_matches: {min_matches}, limit: {limit}")

        # Parse and validate the date
        try:
            if len(draw_date) == 10 and '-' in draw_date:
                # Format: YYYY-MM-DD
                target_date = datetime.strptime(draw_date, '%Y-%m-%d').date()
            else:
                # Try other common formats
                for fmt in ['%Y%m%d', '%m/%d/%Y', '%m-%d-%Y']:
                    try:
                        target_date = datetime.strptime(draw_date, fmt).date()
                        break
                    except ValueError:
                        continue
                else:
                    raise ValueError("Invalid date format")
        except ValueError:
            logger.error(f"Invalid date format: {draw_date}")
            raise HTTPException(status_code=400, detail=f"Invalid date format: {draw_date}. Use YYYY-MM-DD")

        target_date_str = target_date.strftime('%Y-%m-%d')
        logger.info(f"Parsed target date: {target_date_str}")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get draw information for the date
        cursor.execute(
            "SELECT * FROM powerball_draws WHERE draw_date = ?",
            (target_date_str,)
        )
        draw_info = cursor.fetchone()

        if not draw_info:
            logger.warning(f"No draw found for date: {target_date_str}")
            conn.close()
            return {
                "draw_date": target_date_str,
                "requested_date": draw_date,
                "predictions": [],
                "total_predictions": 0,
                "winning_numbers": None,
                "total_prizes": 0,
                "message": f"No draw found for date {target_date_str}"
            }

        # Convert draw row to dict
        draw_columns = [desc[0] for desc in cursor.description]
        draw_dict = dict(zip(draw_columns, draw_info))

        winning_numbers = [draw_dict['n1'], draw_dict['n2'], draw_dict['n3'], draw_dict['n4'], draw_dict['n5']]
        winning_powerball = draw_dict['pb']

        logger.info(f"Draw found - Winning numbers: {winning_numbers}, PB: {winning_powerball}")

        # Get predictions for this date
        cursor.execute("""
            SELECT 
                id,
                created_at,
                n1, n2, n3, n4, n5, powerball,
                confidence_score,
                strategy_used,
                draw_date,
                created_at
            FROM generated_tickets 
            WHERE draw_date = ?
            ORDER BY confidence_score DESC
            LIMIT ?
        """, (target_date_str, limit * 2))  # Get more to filter later

        predictions_raw = cursor.fetchall()
        conn.close()

        if not predictions_raw:
            logger.warning(f"No predictions found for date: {target_date_str}")
            return {
                "draw_date": target_date_str,
                "requested_date": draw_date,
                "predictions": [],
                "total_predictions": 0,
                "winning_numbers": {
                    "main_numbers": winning_numbers,
                    "powerball": winning_powerball
                },
                "total_prizes": 0,
                "message": f"No predictions found for date {target_date_str}"
            }

        logger.info(f"Found {len(predictions_raw)} predictions for analysis")

        # Calculate matches and format predictions
        formatted_predictions = []
        total_prizes = 0

        for pred in predictions_raw:
            pred_numbers = [pred[2], pred[3], pred[4], pred[5], pred[6]]  # n1-n5
            pred_powerball = pred[7]  # powerball

            # Calculate matches
            main_matches = len(set(pred_numbers) & set(winning_numbers))
            powerball_match = pred_powerball == winning_powerball

            # Calculate prize using official calculator
            prize_amount, prize_description = calculate_prize_amount(main_matches, powerball_match)
            total_prizes += prize_amount

            # Only include if meets minimum match criteria
            total_matches = main_matches + (1 if powerball_match else 0)
            if total_matches >= min_matches:
                formatted_pred = {
                    "id": pred[0],
                    "numbers": pred_numbers,
                    "powerball": pred_powerball,
                    "matches_main": main_matches,
                    "matches_powerball": powerball_match,
                    "total_matches": total_matches,
                    "prize_amount": prize_amount,
                    "prize_description": prize_description,
                    "score": pred[8] or 0,  # score_total
                    "method": pred[9] or "unknown",  # model_version
                    "created_at": pred[11] or pred[1],  # created_at or timestamp
                    "rank": len(formatted_predictions) + 1
                }
                formatted_predictions.append(formatted_pred)

        # Limit final results
        formatted_predictions = formatted_predictions[:limit]

        logger.info(f"Returning {len(formatted_predictions)} predictions with matches >= {min_matches}")

        return {
            "draw_date": target_date_str,
            "requested_date": draw_date,
            "draw_info": {
                "actual_draw_date": target_date_str,
                "winning_numbers": winning_numbers,
                "winning_powerball": winning_powerball,
                "jackpot_amount": draw_dict.get('jackpot', 'Not available')
            },
            "winning_numbers": {
                "main_numbers": winning_numbers,
                "powerball": winning_powerball
            },
            "predictions": formatted_predictions,
            "total_predictions": len(formatted_predictions),
            "total_prizes": total_prizes,
            "summary": {
                "total_predictions_with_matches": len(formatted_predictions),
                "predictions_with_prizes": len([p for p in formatted_predictions if p['prize_amount'] > 0]),
                "total_prize_won": total_prizes,
                "best_match": max([p['matches_main'] for p in formatted_predictions], default=0)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting predictions by draw date: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Add public endpoint for frontend access
@prediction_router.get("/public/by-draw/{draw_date}")
async def get_public_predictions_by_draw_date(
    draw_date: str,
    min_matches: int = Query(0, ge=0, description="Minimum number of matches required"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of predictions to return")
):
    """Public endpoint for getting predictions by draw date (frontend access)"""
    return await get_predictions_by_draw_date(draw_date, min_matches, limit)

# Add new endpoint for predictions without requiring official results
@prediction_router.get("/public/predictions-only/{draw_date}")
async def get_predictions_only_by_date(
    draw_date: str,
    limit: int = Query(100, ge=1, le=500, description="Maximum number of predictions to return")
):
    """Get predictions for a specific date without requiring official draw results"""
    try:
        logger.info(f"Getting predictions only for date: {draw_date}, limit: {limit}")

        # Parse and validate the date
        try:
            if len(draw_date) == 10 and '-' in draw_date:
                target_date = datetime.strptime(draw_date, '%Y-%m-%d').date()
            else:
                for fmt in ['%Y%m%d', '%m/%d/%Y', '%m-%d-%Y']:
                    try:
                        target_date = datetime.strptime(draw_date, fmt).date()
                        break
                    except ValueError:
                        continue
                else:
                    raise ValueError("Invalid date format")
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {draw_date}. Use YYYY-MM-DD")

        target_date_str = target_date.strftime('%Y-%m-%d')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get predictions for this date (no need for official results)
        cursor.execute("""
            SELECT 
                id,
                created_at,
                n1, n2, n3, n4, n5, powerball,
                confidence_score,
                strategy_used,
                draw_date,
                created_at
            FROM generated_tickets 
            WHERE draw_date = ?
            ORDER BY confidence_score DESC
            LIMIT ?
        """, (target_date_str, limit))

        predictions_raw = cursor.fetchall()
        conn.close()

        if not predictions_raw:
            return {
                "draw_date": target_date_str,
                "requested_date": draw_date,
                "predictions": [],
                "total_predictions": 0,
                "message": f"No predictions found for date {target_date_str}"
            }

        # Format predictions without match analysis (since we don't have official results)
        formatted_predictions = []
        for i, pred in enumerate(predictions_raw):
            pred_numbers = [pred[2], pred[3], pred[4], pred[5], pred[6]]  # n1-n5
            pred_powerball = pred[7]  # powerball

            formatted_pred = {
                "id": pred[0],
                "numbers": pred_numbers,
                "powerball": pred_powerball,
                "score": pred[8] or 0,  # confidence_score
                "method": pred[9] or "unknown",  # strategy_used
                "created_at": pred[11] or pred[1],  # created_at or created_at
                "rank": i + 1,
                "target_draw_date": pred[10]  # draw_date (aliased for API compatibility)
            }
            formatted_predictions.append(formatted_pred)

        logger.info(f"Returning {len(formatted_predictions)} predictions for date {target_date_str}")

        return {
            "draw_date": target_date_str,
            "requested_date": draw_date,
            "predictions": formatted_predictions,
            "total_predictions": len(formatted_predictions),
            "message": f"Found {len(formatted_predictions)} predictions for {target_date_str}",
            "note": "Predictions shown without match analysis (official results not available)"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting predictions only: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Routers are included in main app (src/api.py)


# --- Phase 5: Multi-strategy API endpoints ---
@prediction_router.post("/generate-multi-strategy", response_model=Dict[str, Any])
async def generate_tickets_multi_strategy(count: int = Query(5, ge=1, le=100)):
    """
    Generate tickets using the multi-strategy system with adaptive weights.
    
    Args:
        count: Number of tickets to generate (1-100, default 5)
    
    Returns:
        Dict with tickets, metadata, and strategy distribution
    """
    try:
        from src.strategy_generators import StrategyManager

        logger.info(f"Generating {count} tickets using multi-strategy system")

        manager = StrategyManager()
        tickets = manager.generate_balanced_tickets(count)

        # Calculate metadata
        all_numbers = set()
        all_powerballs = set()
        strategy_dist = {}

        for ticket in tickets:
            all_numbers.update(ticket['white_balls'])
            all_powerballs.add(ticket['powerball'])

            strategy = ticket['strategy']
            strategy_dist[strategy] = strategy_dist.get(strategy, 0) + 1

        coverage_pct = len(all_numbers) / 69 * 100

        # Get current strategy weights
        weights = manager.get_strategy_weights()

        response = {
            "success": True,
            "tickets": tickets,
            "metadata": {
                "total_tickets": len(tickets),
                "total_coverage": len(all_numbers),
                "coverage_percentage": round(coverage_pct, 2),
                "unique_powerballs": len(all_powerballs),
                "strategy_distribution": strategy_dist,
                "current_weights": {k: round(v, 4) for k, v in weights.items()}
            },
            "explanation": {
                "coverage": f"These {count} tickets cover {len(all_numbers)} unique white ball numbers ({coverage_pct:.1f}% of all possible numbers)",
                "powerballs": f"Using {len(all_powerballs)} different Powerball numbers for diversification",
                "strategies": f"Tickets generated using {len(strategy_dist)} different strategies based on adaptive weights"
            }
        }

        logger.info(f"✅ Generated {count} tickets successfully")
        return response

    except Exception as e:
        logger.error(f"Error generating multi-strategy tickets: {e}")
        logger.exception("Full traceback:")
        raise HTTPException(status_code=500, detail=f"Ticket generation failed: {str(e)}")


@prediction_router.get("/strategy-performance", response_model=Dict[str, Any])
async def get_strategy_performance():
    """
    Get performance metrics for all strategies.
    
    Returns:
        Dict with performance data for each strategy
    """
    try:
        from src.strategy_generators import StrategyManager

        manager = StrategyManager()
        summary = manager.get_strategy_summary()

        # Sort by ROI
        sorted_strategies = sorted(
            summary.items(),
            key=lambda x: x[1].get('roi', 0),
            reverse=True
        )

        return {
            "success": True,
            "strategies": dict(sorted_strategies),
            "total_strategies": len(summary),
            "best_strategy": sorted_strategies[0][0] if sorted_strategies else None,
            "explanation": "Strategies ranked by ROI (Return on Investment). Higher is better."
        }

    except Exception as e:
        logger.error(f"Error fetching strategy performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))
