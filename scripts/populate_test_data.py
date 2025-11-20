#!/usr/bin/env python3
"""
Script to populate test database with sample predictions for testing PHASE 3 endpoints
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.database import get_db_connection
from datetime import datetime, timedelta
import random

def populate_test_data():
    """Add sample predictions to database for testing"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # First, ensure strategy_performance table has our strategies
    strategies = [
        'frequency_weighted',
        'cooccurrence',
        'ai_guided',
        'range_balanced',
        'random_baseline',
        'coverage_optimizer',
        'xgboost_ml',
        'random_forest_ml',
        'lstm_neural',
        'hybrid_ensemble',
        'intelligent_scoring'
    ]
    
    print("Initializing strategies in strategy_performance table...")
    for i, strategy in enumerate(strategies):
        cursor.execute("""
            INSERT OR REPLACE INTO strategy_performance 
            (strategy_name, current_weight, confidence, total_plays, total_wins, win_rate, roi, avg_prize, total_prizes, total_cost)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            strategy,
            0.091,  # 1/11 weight
            0.5 + (i * 0.03),  # Varying confidence
            random.randint(50, 200),  # total_plays
            random.randint(5, 30),  # total_wins
            random.uniform(0.05, 0.25),  # win_rate
            random.uniform(-0.5, 2.0),  # roi
            random.uniform(0, 50),  # avg_prize
            random.uniform(0, 500),  # total_prizes
            random.uniform(100, 400)  # total_cost
        ))
    
    conn.commit()
    print(f"✓ Initialized {len(strategies)} strategies")
    
    # Add sample predictions
    print("\nAdding sample predictions...")
    
    next_draw_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Generate 500 tickets (matching roadmap specification)
    tickets_per_strategy = 45  # Approximately 500/11
    total_tickets = 0
    
    for strategy in strategies:
        # Vary ticket count slightly per strategy
        count = tickets_per_strategy + random.randint(-5, 5)
        
        for _ in range(count):
            # Generate valid white balls (1-69, sorted, unique)
            white_balls = sorted(random.sample(range(1, 70), 5))
            
            # Generate powerball (1-26)
            powerball = random.randint(1, 26)
            
            # Generate confidence score with strategy-specific bias
            base_confidence = 0.5
            if strategy == 'xgboost_ml':
                confidence = random.uniform(0.7, 0.9)
            elif strategy == 'random_baseline':
                confidence = random.uniform(0.3, 0.5)
            else:
                confidence = random.uniform(0.4, 0.8)
            
            cursor.execute("""
                INSERT INTO generated_tickets 
                (draw_date, strategy_used, n1, n2, n3, n4, n5, powerball, confidence_score, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                next_draw_date,
                strategy,
                white_balls[0], white_balls[1], white_balls[2], white_balls[3], white_balls[4],
                powerball,
                confidence,
                datetime.now().isoformat()
            ))
            
            total_tickets += 1
    
    conn.commit()
    print(f"✓ Added {total_tickets} predictions for draw date {next_draw_date}")
    
    # Display summary
    cursor.execute("""
        SELECT strategy_used, COUNT(*) as count, AVG(confidence_score) as avg_conf
        FROM generated_tickets
        GROUP BY strategy_used
        ORDER BY count DESC
    """)
    
    print("\nPrediction Distribution:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} tickets (avg confidence: {row[2]:.3f})")
    
    conn.close()
    print("\n✅ Test data populated successfully!")

if __name__ == "__main__":
    populate_test_data()
