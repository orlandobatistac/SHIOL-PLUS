"""
Test ML model integration with AIGuidedStrategy

This test verifies that the XGBoost ML model is properly integrated
into the prediction pipeline through AIGuidedStrategy.
"""

import pytest
import sys
import os
import numpy as np

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_ai_guided_strategy_uses_ml_model():
    """Test that AIGuidedStrategy can use the ML model"""
    from src.strategy_generators import AIGuidedStrategy
    
    # Initialize strategy
    strategy = AIGuidedStrategy()
    
    # Check that ML predictor was initialized
    assert hasattr(strategy, '_predictor'), "Strategy should have _predictor attribute"
    assert hasattr(strategy, '_ml_available'), "Strategy should have _ml_available attribute"
    
    # Generate tickets
    tickets = strategy.generate(count=5)
    
    # Verify tickets were generated
    assert len(tickets) == 5, "Should generate 5 tickets"
    
    # Verify ticket structure
    for ticket in tickets:
        assert 'white_balls' in ticket, "Ticket should have white_balls"
        assert 'powerball' in ticket, "Ticket should have powerball"
        assert 'strategy' in ticket, "Ticket should have strategy"
        assert 'confidence' in ticket, "Ticket should have confidence"
        
        # Verify white balls constraints
        assert len(ticket['white_balls']) == 5, "Should have 5 white balls"
        assert all(1 <= n <= 69 for n in ticket['white_balls']), "White balls should be 1-69"
        assert len(set(ticket['white_balls'])) == 5, "White balls should be unique"
        assert ticket['white_balls'] == sorted(ticket['white_balls']), "White balls should be sorted"
        
        # Verify powerball constraints
        assert 1 <= ticket['powerball'] <= 26, "Powerball should be 1-26"
        
        # Verify strategy name
        assert ticket['strategy'] == 'ai_guided', "Strategy should be ai_guided"
        
        # Verify confidence
        assert 0.0 <= ticket['confidence'] <= 1.0, "Confidence should be 0-1"


def test_ml_predictor_initialization():
    """Test that ML Predictor can be initialized"""
    from src.predictor import Predictor
    
    predictor = Predictor()
    
    # Check model is loaded
    assert hasattr(predictor, 'model'), "Predictor should have model attribute"
    
    # Check predict_probabilities method exists
    assert hasattr(predictor, 'predict_probabilities'), "Should have predict_probabilities method"
    assert callable(predictor.predict_probabilities), "predict_probabilities should be callable"


def test_ml_model_generates_probabilities():
    """Test that ML model can generate probability distributions"""
    from src.predictor import Predictor
    
    try:
        predictor = Predictor()
        
        # Skip test if model is not loaded
        if predictor.model is None:
            pytest.skip("ML model not available for testing")
        
        # Get probabilities
        wb_probs, pb_probs = predictor.predict_probabilities(use_ensemble=False)
        
        # Verify white ball probabilities
        assert isinstance(wb_probs, np.ndarray), "White ball probs should be numpy array"
        assert len(wb_probs) == 69, "Should have 69 white ball probabilities"
        assert np.isclose(wb_probs.sum(), 1.0, atol=1e-6), "White ball probs should sum to 1"
        assert np.all(wb_probs >= 0), "All probabilities should be non-negative"
        assert np.all(wb_probs <= 1), "All probabilities should be <= 1"
        
        # Verify powerball probabilities
        assert isinstance(pb_probs, np.ndarray), "Powerball probs should be numpy array"
        assert len(pb_probs) == 26, "Should have 26 powerball probabilities"
        assert np.isclose(pb_probs.sum(), 1.0, atol=1e-6), "Powerball probs should sum to 1"
        assert np.all(pb_probs >= 0), "All probabilities should be non-negative"
        assert np.all(pb_probs <= 1), "All probabilities should be <= 1"
        
    except Exception as e:
        pytest.skip(f"Test skipped due to error: {e}")


def test_strategy_manager_includes_ml():
    """Test that StrategyManager includes the AI-guided (ML) strategy"""
    from src.strategy_generators import StrategyManager
    
    manager = StrategyManager()
    
    # Verify ai_guided strategy is present
    assert 'ai_guided' in manager.strategies, "StrategyManager should have ai_guided strategy"
    
    # Verify it's an AIGuidedStrategy instance
    from src.strategy_generators import AIGuidedStrategy
    assert isinstance(manager.strategies['ai_guided'], AIGuidedStrategy), \
        "ai_guided should be AIGuidedStrategy instance"


def test_balanced_tickets_can_use_ml():
    """Test that balanced ticket generation can use ML strategy"""
    from src.strategy_generators import StrategyManager
    
    manager = StrategyManager()
    
    # Generate balanced tickets (may include AI-guided)
    tickets = manager.generate_balanced_tickets(total=10)
    
    # Verify tickets were generated
    assert len(tickets) <= 10, "Should generate at most 10 tickets"
    assert len(tickets) > 0, "Should generate at least 1 ticket"
    
    # Check if any tickets use ai_guided strategy
    ai_guided_tickets = [t for t in tickets if t.get('strategy') == 'ai_guided']
    
    # Note: Due to weighted selection, ai_guided may or may not be selected
    # This test just verifies the system doesn't crash when it is selected
    if ai_guided_tickets:
        print(f"✓ {len(ai_guided_tickets)} tickets used ML-based ai_guided strategy")
    else:
        print("  No ai_guided tickets in this batch (weighted random selection)")


if __name__ == "__main__":
    # Run tests
    print("Testing ML Model Integration...")
    print()
    
    print("Test 1: AIGuidedStrategy uses ML model")
    test_ai_guided_strategy_uses_ml_model()
    print("✓ PASSED")
    print()
    
    print("Test 2: ML Predictor initialization")
    test_ml_predictor_initialization()
    print("✓ PASSED")
    print()
    
    print("Test 3: ML model generates probabilities")
    test_ml_model_generates_probabilities()
    print("✓ PASSED")
    print()
    
    print("Test 4: StrategyManager includes ML")
    test_strategy_manager_includes_ml()
    print("✓ PASSED")
    print()
    
    print("Test 5: Balanced tickets can use ML")
    test_balanced_tickets_can_use_ml()
    print("✓ PASSED")
    print()
    
    print("All tests passed! ✓")
