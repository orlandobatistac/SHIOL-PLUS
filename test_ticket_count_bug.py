#!/usr/bin/env python3
"""
Focused test to reproduce the ticket count bug.
Tests that each generation method respects the count parameter.
"""
import sys
import os
sys.path.insert(0, '.')

# Test 1: Test LSTM and RF model generate_tickets directly
print("=" * 60)
print("TEST 1: Direct model.generate_tickets() with count=100")
print("=" * 60)

try:
    import numpy as np
    import pandas as pd
    from src.ml_models.lstm_model import LSTMModel
    from src.ml_models.random_forest_model import RandomForestModel
    
    # Create dummy draws dataframe
    dummy_draws = pd.DataFrame({
        'draw_date': pd.date_range('2024-01-01', periods=20),
        'n1': np.random.randint(1, 69, 20),
        'n2': np.random.randint(1, 69, 20),
        'n3': np.random.randint(1, 69, 20),
        'n4': np.random.randint(1, 69, 20),
        'n5': np.random.randint(1, 69, 20),
        'pb': np.random.randint(1, 27, 20),
    })
    
    # Test LSTM
    print("\n[LSTM] Creating model...")
    lstm_model = LSTMModel(use_pretrained=False)
    
    # Test if it can generate 100 tickets
    print("[LSTM] Calling generate_tickets(count=100)...")
    try:
        lstm_tickets = lstm_model.generate_tickets(dummy_draws, count=100)
        print(f"[LSTM] Generated {len(lstm_tickets)} tickets")
        print(f"[LSTM] Result: {'✓ PASS' if len(lstm_tickets) == 100 else '✗ FAIL - Expected 100'}")
    except Exception as e:
        print(f"[LSTM] ✗ FAIL - Exception: {e}")
    
    # Test Random Forest
    print("\n[RF] Creating model...")
    rf_model = RandomForestModel(use_pretrained=False)
    
    print("[RF] Calling generate_tickets(count=100)...")
    try:
        rf_tickets = rf_model.generate_tickets(dummy_draws, count=100)
        print(f"[RF] Generated {len(rf_tickets)} tickets")
        print(f"[RF] Result: {'✓ PASS' if len(rf_tickets) == 100 else '✗ FAIL - Expected 100'}")
    except Exception as e:
        print(f"[RF] ✗ FAIL - Exception: {e}")
        
except ImportError as e:
    print(f"✗ SKIP - Missing dependencies: {e}")
except Exception as e:
    print(f"✗ FAIL - Unexpected error: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Test UnifiedPredictionEngine
print("\n" + "=" * 60)
print("TEST 2: UnifiedPredictionEngine.generate_tickets() with count=100")
print("=" * 60)

try:
    from src.prediction_engine import UnifiedPredictionEngine
    
    # Test LSTM mode
    print("\n[LSTM Mode] Creating engine...")
    lstm_engine = UnifiedPredictionEngine(mode='lstm')
    
    print("[LSTM Mode] Calling generate_tickets(count=100)...")
    try:
        tickets = lstm_engine.generate_tickets(count=100)
        print(f"[LSTM Mode] Generated {len(tickets)} tickets")
        print(f"[LSTM Mode] Result: {'✓ PASS' if len(tickets) == 100 else '✗ FAIL - Expected 100'}")
    except Exception as e:
        print(f"[LSTM Mode] ✗ FAIL - Exception: {e}")
    
    # Test Random Forest mode
    print("\n[RF Mode] Creating engine...")
    rf_engine = UnifiedPredictionEngine(mode='random_forest')
    
    print("[RF Mode] Calling generate_tickets(count=100)...")
    try:
        tickets = rf_engine.generate_tickets(count=100)
        print(f"[RF Mode] Generated {len(tickets)} tickets")
        print(f"[RF Mode] Result: {'✓ PASS' if len(tickets) == 100 else '✗ FAIL - Expected 100'}")
    except Exception as e:
        print(f"[RF Mode] ✗ FAIL - Exception: {e}")
        
except Exception as e:
    print(f"✗ FAIL - Unexpected error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
