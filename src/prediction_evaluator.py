"""
SHIOL+ Prediction Evaluator
===========================

Module for evaluating predictions against actual drawing results.
This module is called as part of the pipeline to automatically 
evaluate predictions from previous drawings.
"""

from typing import Dict
from loguru import logger
import traceback

from src.database import get_db_connection
from src.prize_calculator import calculate_prize_amount


class PredictionEvaluator:
    """Evaluates predictions against actual drawing results."""

    def __init__(self):
        """Initialize the evaluator."""
        self.evaluated_count = 0
        self.total_prize_awarded = 0.0

    def evaluate_recent_predictions(self, days_back: int = 7) -> Dict:
        """
        Evaluate predictions from recent days against actual results.

        Args:
            days_back: Number of days to look back for unevaluated predictions

        Returns:
            Dict with evaluation results summary
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Select draw dates that have generated tickets which appear unevaluated.
                # Here we treat tickets with prize_won NULL or 0 as not yet evaluated.
                if days_back is None:
                    query = """
                        SELECT DISTINCT gt.draw_date as eval_date
                        FROM generated_tickets gt
                        INNER JOIN powerball_draws pd ON gt.draw_date = pd.draw_date
                        WHERE (gt.prize_won IS NULL OR gt.prize_won = 0)
                        ORDER BY eval_date ASC
                    """
                    cursor.execute(query)
                else:
                    query = """
                        SELECT DISTINCT gt.draw_date as eval_date
                        FROM generated_tickets gt
                        INNER JOIN powerball_draws pd ON gt.draw_date = pd.draw_date
                        WHERE (gt.prize_won IS NULL OR gt.prize_won = 0)
                        AND gt.draw_date >= date('now', '-' || ? || ' days')
                        ORDER BY eval_date ASC
                    """
                    cursor.execute(query, (days_back,))

                dates_to_evaluate = [row[0] for row in cursor.fetchall()]

                evaluation_results = {
                    'dates_evaluated': [],
                    'total_predictions_evaluated': 0,
                    'total_prize_amount': 0.0,
                    'predictions_with_prizes': 0,
                    'evaluation_summary': []
                }

                for draw_date in dates_to_evaluate:
                    date_result = self.evaluate_predictions_for_date(draw_date)
                    evaluation_results['dates_evaluated'].append(draw_date)
                    evaluation_results['total_predictions_evaluated'] += date_result.get('predictions_evaluated', 0)
                    evaluation_results['total_prize_amount'] += date_result.get('total_prize', 0.0)
                    evaluation_results['predictions_with_prizes'] += date_result.get('predictions_with_prizes', 0)
                    evaluation_results['evaluation_summary'].append(date_result)

                logger.info(f"Evaluation completed: {evaluation_results['total_predictions_evaluated']} predictions evaluated, ${evaluation_results['total_prize_amount']:.2f} total prizes")
                return evaluation_results

        except Exception as e:
            logger.error(f"Error during prediction evaluation: {e}")
            return {'error': str(e)}

    def evaluate_predictions_for_date(self, draw_date: str) -> Dict:
        """
        Evaluate all predictions for a specific draw date.

        Args:
            draw_date: Date in YYYY-MM-DD format

        Returns:
            Dict with evaluation results for this date
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Get the actual drawing result
                cursor.execute("""
                    SELECT n1, n2, n3, n4, n5, pb FROM powerball_draws 
                    WHERE draw_date = ?
                """, (draw_date,))

                actual_result = cursor.fetchone()
                if not actual_result:
                    logger.warning(f"No actual drawing result found for {draw_date}")
                    return {'error': f'No drawing result for {draw_date}'}

                # Validate draw result data
                if any(x is None for x in actual_result[:5]) or actual_result[5] is None:
                    logger.error(f"Invalid draw result data for {draw_date}: {actual_result}")
                    return {'error': f'Invalid draw result data for {draw_date}'}

                winning_numbers = list(actual_result[:5])
                winning_powerball = actual_result[5]

                # Get ALL generated tickets for this date
                cursor.execute("""
                    SELECT id, n1, n2, n3, n4, n5, powerball, confidence_score
                    FROM generated_tickets
                    WHERE draw_date = ?
                """, (draw_date,))

                predictions = cursor.fetchall()

                date_summary = {
                    'draw_date': draw_date,
                    'winning_numbers': winning_numbers,
                    'winning_powerball': winning_powerball,
                    'predictions_evaluated': len(predictions),
                    'predictions_with_prizes': 0,
                    'total_prize': 0.0,
                    'best_prediction': None,
                    'evaluation_details': []
                }

                for prediction in predictions:
                    try:
                        pred_id, n1, n2, n3, n4, n5, powerball, already_evaluated = prediction

                        # Validate prediction data
                        if any(x is None for x in prediction[:6]) or powerball is None:
                            logger.warning(f"Skipping prediction {pred_id} due to invalid data")
                            continue

                        prediction_numbers = [n1, n2, n3, n4, n5]

                        # Calculate matches
                        matches_main = len(set(prediction_numbers) & set(winning_numbers))
                        matches_pb = powerball == winning_powerball

                        # Calculate prize
                        prize_amount, prize_description = calculate_prize_amount(matches_main, matches_pb)

                        # Update generated_tickets with prize info and mark as played
                        cursor.execute("""
                            UPDATE generated_tickets
                            SET prize_won = ?,
                                was_played = TRUE
                            WHERE id = ?
                        """, (prize_amount, pred_id))

                        # Update summary
                        if prize_amount > 0:
                            date_summary['predictions_with_prizes'] += 1
                            date_summary['total_prize'] += prize_amount

                            # Track best prediction
                            if not date_summary['best_prediction'] or prize_amount > date_summary['best_prediction']['prize_amount']:
                                date_summary['best_prediction'] = {
                                    'prediction_id': pred_id,
                                    'numbers': prediction_numbers,
                                    'powerball': powerball,
                                    'matches_main': matches_main,
                                    'matches_pb': matches_pb,
                                    'prize_amount': prize_amount,
                                    'prize_description': prize_description
                                }

                        date_summary['evaluation_details'].append({
                            'prediction_id': pred_id,
                            'matches_main': matches_main,
                            'matches_pb': matches_pb,
                            'prize_amount': prize_amount,
                            'prize_description': prize_description
                        })
                    except Exception as pred_error:
                        logger.error(f"Error processing prediction {pred_id if 'pred_id' in locals() else 'unknown'}: {pred_error}")
                        continue

                conn.commit()

                logger.info(f"Evaluated {len(predictions)} predictions for {draw_date}: {date_summary['predictions_with_prizes']} won prizes, total: ${date_summary['total_prize']:.2f}")
                return date_summary

        except Exception as e:
            logger.error(f"Error evaluating predictions for {draw_date}: {e}")
            return {'error': str(e)}

    def get_predictions_with_matches_for_draw(self, draw_date: str, min_matches: int = 0) -> Dict:
        """
        Get all predictions for a specific draw date and calculate matches against actual results.

        Args:
            draw_date: Draw date in YYYY-MM-DD format
            min_matches: Minimum number of matches required (0-5)

        Returns:
            Dictionary with predictions, winning numbers, and prize information
        """
        logger.info(f"Getting predictions with matches for draw: {draw_date}, min_matches: {min_matches}")

        try:
            conn = get_db_connection()
            if not conn:
                logger.error("Failed to get database connection")
                return None

            cursor = conn.cursor()

            # Get the actual draw results
            cursor.execute("""
                SELECT draw_date, n1, n2, n3, n4, n5, pb 
                FROM powerball_draws 
                WHERE draw_date = ?
            """, (draw_date,))

            draw_result = cursor.fetchone()
            if not draw_result:
                logger.warning(f"No draw result found for date: {draw_date}")
                conn.close()
                return None

            # Validate draw result data
            if any(x is None for x in draw_result[1:6]) or draw_result[6] is None:
                logger.error(f"Invalid draw result data for {draw_date}: {draw_result}")
                conn.close()
                return None

            actual_numbers = sorted([draw_result[1], draw_result[2], draw_result[3], draw_result[4], draw_result[5]])
            actual_pb = draw_result[6]

            logger.info(f"Actual numbers for {draw_date}: {actual_numbers} + PB: {actual_pb}")

            # Get all generated tickets for this draw date
            cursor.execute("""
                SELECT id, created_at as timestamp, n1, n2, n3, n4, n5, powerball, strategy_used as method, confidence_score
                FROM generated_tickets 
                WHERE draw_date = ?
                ORDER BY confidence_score DESC
            """, (draw_date,))

            predictions = cursor.fetchall()
            conn.close()

            if not predictions:
                logger.info(f"No predictions found for date: {draw_date}")
                # Return empty structure with winning numbers
                return {
                    "predictions": [],
                    "winning_numbers": {
                        "main_numbers": actual_numbers,
                        "powerball": actual_pb
                    },
                    "total_prizes": 0.0,
                    "draw_date": draw_date
                }

            logger.info(f"Found {len(predictions)} predictions for {draw_date}")

            matched_predictions = []
            total_prizes = 0.0

            for pred in predictions:
                try:
                    # Validate prediction data
                    if any(x is None for x in pred[2:7]) or pred[7] is None:
                        logger.warning(f"Skipping prediction {pred[0]} due to invalid data")
                        continue

                    prediction_numbers = sorted([pred[2], pred[3], pred[4], pred[5], pred[6]])
                    prediction_pb = pred[7]

                    # Calculate matches
                    main_matches = len(set(prediction_numbers) & set(actual_numbers))
                    pb_match = 1 if prediction_pb == actual_pb else 0

                    # Only include if meets minimum match criteria
                    if main_matches >= min_matches:
                        # Calculate prize
                        prize_amount, _ = calculate_prize_amount(main_matches, pb_match)
                        total_prizes += prize_amount

                        matched_predictions.append({
                            "id": pred[0],
                            "draw_date": draw_date,
                            "numbers_predicted": prediction_numbers,
                            "powerball_predicted": prediction_pb,
                            "method": pred[8] or "unknown",
                            "confidence_score": float(pred[9]) if pred[9] is not None else 0.0,
                            "matches": main_matches,
                            "powerball_match": bool(pb_match),
                            "prize_amount": prize_amount,
                            "ticket_id": f"pred_{pred[0]}",
                            "timestamp": pred[1]
                        })
                except Exception as pred_error:
                    logger.error(f"Error processing prediction {pred[0] if pred else 'unknown'}: {pred_error}")
                    continue

            logger.info(f"Found {len(matched_predictions)} predictions with {min_matches}+ matches")

            return {
                "predictions": matched_predictions,
                "winning_numbers": {
                    "main_numbers": actual_numbers,
                    "powerball": actual_pb
                },
                "total_prizes": total_prizes,
                "draw_date": draw_date
            }

        except Exception as e:
            logger.error(f"Error getting predictions with matches for {draw_date}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def get_evaluation_statistics(self, days_back: int = 30) -> Dict:
        """
        Get evaluation statistics for the specified period.

        Args:
            days_back: Number of days to analyze

        Returns:
            Dict with evaluation statistics
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Get overall statistics from generated_tickets
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_evaluated,
                        COUNT(CASE WHEN prize_won > 0 THEN 1 END) as winning_predictions,
                        COALESCE(SUM(COALESCE(prize_won, 0)), 0) as total_prizes,
                        AVG(NULL) as avg_main_matches,
                        MAX(prize_won) as best_prize
                    FROM generated_tickets
                    WHERE (prize_won IS NOT NULL AND prize_won != 0)
                    AND created_at >= datetime('now', '-' || ? || ' days')
                """, (days_back,))

                overall_stats = cursor.fetchone()

                # Handle case where no evaluated predictions are found
                if not overall_stats:
                    return {
                        'period_days': days_back,
                        'total_evaluated': 0,
                        'winning_predictions': 0,
                        'total_prizes': 0.0,
                        'win_rate_percentage': 0.0,
                        'avg_main_matches': 0.0,
                        'best_prize': 0.0,
                        'prize_distribution': []
                    }


                # Get prize distribution
                # Prize distribution from generated_tickets (by numeric bins)
                cursor.execute("""
                    SELECT CASE 
                        WHEN prize_won >= 1000000 THEN '>=1M'
                        WHEN prize_won >= 1000 THEN '>=1K'
                        WHEN prize_won > 0 THEN '<1K'
                        ELSE 'none' END as tier,
                    COUNT(*) as count,
                    COALESCE(SUM(COALESCE(prize_won, 0)), 0) as total
                    FROM generated_tickets
                    WHERE (prize_won IS NOT NULL AND prize_won != 0)
                    AND created_at >= datetime('now', '-' || ? || ' days')
                    GROUP BY tier
                    ORDER BY total DESC
                """, (days_back,))

                prize_distribution = cursor.fetchall()

                stats = {
                    'period_days': days_back,
                    'total_evaluated': overall_stats[0] or 0,
                    'winning_predictions': overall_stats[1] or 0,
                    'total_prizes': overall_stats[2] or 0.0,
                    'win_rate_percentage': round((overall_stats[1] / overall_stats[0] * 100) if overall_stats[0] > 0 else 0, 1),
                    'avg_main_matches': round(overall_stats[3] or 0, 1),
                    'best_prize': overall_stats[4] or 0.0,
                    'prize_distribution': [
                        {
                            'description': row[0],
                            'count': row[1],
                            'total_amount': row[2]
                        } for row in prize_distribution
                    ]
                }

                return stats

        except Exception as e:
            logger.error(f"Error getting evaluation statistics: {e}")
            return {'error': str(e)}
