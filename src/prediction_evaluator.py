
"""
SHIOL+ Prediction Evaluator
===========================

Module for evaluating predictions against actual drawing results.
This module is called as part of the pipeline to automatically 
evaluate predictions from previous drawings.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from loguru import logger

from src.database import get_db_connection, calculate_prize_amount


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
                
                # Find predictions that need evaluation (have target_draw_date with actual results)
                query = """
                    SELECT DISTINCT pl.target_draw_date
                    FROM predictions_log pl
                    INNER JOIN powerball_draws pd ON pl.target_draw_date = pd.draw_date
                    WHERE pl.evaluated = FALSE
                    AND pl.target_draw_date >= date('now', '-' || ? || ' days')
                    ORDER BY pl.target_draw_date ASC
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
                    evaluation_results['total_predictions_evaluated'] += date_result['predictions_evaluated']
                    evaluation_results['total_prize_amount'] += date_result['total_prize']
                    evaluation_results['predictions_with_prizes'] += date_result['predictions_with_prizes']
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
                
                winning_numbers = list(actual_result[:5])
                winning_powerball = actual_result[5]
                
                # Get all unevaluated predictions for this date
                cursor.execute("""
                    SELECT id, n1, n2, n3, n4, n5, powerball
                    FROM predictions_log
                    WHERE target_draw_date = ? AND evaluated = FALSE
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
                    pred_id, n1, n2, n3, n4, n5, powerball = prediction
                    prediction_numbers = [n1, n2, n3, n4, n5]
                    
                    # Calculate matches
                    matches_main = len(set(prediction_numbers) & set(winning_numbers))
                    matches_pb = powerball == winning_powerball
                    
                    # Calculate prize
                    prize_amount, prize_description = calculate_prize_amount(matches_main, matches_pb)
                    
                    # Update prediction with evaluation results
                    cursor.execute("""
                        UPDATE predictions_log
                        SET evaluated = TRUE,
                            matches_wb = ?,
                            matches_pb = ?,
                            prize_amount = ?,
                            prize_description = ?,
                            evaluation_date = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (matches_main, matches_pb, prize_amount, prize_description, pred_id))
                    
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
                
                conn.commit()
                
                logger.info(f"Evaluated {len(predictions)} predictions for {draw_date}: {date_summary['predictions_with_prizes']} won prizes, total: ${date_summary['total_prize']:.2f}")
                return date_summary
                
        except Exception as e:
            logger.error(f"Error evaluating predictions for {draw_date}: {e}")
            return {'error': str(e)}
    
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
                
                # Get overall statistics
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_evaluated,
                        COUNT(CASE WHEN prize_amount > 0 THEN 1 END) as winning_predictions,
                        SUM(prize_amount) as total_prizes,
                        AVG(matches_wb) as avg_main_matches,
                        MAX(prize_amount) as best_prize
                    FROM predictions_log
                    WHERE evaluated = TRUE
                    AND evaluation_date >= datetime('now', '-' || ? || ' days')
                """, (days_back,))
                
                overall_stats = cursor.fetchone()
                
                # Get prize distribution
                cursor.execute("""
                    SELECT prize_description, COUNT(*) as count, SUM(prize_amount) as total
                    FROM predictions_log
                    WHERE evaluated = TRUE
                    AND evaluation_date >= datetime('now', '-' || ? || ' days')
                    AND prize_amount > 0
                    GROUP BY prize_description
                    ORDER BY prize_amount DESC
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


def run_prediction_evaluation() -> Dict:
    """
    Main function to run prediction evaluation.
    Called by the pipeline after data update step.
    
    Returns:
        Dict with evaluation results
    """
    logger.info("Starting prediction evaluation process...")
    
    evaluator = PredictionEvaluator()
    results = evaluator.evaluate_recent_predictions(days_back=7)
    
    if 'error' not in results:
        logger.info(f"Prediction evaluation completed successfully: {results['total_predictions_evaluated']} predictions evaluated")
    else:
        logger.error(f"Prediction evaluation failed: {results['error']}")
    
    return results


if __name__ == "__main__":
    # For testing
    results = run_prediction_evaluation()
    print("Evaluation Results:", results)
