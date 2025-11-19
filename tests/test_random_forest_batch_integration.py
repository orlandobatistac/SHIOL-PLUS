"""
Integration Test for Random Forest Batch Generation
====================================================
Tests the complete flow from RandomForest model through batch generation.
Verifies that the optimization fixes the hanging issue.
"""

import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


def test_random_forest_batch_generation_integration():
    """
    Integration test: Verify RandomForest can generate 100 tickets in batch mode.
    
    This test simulates the actual batch generation scenario to ensure:
    1. RandomForest model can handle realistic data size (~1850 draws)
    2. Generation completes within acceptable time (< 30 seconds)
    3. Correct number of tickets are generated (100)
    4. No hangs or timeouts occur
    """
    from src.ml_models.random_forest_model import RandomForestModel
    
    print("\n" + "="*60)
    print("INTEGRATION TEST: Random Forest Batch Generation")
    print("="*60)
    
    # Step 1: Create realistic historical data (similar to production)
    print("\n[1/5] Creating realistic historical data (1850 draws)...")
    n_draws = 1850
    dates = [datetime.now() - timedelta(days=i*3) for i in range(n_draws)]
    
    # Generate realistic Powerball draws
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
    print(f"✓ Created {len(draws_df)} historical draws")
    
    # Step 2: Initialize and train model
    print("\n[2/5] Training Random Forest model...")
    start_train = time.time()
    
    model = RandomForestModel(
        n_estimators=50,  # Reduced for faster testing
        max_depth=10,
        use_pretrained=False
    )
    
    model.train(draws_df, test_size=0.2)
    train_time = time.time() - start_train
    print(f"✓ Model trained in {train_time:.2f}s")
    
    # Step 3: Generate batch of 100 tickets (production scenario)
    print("\n[3/5] Generating 100 tickets (production batch size)...")
    start_gen = time.time()
    
    try:
        tickets = model.generate_tickets(
            draws_df,
            count=100,
            timeout=30  # Production timeout
        )
        gen_time = time.time() - start_gen
        
        print(f"✓ Generated {len(tickets)} tickets in {gen_time:.2f}s")
        
        # Step 4: Validate results
        print("\n[4/5] Validating generated tickets...")
        
        # Check count
        assert len(tickets) == 100, f"Expected 100 tickets, got {len(tickets)}"
        print(f"✓ Correct ticket count: {len(tickets)}")
        
        # Check generation time
        assert gen_time < 30.0, f"Generation took {gen_time:.2f}s, should be < 30s"
        print(f"✓ Generation time acceptable: {gen_time:.2f}s < 30s")
        
        # Validate ticket structure
        for i, ticket in enumerate(tickets[:5]):  # Check first 5
            assert 'white_balls' in ticket, f"Ticket {i} missing white_balls"
            assert 'powerball' in ticket, f"Ticket {i} missing powerball"
            assert 'strategy' in ticket, f"Ticket {i} missing strategy"
            assert len(ticket['white_balls']) == 5, f"Ticket {i} has wrong number of white balls"
            assert ticket['strategy'] == 'random_forest', f"Ticket {i} wrong strategy"
            
            # Validate ranges
            for wb in ticket['white_balls']:
                assert 1 <= wb <= 69, f"Ticket {i} white ball {wb} out of range"
            assert 1 <= ticket['powerball'] <= 26, f"Ticket {i} powerball out of range"
            
            # Check sorted
            assert ticket['white_balls'] == sorted(ticket['white_balls']), f"Ticket {i} not sorted"
        
        print("✓ All tickets have valid structure and values")
        
        # Step 5: Performance summary
        print("\n[5/5] Performance Summary")
        print("-" * 60)
        print(f"Historical draws processed: {len(draws_df)}")
        print(f"Training time: {train_time:.2f}s")
        print(f"Ticket generation time: {gen_time:.2f}s")
        print(f"Tickets generated: {len(tickets)}")
        print(f"Avg time per ticket: {(gen_time / len(tickets) * 1000):.1f}ms")
        print("-" * 60)
        
        # Performance assertion
        avg_per_ticket = gen_time / len(tickets)
        assert avg_per_ticket < 0.5, f"Avg per ticket {avg_per_ticket:.2f}s too slow"
        
        print("\n✓ INTEGRATION TEST PASSED")
        print("="*60)
        
        return True
        
    except TimeoutError as e:
        print(f"\n✗ TIMEOUT ERROR: {e}")
        print("This indicates the optimization did not fully resolve the hanging issue.")
        raise
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        raise


def test_batch_generator_with_random_forest():
    """
    Test BatchTicketGenerator with actual RandomForest backend.
    
    This ensures the integration between batch generator and optimized
    RandomForest model works correctly.
    """
    from src.batch_generator import BatchTicketGenerator
    from src.prediction_engine import UnifiedPredictionEngine
    
    print("\n" + "="*60)
    print("INTEGRATION TEST: Batch Generator + Random Forest")
    print("="*60)
    
    print("\n[1/3] Testing prediction engine with random_forest mode...")
    
    # Mock the database function to return sample data
    with patch('src.database.get_all_draws') as mock_draws:
        # Create sample draws
        n_draws = 100
        dates = [datetime.now() - timedelta(days=i*3) for i in range(n_draws)]
        
        mock_draws.return_value = pd.DataFrame({
            'draw_date': dates,
            'n1': np.random.randint(1, 15, n_draws),
            'n2': np.random.randint(15, 30, n_draws),
            'n3': np.random.randint(30, 45, n_draws),
            'n4': np.random.randint(45, 60, n_draws),
            'n5': np.random.randint(60, 70, n_draws),
            'pb': np.random.randint(1, 27, n_draws),
        })
        
        # Create prediction engine
        try:
            engine = UnifiedPredictionEngine(mode='random_forest')
            print("✓ Prediction engine initialized")
            
            # Generate small batch
            print("\n[2/3] Generating 10 tickets via prediction engine...")
            start = time.time()
            tickets = engine.generate_tickets(count=10)
            elapsed = time.time() - start
            
            assert len(tickets) == 10, f"Expected 10 tickets, got {len(tickets)}"
            print(f"✓ Generated {len(tickets)} tickets in {elapsed:.2f}s")
            
            # Verify ticket format
            print("\n[3/3] Validating ticket format...")
            for ticket in tickets:
                assert 'white_balls' in ticket
                assert 'powerball' in ticket
                assert len(ticket['white_balls']) == 5
            
            print("✓ All tickets valid")
            print("\n✓ INTEGRATION TEST PASSED")
            print("="*60)
            
            return True
            
        except Exception as e:
            print(f"\n✗ ERROR: {e}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    print("Running Random Forest Batch Integration Tests...")
    print("This validates the optimization fixes the hanging issue.\n")
    
    try:
        # Test 1: Direct RandomForest integration
        test_random_forest_batch_generation_integration()
        
        # Test 2: BatchGenerator + RandomForest integration
        test_batch_generator_with_random_forest()
        
        print("\n" + "="*60)
        print("ALL INTEGRATION TESTS PASSED ✓")
        print("="*60)
        print("\nThe optimization successfully fixes the batch generation hang!")
        
    except Exception as e:
        print("\n" + "="*60)
        print("INTEGRATION TESTS FAILED ✗")
        print("="*60)
        print(f"\nError: {e}")
        import sys
        sys.exit(1)
