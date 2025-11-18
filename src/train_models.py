"""
Training Pipeline for Advanced ML Models
=========================================
Trains LSTM and Random Forest models on historical lottery draw data.

Usage:
    python src/train_models.py --model lstm
    python src/train_models.py --model random_forest
    python src/train_models.py --model all
"""

import argparse
import sys
from loguru import logger
from src.database import get_all_draws


def train_lstm_model(draws_df, epochs=50, batch_size=32):
    """
    Train LSTM model on historical draws.
    
    Args:
        draws_df: DataFrame with historical draws
        epochs: Number of training epochs
        batch_size: Batch size for training
        
    Returns:
        Training metrics dict
    """
    logger.info("=" * 60)
    logger.info("Training LSTM Model")
    logger.info("=" * 60)
    
    try:
        from src.ml_models.lstm_model import LSTMModel
    except ImportError as e:
        logger.error(f"Failed to import LSTM model: {e}")
        logger.error("Install TensorFlow with: pip install tensorflow")
        return None
    
    # Initialize model
    model = LSTMModel(
        sequence_length=20,
        lstm_units=128,
        dropout_rate=0.3,
        use_pretrained=False
    )
    
    # Train
    logger.info(f"Training on {len(draws_df)} historical draws...")
    metrics = model.train(
        draws_df,
        epochs=epochs,
        batch_size=batch_size,
        validation_split=0.2,
        verbose=1
    )
    
    logger.info("LSTM Training Complete!")
    logger.info(f"White Ball Final Loss: {metrics['wb_final_loss']:.4f}")
    logger.info(f"White Ball Final Val Loss: {metrics['wb_final_val_loss']:.4f}")
    logger.info(f"Powerball Final Loss: {metrics['pb_final_loss']:.4f}")
    logger.info(f"Powerball Final Val Loss: {metrics['pb_final_val_loss']:.4f}")
    
    return metrics


def train_random_forest_model(draws_df, n_estimators=200):
    """
    Train Random Forest model on historical draws.
    
    Args:
        draws_df: DataFrame with historical draws
        n_estimators: Number of trees in the forest
        
    Returns:
        Training metrics dict
    """
    logger.info("=" * 60)
    logger.info("Training Random Forest Model")
    logger.info("=" * 60)
    
    from src.ml_models.random_forest_model import RandomForestModel
    
    # Initialize model
    model = RandomForestModel(
        n_estimators=n_estimators,
        max_depth=20,
        min_samples_split=5,
        min_samples_leaf=2,
        use_pretrained=False
    )
    
    # Train
    logger.info(f"Training on {len(draws_df)} historical draws...")
    metrics = model.train(
        draws_df,
        test_size=0.2,
        random_state=42
    )
    
    logger.info("Random Forest Training Complete!")
    logger.info("White Ball Model Scores:")
    for i in range(1, 6):
        train_score = metrics.get(f'wb_{i}_train_score', 0)
        test_score = metrics.get(f'wb_{i}_test_score', 0)
        logger.info(f"  Position {i}: train={train_score:.4f}, test={test_score:.4f}")
    
    logger.info("Powerball Model Scores:")
    logger.info(f"  train={metrics['pb_train_score']:.4f}, test={metrics['pb_test_score']:.4f}")
    
    return metrics


def main():
    """Main training pipeline."""
    parser = argparse.ArgumentParser(
        description="Train advanced ML models for lottery prediction"
    )
    parser.add_argument(
        '--model',
        type=str,
        choices=['lstm', 'random_forest', 'all'],
        default='all',
        help="Which model to train (default: all)"
    )
    parser.add_argument(
        '--epochs',
        type=int,
        default=50,
        help="Number of epochs for LSTM training (default: 50)"
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=32,
        help="Batch size for LSTM training (default: 32)"
    )
    parser.add_argument(
        '--n-estimators',
        type=int,
        default=200,
        help="Number of trees for Random Forest (default: 200)"
    )
    parser.add_argument(
        '--min-draws',
        type=int,
        default=100,
        help="Minimum number of draws required for training (default: 100)"
    )
    
    args = parser.parse_args()
    
    # Load historical draws
    logger.info("Loading historical draw data...")
    draws_df = get_all_draws()
    
    if len(draws_df) == 0:
        logger.error("No historical draws found in database!")
        logger.error("Run: python scripts/update_draws.py")
        sys.exit(1)
    
    logger.info(f"Loaded {len(draws_df)} historical draws")
    
    # Check minimum data requirement
    if len(draws_df) < args.min_draws:
        logger.warning(
            f"Only {len(draws_df)} draws available. "
            f"Recommended minimum: {args.min_draws} draws for robust training."
        )
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            logger.info("Training cancelled.")
            sys.exit(0)
    
    # Train models based on selection
    results = {}
    
    if args.model in ['lstm', 'all']:
        try:
            lstm_metrics = train_lstm_model(
                draws_df,
                epochs=args.epochs,
                batch_size=args.batch_size
            )
            results['lstm'] = lstm_metrics
        except Exception as e:
            logger.error(f"LSTM training failed: {e}")
            if args.model == 'lstm':
                sys.exit(1)
    
    if args.model in ['random_forest', 'all']:
        try:
            rf_metrics = train_random_forest_model(
                draws_df,
                n_estimators=args.n_estimators
            )
            results['random_forest'] = rf_metrics
        except Exception as e:
            logger.error(f"Random Forest training failed: {e}")
            if args.model == 'random_forest':
                sys.exit(1)
    
    # Summary
    logger.info("=" * 60)
    logger.info("Training Pipeline Complete!")
    logger.info("=" * 60)
    
    if 'lstm' in results and results['lstm']:
        logger.info("✓ LSTM model trained and saved")
    
    if 'random_forest' in results and results['random_forest']:
        logger.info("✓ Random Forest model trained and saved")
    
    logger.info("")
    logger.info("Test predictions with:")
    logger.info("  PREDICTION_MODE=lstm python main.py")
    logger.info("  PREDICTION_MODE=random_forest python main.py")


if __name__ == "__main__":
    main()
