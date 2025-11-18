"""
Random Forest Model for Lottery Prediction
==========================================
Uses Random Forest ensemble method to predict lottery number probabilities
based on historical patterns and engineered features.

This model uses multiple decision trees trained on different aspects of
the data to create robust predictions through voting/averaging.
"""

import os
import numpy as np
import pandas as pd
import joblib
from typing import List, Dict, Tuple, Optional
from loguru import logger
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


class RandomForestModel:
    """
    Random Forest-based model for lottery number prediction.
    
    Architecture:
        - Feature engineering from historical draws
        - Separate Random Forest classifiers for white balls and powerball
        - Feature scaling for improved performance
        - Probability estimation from tree voting
    
    Features:
        - Hot/cold number analysis
        - Number frequency features
        - Gap analysis (draws since last appearance)
        - Co-occurrence features
        - Temporal features (day of week, month, etc.)
    """
    
    def __init__(
        self,
        n_estimators: int = 200,
        max_depth: Optional[int] = 20,
        min_samples_split: int = 5,
        min_samples_leaf: int = 2,
        model_dir: str = "models/random_forest",
        use_pretrained: bool = True
    ):
        """
        Initialize Random Forest model.
        
        Args:
            n_estimators: Number of trees in the forest
            max_depth: Maximum depth of trees (None for unlimited)
            min_samples_split: Minimum samples required to split a node
            min_samples_leaf: Minimum samples required at a leaf node
            model_dir: Directory to save/load models
            use_pretrained: Whether to load pretrained model if available
        """
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.min_samples_leaf = min_samples_leaf
        self.model_dir = model_dir
        
        # Create model directory if it doesn't exist
        os.makedirs(model_dir, exist_ok=True)
        
        # Models and scalers
        self.wb_models = []  # One model per white ball position
        self.pb_model = None
        self.scaler = StandardScaler()
        
        # Model paths
        self.wb_models_path = os.path.join(model_dir, "rf_white_balls.pkl")
        self.pb_model_path = os.path.join(model_dir, "rf_powerball.pkl")
        self.scaler_path = os.path.join(model_dir, "rf_scaler.pkl")
        
        # Load pretrained models if requested
        if use_pretrained:
            self._load_models()
        
        logger.info(
            f"RandomForestModel initialized (n_estimators={n_estimators}, "
            f"max_depth={max_depth})"
        )
    
    def _engineer_features(self, draws_df: pd.DataFrame) -> pd.DataFrame:
        """
        Engineer features from historical draw data.
        
        Args:
            draws_df: DataFrame with historical draws
            
        Returns:
            DataFrame with engineered features
        """
        features = pd.DataFrame(index=draws_df.index)
        
        # Ensure draw_date is datetime
        if 'draw_date' in draws_df.columns:
            draws_df['draw_date'] = pd.to_datetime(draws_df['draw_date'])
        
        # White ball columns
        white_ball_cols = ['n1', 'n2', 'n3', 'n4', 'n5']
        
        # 1. Frequency features (last N draws)
        for window in [10, 20, 50]:
            for num in range(1, 70):
                freq_col = f'freq_{num}_last_{window}'
                freq_values = []
                
                for idx in range(len(draws_df)):
                    start_idx = max(0, idx - window)
                    window_draws = draws_df.iloc[start_idx:idx]
                    
                    if len(window_draws) == 0:
                        freq_values.append(0)
                    else:
                        count = sum(
                            (window_draws[col] == num).sum()
                            for col in white_ball_cols
                        )
                        freq_values.append(count / len(window_draws) / 5)
                
                features[freq_col] = freq_values
        
        # 2. Gap analysis (draws since last appearance)
        for num in range(1, 70):
            gap_col = f'gap_{num}'
            gap_values = []
            
            for idx in range(len(draws_df)):
                # Look backwards for last appearance
                gap = 0
                for look_back in range(1, min(idx + 1, 100)):
                    prev_draw = draws_df.iloc[idx - look_back]
                    if any(prev_draw[col] == num for col in white_ball_cols):
                        gap = look_back
                        break
                else:
                    gap = 100  # Cap at 100 draws
                
                gap_values.append(gap)
            
            features[gap_col] = gap_values
        
        # 3. Temporal features
        if 'draw_date' in draws_df.columns:
            features['day_of_week'] = draws_df['draw_date'].dt.dayofweek
            features['month'] = draws_df['draw_date'].dt.month
            features['day_of_month'] = draws_df['draw_date'].dt.day
        
        # 4. Statistical features
        features['draw_sum'] = draws_df[white_ball_cols].sum(axis=1)
        features['draw_mean'] = draws_df[white_ball_cols].mean(axis=1)
        features['draw_std'] = draws_df[white_ball_cols].std(axis=1)
        features['draw_range'] = draws_df['n5'] - draws_df['n1']
        
        # 5. Powerball frequency features
        if 'pb' in draws_df.columns:
            for window in [10, 20, 50]:
                for pb_num in range(1, 27):
                    pb_freq_col = f'pb_freq_{pb_num}_last_{window}'
                    pb_freq_values = []
                    
                    for idx in range(len(draws_df)):
                        start_idx = max(0, idx - window)
                        window_draws = draws_df.iloc[start_idx:idx]
                        
                        if len(window_draws) == 0:
                            pb_freq_values.append(0)
                        else:
                            count = (window_draws['pb'] == pb_num).sum()
                            pb_freq_values.append(count / len(window_draws))
                    
                    features[pb_freq_col] = pb_freq_values
        
        # Fill NaN values with 0
        features = features.fillna(0)
        
        logger.info(f"Engineered {len(features.columns)} features from {len(draws_df)} draws")
        
        return features
    
    def train(
        self,
        draws_df: pd.DataFrame,
        test_size: float = 0.2,
        random_state: int = 42
    ) -> Dict:
        """
        Train Random Forest models on historical draw data.
        
        Args:
            draws_df: DataFrame with historical draws
            test_size: Fraction of data to use for testing
            random_state: Random seed for reproducibility
            
        Returns:
            Dict with training metrics
        """
        logger.info(f"Training Random Forest models on {len(draws_df)} draws...")
        
        # Engineer features
        X = self._engineer_features(draws_df)
        
        # Fit scaler on all data
        X_scaled = self.scaler.fit_transform(X)
        X_scaled = pd.DataFrame(X_scaled, columns=X.columns, index=X.index)
        
        # Split data
        train_indices, test_indices = train_test_split(
            range(len(X_scaled)),
            test_size=test_size,
            random_state=random_state,
            shuffle=False  # Preserve temporal order
        )
        
        X_train = X_scaled.iloc[train_indices]
        X_test = X_scaled.iloc[test_indices]
        
        white_ball_cols = ['n1', 'n2', 'n3', 'n4', 'n5']
        metrics = {}
        
        # Train 5 models for white balls (one per position)
        self.wb_models = []
        for i, col in enumerate(white_ball_cols):
            logger.info(f"Training model for white ball position {i+1}...")
            
            y = draws_df[col].values
            y_train = y[train_indices]
            y_test = y[test_indices]
            
            model = RandomForestClassifier(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                min_samples_split=self.min_samples_split,
                min_samples_leaf=self.min_samples_leaf,
                random_state=random_state,
                n_jobs=-1,
                verbose=0
            )
            
            model.fit(X_train, y_train)
            train_score = model.score(X_train, y_train)
            test_score = model.score(X_test, y_test)
            
            self.wb_models.append(model)
            
            metrics[f'wb_{i+1}_train_score'] = train_score
            metrics[f'wb_{i+1}_test_score'] = test_score
            
            logger.info(
                f"White ball {i+1}: train_score={train_score:.4f}, "
                f"test_score={test_score:.4f}"
            )
        
        # Train powerball model
        logger.info("Training powerball model...")
        
        y_pb = draws_df['pb'].values
        y_pb_train = y_pb[train_indices]
        y_pb_test = y_pb[test_indices]
        
        self.pb_model = RandomForestClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            min_samples_split=self.min_samples_split,
            min_samples_leaf=self.min_samples_leaf,
            random_state=random_state,
            n_jobs=-1,
            verbose=0
        )
        
        self.pb_model.fit(X_train, y_pb_train)
        pb_train_score = self.pb_model.score(X_train, y_pb_train)
        pb_test_score = self.pb_model.score(X_test, y_pb_test)
        
        metrics['pb_train_score'] = pb_train_score
        metrics['pb_test_score'] = pb_test_score
        
        logger.info(
            f"Powerball: train_score={pb_train_score:.4f}, "
            f"test_score={pb_test_score:.4f}"
        )
        
        # Save models
        self._save_models()
        
        logger.info("Random Forest training completed successfully")
        
        return metrics
    
    def _save_models(self):
        """Save trained models to disk."""
        try:
            joblib.dump(self.wb_models, self.wb_models_path)
            joblib.dump(self.pb_model, self.pb_model_path)
            joblib.dump(self.scaler, self.scaler_path)
            logger.info(f"Models saved to {self.model_dir}")
        except Exception as e:
            logger.error(f"Failed to save models: {e}")
    
    def _load_models(self) -> bool:
        """
        Load pretrained models from disk.
        
        Returns:
            True if models loaded successfully, False otherwise
        """
        try:
            if os.path.exists(self.wb_models_path):
                self.wb_models = joblib.load(self.wb_models_path)
                logger.info(f"Loaded white ball models from {self.wb_models_path}")
            
            if os.path.exists(self.pb_model_path):
                self.pb_model = joblib.load(self.pb_model_path)
                logger.info(f"Loaded powerball model from {self.pb_model_path}")
            
            if os.path.exists(self.scaler_path):
                self.scaler = joblib.load(self.scaler_path)
                logger.info(f"Loaded scaler from {self.scaler_path}")
            
            return (
                len(self.wb_models) == 5 and
                self.pb_model is not None and
                self.scaler is not None
            )
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
            recent_draws: DataFrame with recent draws (all historical data for feature engineering)
            
        Returns:
            Tuple of (wb_probs, pb_probs) where:
                - wb_probs: Probability distribution over 69 white balls
                - pb_probs: Probability distribution over 26 powerballs
        """
        if len(self.wb_models) != 5 or self.pb_model is None:
            raise RuntimeError("Models not trained or loaded. Call train() or load pretrained models.")
        
        # Engineer features for the most recent draw
        X = self._engineer_features(recent_draws)
        X_scaled = self.scaler.transform(X)
        X_latest = X_scaled[-1:] # Last row
        
        # Predict probabilities for each white ball position
        wb_position_probs = []
        for i, model in enumerate(self.wb_models):
            probs = model.predict_proba(X_latest)[0]
            
            # Convert to full 69-length array
            full_probs = np.zeros(69)
            for class_idx, class_val in enumerate(model.classes_):
                if 1 <= class_val <= 69:
                    full_probs[class_val - 1] = probs[class_idx]
            
            wb_position_probs.append(full_probs)
        
        # Average probabilities across all positions
        wb_probs = np.mean(wb_position_probs, axis=0)
        wb_probs = wb_probs / wb_probs.sum()  # Normalize
        
        # Predict powerball probabilities
        pb_probs_raw = self.pb_model.predict_proba(X_latest)[0]
        pb_probs = np.zeros(26)
        for class_idx, class_val in enumerate(self.pb_model.classes_):
            if 1 <= class_val <= 26:
                pb_probs[class_val - 1] = pb_probs_raw[class_idx]
        pb_probs = pb_probs / pb_probs.sum()  # Normalize
        
        logger.debug(
            f"Predicted probabilities: wb_probs sum={wb_probs.sum():.4f}, "
            f"pb_probs sum={pb_probs.sum():.4f}"
        )
        
        return wb_probs, pb_probs
    
    def generate_tickets(
        self,
        recent_draws: pd.DataFrame,
        count: int = 5
    ) -> List[Dict]:
        """
        Generate lottery tickets using Random Forest predictions.
        
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
            powerball = int(np.random.choice(range(1, 27), p=pb_probs))
            
            tickets.append({
                'white_balls': white_balls,
                'powerball': powerball,
                'strategy': 'random_forest',
                'confidence': float(np.mean([wb_probs[n-1] for n in white_balls]))
            })
        
        logger.info(f"Generated {count} tickets using Random Forest model")
        return tickets
    
    def get_model_info(self) -> Dict:
        """
        Get information about the model.
        
        Returns:
            Dict with model metadata
        """
        return {
            'model_type': 'RandomForest',
            'n_estimators': self.n_estimators,
            'max_depth': self.max_depth,
            'min_samples_split': self.min_samples_split,
            'min_samples_leaf': self.min_samples_leaf,
            'wb_models_loaded': len(self.wb_models) == 5,
            'pb_model_loaded': self.pb_model is not None,
            'scaler_loaded': self.scaler is not None,
            'wb_models_path': self.wb_models_path,
            'pb_model_path': self.pb_model_path
        }
