"""
LSTM Model for Lottery Prediction
==================================
Uses LSTM (Long Short-Term Memory) neural network to analyze temporal patterns
in historical lottery draws and predict future number probabilities.

This model treats lottery prediction as a sequence modeling problem, where
the model learns patterns from historical sequences of draws.
"""

import os
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from loguru import logger

# TensorFlow/Keras imports (optional, with fallback)
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
    from tensorflow.keras.models import Sequential, load_model
    from tensorflow.keras.layers import LSTM, Dense, Dropout, Embedding
    from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
    KERAS_AVAILABLE = True
except ImportError:
    KERAS_AVAILABLE = False
    logger.warning("TensorFlow/Keras not available. Install with: pip install tensorflow")


class LSTMModel:
    """
    LSTM-based model for lottery number prediction.
    
    Architecture:
        - Input: Sequence of historical draws (configurable window size)
        - LSTM layers: Learn temporal patterns
        - Dense layers: Project to probability distribution over numbers
        - Output: Probabilities for white balls (1-69) and powerball (1-26)
    
    Features:
        - Sequence-based learning from historical patterns
        - Separate models for white balls and powerball
        - Early stopping to prevent overfitting
        - Model checkpointing for best performance
    """
    
    def __init__(
        self,
        sequence_length: int = 20,
        lstm_units: int = 128,
        dropout_rate: float = 0.3,
        model_dir: str = "models/lstm",
        use_pretrained: bool = True
    ):
        """
        Initialize LSTM model.
        
        Args:
            sequence_length: Number of historical draws to use as input
            lstm_units: Number of LSTM units in hidden layers
            dropout_rate: Dropout rate for regularization
            model_dir: Directory to save/load models
            use_pretrained: Whether to load pretrained model if available
        """
        if not KERAS_AVAILABLE:
            raise ImportError(
                "TensorFlow/Keras is required for LSTM model. "
                "Install with: pip install tensorflow"
            )
        
        self.sequence_length = sequence_length
        self.lstm_units = lstm_units
        self.dropout_rate = dropout_rate
        self.model_dir = model_dir
        
        # Create model directory if it doesn't exist
        os.makedirs(model_dir, exist_ok=True)
        
        # Models for white balls and powerball
        self.wb_model = None
        self.pb_model = None
        
        # Model paths
        self.wb_model_path = os.path.join(model_dir, "lstm_white_balls.keras")
        self.pb_model_path = os.path.join(model_dir, "lstm_powerball.keras")
        
        # Training history
        self.wb_history = None
        self.pb_history = None
        
        # Load pretrained models if requested
        if use_pretrained:
            self._load_models()
        
        logger.info(
            f"LSTMModel initialized (seq_len={sequence_length}, "
            f"units={lstm_units}, dropout={dropout_rate})"
        )
    
    def _build_white_ball_model(self):
        """
        Build LSTM model for white ball prediction.
        
        Returns:
            Keras Sequential model
        """
        model = Sequential([
            # Input layer: sequence of draws, each with 5 numbers
            layers.Input(shape=(self.sequence_length, 5)),
            
            # First LSTM layer with return sequences
            LSTM(self.lstm_units, return_sequences=True),
            Dropout(self.dropout_rate),
            
            # Second LSTM layer
            LSTM(self.lstm_units // 2),
            Dropout(self.dropout_rate),
            
            # Dense layers
            Dense(128, activation='relu'),
            Dropout(self.dropout_rate),
            
            # Output layer: probabilities for 69 white balls
            Dense(69, activation='softmax')
        ])
        
        model.compile(
            optimizer='adam',
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        
        logger.debug("White ball LSTM model built successfully")
        return model
    
    def _build_powerball_model(self):
        """
        Build LSTM model for powerball prediction.
        
        Returns:
            Keras Sequential model
        """
        model = Sequential([
            # Input layer: sequence of powerballs
            layers.Input(shape=(self.sequence_length, 1)),
            
            # LSTM layer
            LSTM(self.lstm_units // 2),
            Dropout(self.dropout_rate),
            
            # Dense layers
            Dense(64, activation='relu'),
            Dropout(self.dropout_rate),
            
            # Output layer: probabilities for 26 powerballs
            Dense(26, activation='softmax')
        ])
        
        model.compile(
            optimizer='adam',
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        
        logger.debug("Powerball LSTM model built successfully")
        return model
    
    def _prepare_sequences(
        self,
        draws_df: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Prepare sequence data for LSTM training.
        
        Args:
            draws_df: DataFrame with historical draws
            
        Returns:
            Tuple of (X_wb, y_wb, X_pb, y_pb) where:
                - X_wb: White ball sequences (samples, seq_len, 5)
                - y_wb: Target white ball probabilities (samples, 69)
                - X_pb: Powerball sequences (samples, seq_len, 1)
                - y_pb: Target powerball probabilities (samples, 26)
        """
        # Extract white balls and powerball columns
        white_ball_cols = ['n1', 'n2', 'n3', 'n4', 'n5']
        pb_col = 'pb'
        
        # Ensure we have enough data
        if len(draws_df) < self.sequence_length + 1:
            raise ValueError(
                f"Insufficient data: need at least {self.sequence_length + 1} draws, "
                f"got {len(draws_df)}"
            )
        
        # Convert to numpy arrays
        white_balls = draws_df[white_ball_cols].values
        powerballs = draws_df[pb_col].values
        
        # Create sequences
        X_wb_list = []
        y_wb_list = []
        X_pb_list = []
        y_pb_list = []
        
        for i in range(len(draws_df) - self.sequence_length):
            # White ball sequence
            wb_seq = white_balls[i:i + self.sequence_length]
            X_wb_list.append(wb_seq)
            
            # Target: next draw's white balls (convert to multi-hot encoding)
            next_wb = white_balls[i + self.sequence_length]
            y_wb = np.zeros(69)
            for num in next_wb:
                if 1 <= num <= 69:
                    y_wb[num - 1] = 1.0 / 5  # Equal probability across 5 numbers
            y_wb_list.append(y_wb)
            
            # Powerball sequence
            pb_seq = powerballs[i:i + self.sequence_length].reshape(-1, 1)
            X_pb_list.append(pb_seq)
            
            # Target: next draw's powerball (one-hot encoding)
            next_pb = powerballs[i + self.sequence_length]
            y_pb = np.zeros(26)
            if 1 <= next_pb <= 26:
                y_pb[next_pb - 1] = 1.0
            y_pb_list.append(y_pb)
        
        X_wb = np.array(X_wb_list)
        y_wb = np.array(y_wb_list)
        X_pb = np.array(X_pb_list)
        y_pb = np.array(y_pb_list)
        
        logger.info(
            f"Prepared sequences: X_wb={X_wb.shape}, y_wb={y_wb.shape}, "
            f"X_pb={X_pb.shape}, y_pb={y_pb.shape}"
        )
        
        return X_wb, y_wb, X_pb, y_pb
    
    def train(
        self,
        draws_df: pd.DataFrame,
        epochs: int = 50,
        batch_size: int = 32,
        validation_split: float = 0.2,
        verbose: int = 1
    ) -> Dict[str, any]:
        """
        Train the LSTM models on historical draw data.
        
        Args:
            draws_df: DataFrame with historical draws
            epochs: Number of training epochs
            batch_size: Batch size for training
            validation_split: Fraction of data to use for validation
            verbose: Verbosity level (0=silent, 1=progress bar, 2=one line per epoch)
            
        Returns:
            Dict with training history and metrics
        """
        logger.info(f"Training LSTM models on {len(draws_df)} draws...")
        
        # Prepare sequences
        X_wb, y_wb, X_pb, y_pb = self._prepare_sequences(draws_df)
        
        # Build models
        self.wb_model = self._build_white_ball_model()
        self.pb_model = self._build_powerball_model()
        
        # Callbacks
        wb_checkpoint = ModelCheckpoint(
            self.wb_model_path,
            monitor='val_loss',
            save_best_only=True,
            verbose=0
        )
        pb_checkpoint = ModelCheckpoint(
            self.pb_model_path,
            monitor='val_loss',
            save_best_only=True,
            verbose=0
        )
        early_stop = EarlyStopping(
            monitor='val_loss',
            patience=10,
            restore_best_weights=True,
            verbose=0
        )
        
        # Train white ball model
        logger.info("Training white ball model...")
        self.wb_history = self.wb_model.fit(
            X_wb, y_wb,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=validation_split,
            callbacks=[wb_checkpoint, early_stop],
            verbose=verbose
        )
        
        # Train powerball model
        logger.info("Training powerball model...")
        self.pb_history = self.pb_model.fit(
            X_pb, y_pb,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=validation_split,
            callbacks=[pb_checkpoint, early_stop],
            verbose=verbose
        )
        
        logger.info("LSTM training completed successfully")
        
        return {
            'wb_history': self.wb_history.history,
            'pb_history': self.pb_history.history,
            'wb_final_loss': self.wb_history.history['loss'][-1],
            'pb_final_loss': self.pb_history.history['loss'][-1],
            'wb_final_val_loss': self.wb_history.history['val_loss'][-1],
            'pb_final_val_loss': self.pb_history.history['val_loss'][-1]
        }
    
    def _load_models(self) -> bool:
        """
        Load pretrained models from disk.
        
        Returns:
            True if models loaded successfully, False otherwise
        """
        try:
            if os.path.exists(self.wb_model_path):
                self.wb_model = load_model(self.wb_model_path)
                logger.info(f"Loaded white ball model from {self.wb_model_path}")
            
            if os.path.exists(self.pb_model_path):
                self.pb_model = load_model(self.pb_model_path)
                logger.info(f"Loaded powerball model from {self.pb_model_path}")
            
            return self.wb_model is not None and self.pb_model is not None
        except Exception as e:
            logger.warning(f"Failed to load pretrained models: {e}")
            return False
    
    def predict_probabilities(
        self,
        recent_draws: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict probability distributions for next draw.
        
        Args:
            recent_draws: DataFrame with recent draws (must have at least sequence_length rows)
            
        Returns:
            Tuple of (wb_probs, pb_probs) where:
                - wb_probs: Probability distribution over 69 white balls
                - pb_probs: Probability distribution over 26 powerballs
        """
        if self.wb_model is None or self.pb_model is None:
            raise RuntimeError("Models not trained or loaded. Call train() or load pretrained models.")
        
        if len(recent_draws) < self.sequence_length:
            raise ValueError(
                f"Need at least {self.sequence_length} recent draws, got {len(recent_draws)}"
            )
        
        # Use the most recent sequence
        recent_draws = recent_draws.tail(self.sequence_length)
        
        # Prepare input sequences
        white_ball_cols = ['n1', 'n2', 'n3', 'n4', 'n5']
        pb_col = 'pb'
        
        X_wb = recent_draws[white_ball_cols].values.reshape(1, self.sequence_length, 5)
        X_pb = recent_draws[pb_col].values.reshape(1, self.sequence_length, 1)
        
        # Predict
        wb_probs = self.wb_model.predict(X_wb, verbose=0)[0]
        pb_probs = self.pb_model.predict(X_pb, verbose=0)[0]
        
        # Normalize to ensure sum=1
        wb_probs = wb_probs / wb_probs.sum()
        pb_probs = pb_probs / pb_probs.sum()
        
        logger.debug(f"Predicted probabilities: wb_probs sum={wb_probs.sum():.4f}, pb_probs sum={pb_probs.sum():.4f}")
        
        return wb_probs, pb_probs
    
    def generate_tickets(
        self,
        recent_draws: pd.DataFrame,
        count: int = 5
    ) -> List[Dict]:
        """
        Generate lottery tickets using LSTM predictions.
        
        Args:
            recent_draws: DataFrame with recent draws
            count: Number of tickets to generate
            
        Returns:
            List of ticket dictionaries
        """
        wb_probs, pb_probs = self.predict_probabilities(recent_draws)
        
        tickets = []
        for _ in range(count):
            # Sample white balls using predicted probabilities
            white_balls = sorted(np.random.choice(
                range(1, 70),
                size=5,
                replace=False,
                p=wb_probs
            ).tolist())
            
            # Sample powerball using predicted probabilities
            powerball = int(np.random.choice(range(1, 27), p=pb_probs)) + 1
            
            tickets.append({
                'white_balls': white_balls,
                'powerball': powerball,
                'strategy': 'lstm',
                'confidence': float(np.mean([wb_probs[n-1] for n in white_balls]))
            })
        
        logger.info(f"Generated {count} tickets using LSTM model")
        return tickets
    
    def get_model_info(self) -> Dict:
        """
        Get information about the model.
        
        Returns:
            Dict with model metadata
        """
        return {
            'model_type': 'LSTM',
            'sequence_length': self.sequence_length,
            'lstm_units': self.lstm_units,
            'dropout_rate': self.dropout_rate,
            'wb_model_loaded': self.wb_model is not None,
            'pb_model_loaded': self.pb_model is not None,
            'wb_model_path': self.wb_model_path,
            'pb_model_path': self.pb_model_path,
            'keras_available': KERAS_AVAILABLE
        }
