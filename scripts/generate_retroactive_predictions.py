#!/usr/bin/env python3
"""
Generate retroactive predictions for a past draw date.
This simulates what predictions would have been made BEFORE the draw occurred.

Usage:
    python scripts/generate_retroactive_predictions.py 2025-12-01 --count 10
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from src.strategy_generators import StrategyManager
from src.database import get_db_connection


def generate_retroactive_predictions(draw_date: str, count_per_strategy: int = 10):
    """
    Generate predictions for a past draw date.
    
    Args:
        draw_date: The draw date to generate predictions for (YYYY-MM-DD)
        count_per_strategy: Number of tickets per strategy
    """
    logger.info(f"Generating retroactive predictions for {draw_date}")
    logger.info(f"Tickets per strategy: {count_per_strategy}")
    
    # Initialize StrategyManager with max_date to exclude the target draw
    # This ensures we don't "cheat" by using data from after the draw
    manager = StrategyManager(max_date=draw_date)
    
    # Generate tickets using the new method
    tickets = manager.generate_tickets_per_strategy(count_per_strategy=count_per_strategy)
    
    # Add draw_date to all tickets
    for ticket in tickets:
        ticket['draw_date'] = draw_date
    
    # Save to database
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # First, clear any existing predictions for this date
        cursor.execute("DELETE FROM generated_tickets WHERE draw_date = ?", (draw_date,))
        deleted = cursor.rowcount
        if deleted > 0:
            logger.info(f"Deleted {deleted} existing predictions for {draw_date}")
        
        # Insert new predictions
        for ticket in tickets:
            cursor.execute("""
                INSERT INTO generated_tickets 
                (draw_date, n1, n2, n3, n4, n5, powerball, strategy, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                ticket['draw_date'],
                ticket['white_balls'][0],
                ticket['white_balls'][1],
                ticket['white_balls'][2],
                ticket['white_balls'][3],
                ticket['white_balls'][4],
                ticket['powerball'],
                ticket['strategy'],
                ticket.get('confidence', 0.5)
            ))
        
        conn.commit()
        logger.info(f"✅ Saved {len(tickets)} retroactive predictions for {draw_date}")
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"RETROACTIVE PREDICTIONS FOR {draw_date}")
    print(f"{'='*60}")
    
    strategy_counts = {}
    for ticket in tickets:
        strategy = ticket['strategy']
        strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
    
    for strategy, count in sorted(strategy_counts.items()):
        print(f"  {strategy}: {count} tickets")
    
    print(f"{'='*60}")
    print(f"TOTAL: {len(tickets)} tickets")
    print(f"{'='*60}")
    
    return tickets


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate retroactive predictions for a past draw")
    parser.add_argument("draw_date", help="Draw date (YYYY-MM-DD)")
    parser.add_argument("--count", type=int, default=10, help="Tickets per strategy (default: 10)")
    
    args = parser.parse_args()
    
    generate_retroactive_predictions(args.draw_date, args.count)
