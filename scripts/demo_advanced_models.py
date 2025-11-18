#!/usr/bin/env python3
"""
Demo: Advanced ML Models (LSTM and Random Forest)
==================================================
This script demonstrates how to use the new LSTM and Random Forest models
for lottery prediction.

Usage:
    python scripts/demo_advanced_models.py
"""

import sys
import os
import pandas as pd
import numpy as np
from loguru import logger

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def demo_random_forest():
    """Demonstrate Random Forest model usage."""
    logger.info("=" * 70)
    logger.info("DEMO: Random Forest Model")
    logger.info("=" * 70)
    
    from src.ml_models.random_forest_model import RandomForestModel
    
    # Create sample historical data
    logger.info("Creating sample historical data (100 draws)...")
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', periods=100, freq='3D')
    sample_data = {
        'draw_date': [d.strftime('%Y-%m-%d') for d in dates],
        'n1': np.random.randint(1, 70, 100),
        'n2': np.random.randint(1, 70, 100),
        'n3': np.random.randint(1, 70, 100),
        'n4': np.random.randint(1, 70, 100),
        'n5': np.random.randint(1, 70, 100),
        'pb': np.random.randint(1, 27, 100)
    }
    draws_df = pd.DataFrame(sample_data)
    
    # Initialize model
    logger.info("Initializing Random Forest model...")
    model = RandomForestModel(
        n_estimators=50,  # Reduced for demo speed
        max_depth=10,
        use_pretrained=False
    )
    
    # Train model
    logger.info("Training Random Forest model (this may take a minute)...")
    metrics = model.train(draws_df, test_size=0.2)
    
    logger.info("Training completed!")
    logger.info(f"Powerball model - Train: {metrics['pb_train_score']:.4f}, Test: {metrics['pb_test_score']:.4f}")
    
    # Generate predictions
    logger.info("Generating 5 tickets...")
    tickets = model.generate_tickets(draws_df, count=5)
    
    logger.info("Generated tickets:")
    for i, ticket in enumerate(tickets, 1):
        wb = ticket['white_balls']
        pb = ticket['powerball']
        conf = ticket['confidence']
        logger.info(f"  {i}. {wb} + PB {pb} (confidence: {conf:.3f})")
    
    logger.info("")


def demo_lstm():
    """Demonstrate LSTM model usage."""
    logger.info("=" * 70)
    logger.info("DEMO: LSTM Model")
    logger.info("=" * 70)
    
    try:
        from src.ml_models.lstm_model import LSTMModel, KERAS_AVAILABLE
        
        if not KERAS_AVAILABLE:
            logger.warning("TensorFlow/Keras not installed. Skipping LSTM demo.")
            logger.info("To enable LSTM: pip install tensorflow")
            return
        
        # Create sample historical data
        logger.info("Creating sample historical data (50 draws)...")
        np.random.seed(42)
        dates = pd.date_range('2023-01-01', periods=50, freq='3D')
        sample_data = {
            'draw_date': [d.strftime('%Y-%m-%d') for d in dates],
            'n1': np.random.randint(1, 70, 50),
            'n2': np.random.randint(1, 70, 50),
            'n3': np.random.randint(1, 70, 50),
            'n4': np.random.randint(1, 70, 50),
            'n5': np.random.randint(1, 70, 50),
            'pb': np.random.randint(1, 27, 50)
        }
        draws_df = pd.DataFrame(sample_data)
        
        # Initialize model
        logger.info("Initializing LSTM model...")
        model = LSTMModel(
            sequence_length=10,  # Reduced for demo with limited data
            lstm_units=64,
            dropout_rate=0.3,
            use_pretrained=False
        )
        
        # Train model
        logger.info("Training LSTM model (this may take several minutes)...")
        logger.info("Note: LSTM training is verbose. Please wait...")
        
        metrics = model.train(
            draws_df,
            epochs=10,  # Reduced for demo
            batch_size=8,
            verbose=0  # Quiet mode for demo
        )
        
        logger.info("Training completed!")
        logger.info(f"White balls - Loss: {metrics['wb_final_loss']:.4f}, Val Loss: {metrics['wb_final_val_loss']:.4f}")
        logger.info(f"Powerball - Loss: {metrics['pb_final_loss']:.4f}, Val Loss: {metrics['pb_final_val_loss']:.4f}")
        
        # Generate predictions
        logger.info("Generating 5 tickets...")
        tickets = model.generate_tickets(draws_df, count=5)
        
        logger.info("Generated tickets:")
        for i, ticket in enumerate(tickets, 1):
            wb = ticket['white_balls']
            pb = ticket['powerball']
            conf = ticket['confidence']
            logger.info(f"  {i}. {wb} + PB {pb} (confidence: {conf:.3f})")
        
        logger.info("")
        
    except ImportError as e:
        logger.warning(f"LSTM model requires TensorFlow: {e}")
        logger.info("Install with: pip install tensorflow")


def demo_prediction_engine():
    """Demonstrate prediction engine integration."""
    logger.info("=" * 70)
    logger.info("DEMO: Prediction Engine Integration")
    logger.info("=" * 70)
    
    from src.prediction_engine import UnifiedPredictionEngine
    
    # Test Random Forest mode
    logger.info("Testing Random Forest mode...")
    engine_rf = UnifiedPredictionEngine(mode='random_forest')
    logger.info(f"Engine initialized with mode: {engine_rf.mode}")
    
    if engine_rf.mode == 'random_forest':
        logger.info("✓ Random Forest mode active")
    else:
        logger.info(f"✗ Fallback to {engine_rf.mode} mode (insufficient data or model not available)")
    
    # Test LSTM mode
    logger.info("")
    logger.info("Testing LSTM mode...")
    engine_lstm = UnifiedPredictionEngine(mode='lstm')
    logger.info(f"Engine initialized with mode: {engine_lstm.mode}")
    
    if engine_lstm.mode == 'lstm':
        logger.info("✓ LSTM mode active")
    else:
        logger.info(f"✗ Fallback to {engine_lstm.mode} mode (insufficient data or TensorFlow not available)")
    
    logger.info("")


def main():
    """Run all demos."""
    logger.info("Advanced ML Models Demo")
    logger.info("=" * 70)
    logger.info("")
    
    try:
        # Demo 1: Random Forest
        demo_random_forest()
        
        # Demo 2: LSTM
        demo_lstm()
        
        # Demo 3: Prediction Engine
        demo_prediction_engine()
        
        logger.info("=" * 70)
        logger.info("Demo completed successfully!")
        logger.info("=" * 70)
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Train models on real data: python src/train_models.py --model all")
        logger.info("2. Use in production: PREDICTION_MODE=random_forest python main.py")
        logger.info("3. Or: PREDICTION_MODE=lstm python main.py")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
