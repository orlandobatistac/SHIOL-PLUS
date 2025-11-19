"""
Test Random Forest Model Optimization
======================================
Tests for the optimized Random Forest feature engineering to ensure:
1. Feature generation completes in reasonable time
2. Tickets are generated successfully
3. No hangs or timeouts occur
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_feature_engineering_performance():
    """
    Test that feature engineering completes in reasonable time with realistic data.
    
    This test creates ~1850 synthetic draws (similar to production) and ensures
    feature engineering completes in under 10 seconds (vs 30+ seconds before).
    """
    from src.ml_models.random_forest_model import RandomForestModel
    
    # Create synthetic historical data (similar to production size)
    n_draws = 1850
    dates = [datetime.now() - timedelta(days=i*3) for i in range(n_draws)]
    
    draws_data = {
        'draw_date': dates,
        'n1': np.random.randint(1, 15, n_draws),
        'n2': np.random.randint(15, 30, n_draws),
        'n3': np.random.randint(30, 45, n_draws),
        'n4': np.random.randint(45, 60, n_draws),
        'n5': np.random.randint(60, 70, n_draws),
        'pb': np.random.randint(1, 27, n_draws),
    }
    
    draws_df = pd.DataFrame(draws_data)
    
    # Initialize model without pretrained models
    model = RandomForestModel(use_pretrained=False)
    
    # Time feature engineering
    start_time = time.time()
    features = model._engineer_features(draws_df)
    elapsed = time.time() - start_time
    
    # Assertions
    assert features is not None, "Features should not be None"
    assert len(features) == len(draws_df), "Features length should match draws"
    assert len(features.columns) > 0, "Should have at least some features"
    assert elapsed < 10.0, f"Feature engineering took {elapsed:.2f}s, should be < 10s"
    
    print(f"✓ Feature engineering completed in {elapsed:.2f}s with {len(features.columns)} features")


def test_feature_count_reduction():
    """
    Test that optimized feature engineering produces fewer features than original.
    
    Original: ~354 features (207 white ball + 69 gap + 78 powerball)
    Optimized: ~60-80 features (aggregated statistics)
    """
    from src.ml_models.random_forest_model import RandomForestModel
    
    # Small sample data
    n_draws = 100
    dates = [datetime.now() - timedelta(days=i*3) for i in range(n_draws)]
    
    draws_data = {
        'draw_date': dates,
        'n1': np.random.randint(1, 15, n_draws),
        'n2': np.random.randint(15, 30, n_draws),
        'n3': np.random.randint(30, 45, n_draws),
        'n4': np.random.randint(45, 60, n_draws),
        'n5': np.random.randint(60, 70, n_draws),
        'pb': np.random.randint(1, 27, n_draws),
    }
    
    draws_df = pd.DataFrame(draws_data)
    model = RandomForestModel(use_pretrained=False)
    
    features = model._engineer_features(draws_df)
    
    # Should have significantly fewer features than original (354)
    assert len(features.columns) < 100, (
        f"Should have < 100 features (aggregated), got {len(features.columns)}"
    )
    assert len(features.columns) > 30, (
        f"Should have > 30 features (enough signal), got {len(features.columns)}"
    )
    
    print(f"✓ Feature count reduced to {len(features.columns)} (optimal range: 30-100)")


def test_generate_tickets_timeout():
    """
    Test that ticket generation completes within timeout and doesn't hang.
    """
    from src.ml_models.random_forest_model import RandomForestModel
    
    # Create minimal sample data
    n_draws = 100
    dates = [datetime.now() - timedelta(days=i*3) for i in range(n_draws)]
    
    draws_data = {
        'draw_date': dates,
        'n1': np.random.randint(1, 15, n_draws),
        'n2': np.random.randint(15, 30, n_draws),
        'n3': np.random.randint(30, 45, n_draws),
        'n4': np.random.randint(45, 60, n_draws),
        'n5': np.random.randint(60, 70, n_draws),
        'pb': np.random.randint(1, 27, n_draws),
    }
    
    draws_df = pd.DataFrame(draws_data)
    
    # Initialize and train a simple model
    model = RandomForestModel(
        n_estimators=10,  # Reduced for fast testing
        max_depth=5,
        use_pretrained=False
    )
    
    # Train model
    model.train(draws_df, test_size=0.2)
    
    # Test ticket generation with timeout
    start_time = time.time()
    tickets = model.generate_tickets(draws_df, count=10, timeout=30)
    elapsed = time.time() - start_time
    
    # Assertions
    assert tickets is not None, "Tickets should not be None"
    assert len(tickets) == 10, f"Should generate 10 tickets, got {len(tickets)}"
    assert elapsed < 30.0, f"Generation took {elapsed:.2f}s, should be < 30s"
    
    # Verify ticket structure
    for ticket in tickets:
        assert 'white_balls' in ticket, "Ticket should have white_balls"
        assert 'powerball' in ticket, "Ticket should have powerball"
        assert 'strategy' in ticket, "Ticket should have strategy"
        assert len(ticket['white_balls']) == 5, "Should have 5 white balls"
        assert ticket['strategy'] == 'random_forest', "Strategy should be random_forest"
        
        # Verify number ranges
        for wb in ticket['white_balls']:
            assert 1 <= wb <= 69, f"White ball {wb} out of range"
        assert 1 <= ticket['powerball'] <= 26, f"Powerball {ticket['powerball']} out of range"
    
    print(f"✓ Generated {len(tickets)} tickets in {elapsed:.2f}s")


def test_no_nan_in_features():
    """
    Test that feature engineering doesn't produce NaN values.
    """
    from src.ml_models.random_forest_model import RandomForestModel
    
    # Create sample data with potential edge cases
    n_draws = 50
    dates = [datetime.now() - timedelta(days=i*3) for i in range(n_draws)]
    
    draws_data = {
        'draw_date': dates,
        'n1': np.random.randint(1, 15, n_draws),
        'n2': np.random.randint(15, 30, n_draws),
        'n3': np.random.randint(30, 45, n_draws),
        'n4': np.random.randint(45, 60, n_draws),
        'n5': np.random.randint(60, 70, n_draws),
        'pb': np.random.randint(1, 27, n_draws),
    }
    
    draws_df = pd.DataFrame(draws_data)
    model = RandomForestModel(use_pretrained=False)
    
    features = model._engineer_features(draws_df)
    
    # Check for NaN values
    nan_count = features.isna().sum().sum()
    assert nan_count == 0, f"Features should not contain NaN values, found {nan_count}"
    
    print(f"✓ No NaN values in {len(features.columns)} features")


if __name__ == "__main__":
    # Run tests manually
    print("Testing Random Forest Optimization...")
    print("\n1. Feature Engineering Performance Test")
    test_feature_engineering_performance()
    
    print("\n2. Feature Count Reduction Test")
    test_feature_count_reduction()
    
    print("\n3. No NaN Values Test")
    test_no_nan_in_features()
    
    print("\n4. Generate Tickets Timeout Test")
    test_generate_tickets_timeout()
    
    print("\n✓ All tests passed!")
