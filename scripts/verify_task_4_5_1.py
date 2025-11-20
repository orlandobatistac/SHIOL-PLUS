
import sys
import os
import pandas as pd
import numpy as np
from loguru import logger

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.analytics_engine import (
    get_analytics_overview, 
    compute_gap_analysis, 
    compute_temporal_frequencies, 
    compute_momentum_scores
)
from src.ticket_scorer import TicketScorer
from src.strategy_generators import CustomInteractiveGenerator
from src.database import get_all_draws

def test_analytics_engine():
    logger.info("Testing Analytics Engine...")
    
    # 1. Test get_analytics_overview
    overview = get_analytics_overview()
    
    if 'error' in overview:
        logger.error(f"Analytics overview returned error: {overview['error']}")
        return False
        
    logger.info("Analytics overview keys: " + str(overview.keys()))
    
    # Validate structure
    assert 'gap_analysis' in overview
    assert 'temporal_frequencies' in overview
    assert 'momentum_scores' in overview
    assert 'pattern_statistics' in overview
    
    # Validate content types
    gaps = overview['gap_analysis']
    assert 'white_balls' in gaps
    assert 'powerball' in gaps
    
    logger.info(f"Gap analysis sample (WB 1): {gaps['white_balls'].get(1)}")
    
    return overview

def test_ticket_scorer(context):
    logger.info("Testing Ticket Scorer...")
    
    scorer = TicketScorer()
    
    # Test valid ticket
    ticket = [1, 10, 20, 30, 40]
    pb = 15
    
    score = scorer.score_ticket(ticket, pb, context)
    
    logger.info(f"Ticket Score: {score['total_score']}")
    logger.info(f"Recommendation: {score['recommendation']}")
    
    assert 0 <= score['total_score'] <= 100
    assert 'details' in score
    assert 'diversity' in score['details']
    
    # Test invalid ticket
    invalid_score = scorer.score_ticket([1, 1, 2, 3, 4], 15, context) # Duplicate
    assert invalid_score['total_score'] == 0
    assert "Error" in invalid_score['recommendation']
    
    return True

def test_interactive_generator(context):
    logger.info("Testing Interactive Generator...")
    
    generator = CustomInteractiveGenerator()
    
    # Test Hot/High Risk
    params_hot = {'temperature': 'hot', 'risk': 'high', 'exclude': []}
    tickets_hot = generator.generate_custom(params_hot, context)
    
    logger.info(f"Generated {len(tickets_hot)} tickets (Hot/High Risk)")
    if tickets_hot:
        logger.info(f"Sample ticket: {tickets_hot[0]}")
        
    # Test Cold/Low Risk
    params_cold = {'temperature': 'cold', 'risk': 'low', 'exclude': [1, 2, 3]}
    tickets_cold = generator.generate_custom(params_cold, context)
    
    logger.info(f"Generated {len(tickets_cold)} tickets (Cold/Low Risk)")
    
    # Validate exclusion
    for t in tickets_cold:
        for num in [1, 2, 3]:
            assert num not in t['white_balls'], f"Excluded number {num} found in ticket"
            
    return True

if __name__ == "__main__":
    try:
        # Get context first
        context = test_analytics_engine()
        if context:
            test_ticket_scorer(context)
            test_interactive_generator(context)
            logger.success("All tests passed successfully!")
        else:
            logger.error("Failed to get context, skipping dependent tests")
    except Exception as e:
        logger.exception(f"Test failed with exception: {e}")
        sys.exit(1)
