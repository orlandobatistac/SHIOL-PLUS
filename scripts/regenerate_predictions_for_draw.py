#!/usr/bin/env python3
"""
Regenerate predictions for a specific draw date.

This script performs a complete regeneration workflow:
1. Delete existing tickets for the specified draw date
2. Generate 500 new predictions using historical data before the draw
3. Evaluate predictions against official results

Usage:
    python scripts/regenerate_predictions_for_draw.py --draw-date 2025-11-23
    python scripts/regenerate_predictions_for_draw.py --draw-date 2025-11-23 --tickets 500
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import get_db_connection
from src.strategy_generators import StrategyManager
from src.prediction_evaluator import PredictionEvaluator
from loguru import logger
import argparse


def delete_existing_tickets(draw_date: str) -> int:
    """Delete all existing tickets for a draw date."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM generated_tickets WHERE draw_date = ?", (draw_date,))
        existing_count = cursor.fetchone()[0]
        
        if existing_count > 0:
            cursor.execute("DELETE FROM generated_tickets WHERE draw_date = ?", (draw_date,))
            conn.commit()
            logger.info(f"🗑️  Deleted {existing_count} existing tickets for {draw_date}")
        else:
            logger.info(f"No existing tickets found for {draw_date}")
        
        return existing_count


def verify_draw_exists(draw_date: str) -> bool:
    """Verify that official draw results exist for the date."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM powerball_draws WHERE draw_date = ?", (draw_date,))
        exists = cursor.fetchone()[0] > 0
        
        if not exists:
            logger.warning(f"⚠️  No official draw results found for {draw_date}")
            logger.warning(f"   Predictions will be generated but cannot be evaluated yet")
        
        return exists


def generate_predictions(draw_date: str, total_tickets: int = 500) -> int:
    """Generate predictions for a specific draw date."""
    logger.info(f"🎲 Generating {total_tickets} predictions for {draw_date}")
    
    manager = StrategyManager()
    tickets = manager.generate_balanced_tickets(total=total_tickets)
    
    logger.info(f"✅ Generated {len(tickets)} tickets by StrategyManager")
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        inserted = 0
        
        for ticket in tickets:
            try:
                cursor.execute("""
                    INSERT INTO generated_tickets (
                        draw_date, strategy_used, n1, n2, n3, n4, n5, powerball, confidence_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    draw_date,
                    ticket['strategy'],
                    ticket['white_balls'][0],
                    ticket['white_balls'][1],
                    ticket['white_balls'][2],
                    ticket['white_balls'][3],
                    ticket['white_balls'][4],
                    ticket['powerball'],
                    ticket.get('confidence', 0.5)
                ))
                inserted += 1
            except Exception as e:
                logger.error(f"Error inserting ticket: {e}")
                continue
        
        conn.commit()
    
    logger.success(f"✅ Inserted {inserted}/{len(tickets)} tickets for {draw_date}")
    return inserted


def evaluate_predictions(draw_date: str) -> dict:
    """Evaluate predictions against official results."""
    logger.info(f"📊 Evaluating predictions for {draw_date}")
    
    evaluator = PredictionEvaluator()
    result = evaluator.evaluate_predictions_for_date(draw_date)
    
    total_predictions = result.get('total_predictions', 0)
    total_wins = result.get('total_wins', 0)
    total_winnings = result.get('total_winnings', 0)
    
    logger.success(f"✅ Evaluation complete:")
    logger.info(f"   Total predictions: {total_predictions}")
    logger.info(f"   Total wins: {total_wins}")
    logger.info(f"   Total winnings: ${total_winnings:,.2f}")
    
    if 'wins_by_tier' in result:
        logger.info(f"   Wins by tier:")
        for tier, count in result['wins_by_tier'].items():
            logger.info(f"      {tier}: {count}")
    
    return result


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Regenerate predictions for a specific draw date'
    )
    parser.add_argument(
        '--draw-date',
        type=str,
        required=True,
        help='Draw date in YYYY-MM-DD format (e.g., 2025-11-23)'
    )
    parser.add_argument(
        '--tickets',
        type=int,
        default=500,
        help='Number of tickets to generate (default: 500)'
    )
    parser.add_argument(
        '--skip-evaluation',
        action='store_true',
        help='Skip evaluation step (useful if draw results not available yet)'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 70)
    logger.info("REGENERATE PREDICTIONS FOR DRAW")
    logger.info("=" * 70)
    logger.info(f"Draw date: {args.draw_date}")
    logger.info(f"Tickets to generate: {args.tickets}")
    logger.info("=" * 70)
    
    # Step 1: Delete existing tickets
    logger.info("\n[STEP 1/3] Deleting existing tickets...")
    deleted_count = delete_existing_tickets(args.draw_date)
    
    # Step 2: Generate new predictions
    logger.info("\n[STEP 2/3] Generating new predictions...")
    inserted_count = generate_predictions(args.draw_date, args.tickets)
    
    if inserted_count == 0:
        logger.error("❌ Failed to generate predictions")
        return 1
    
    # Step 3: Evaluate predictions (if draw exists and not skipped)
    if not args.skip_evaluation:
        logger.info("\n[STEP 3/3] Evaluating predictions...")
        draw_exists = verify_draw_exists(args.draw_date)
        
        if draw_exists:
            try:
                evaluate_predictions(args.draw_date)
            except Exception as e:
                logger.error(f"❌ Evaluation failed: {e}")
                return 1
        else:
            logger.warning("⏭️  Skipping evaluation (no official results yet)")
    else:
        logger.info("\n[STEP 3/3] Skipping evaluation (--skip-evaluation flag)")
    
    # Summary
    logger.success("\n" + "=" * 70)
    logger.success("WORKFLOW COMPLETED")
    logger.success("=" * 70)
    logger.success(f"Draw date: {args.draw_date}")
    logger.success(f"Deleted: {deleted_count} tickets")
    logger.success(f"Generated: {inserted_count} tickets")
    logger.success("=" * 70)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
