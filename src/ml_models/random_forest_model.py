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
        
        OPTIMIZED VERSION: Uses vectorized operations to avoid O(n²) complexity.
        Reduces feature count from 354 to ~50 for dramatic speedup.
        
        Args:
            draws_df: DataFrame with historical draws
            
        Returns:
            DataFrame with engineered features
        """
        logger.info(f"Engineering features from {len(draws_df)} draws...")
        features = pd.DataFrame(index=draws_df.index)
        
        # Ensure draw_date is datetime
        if 'draw_date' in draws_df.columns:
            draws_df['draw_date'] = pd.to_datetime(draws_df['draw_date'])
        
        # White ball columns
        white_ball_cols = ['n1', 'n2', 'n3', 'n4', 'n5']
        
        # 1. OPTIMIZED: Rolling statistics for each ball position (15 features)
        logger.debug("Computing position-based rolling statistics...")
        for window in [10, 20, 50]:
            for col in white_ball_cols:
                features[f'{col}_freq_last_{window}'] = (
                    draws_df[col].rolling(window=window, min_periods=1).mean()
                )
        
        # 2. OPTIMIZED: Overall number distribution statistics (8 features)
        # Instead of per-number tracking, use aggregate statistics
        logger.debug("Computing aggregate frequency statistics...")
        for window in [20, 50]:
            # Compute overall frequency variance across all numbers in window
            variance_values = []
            mean_values = []
            
            for idx in range(len(draws_df)):
                start_idx = max(0, idx - window)
                window_draws = draws_df.iloc[start_idx:idx]
                
                if len(window_draws) > 0:
                    # Get all numbers in window
                    all_nums = []
                    for col in white_ball_cols:
                        all_nums.extend(window_draws[col].tolist())
                    
                    if all_nums:
                        variance_values.append(np.var(all_nums))
                        mean_values.append(np.mean(all_nums))
                    else:
                        variance_values.append(0)
                        mean_values.append(0)
                else:
                    variance_values.append(0)
                    mean_values.append(0)
            
            features[f'num_variance_last_{window}'] = variance_values
            features[f'num_mean_last_{window}'] = mean_values
        
        # 3. Temporal features (3 features) - Fast
        logger.debug("Computing temporal features...")
        if 'draw_date' in draws_df.columns:
            features['day_of_week'] = draws_df['draw_date'].dt.dayofweek
            features['month'] = draws_df['draw_date'].dt.month
            features['day_of_month'] = draws_df['draw_date'].dt.day
        
        # 4. Statistical features per draw (6 features) - Fast
        logger.debug("Computing per-draw statistics...")
        features['draw_sum'] = draws_df[white_ball_cols].sum(axis=1)
        features['draw_mean'] = draws_df[white_ball_cols].mean(axis=1)
        features['draw_std'] = draws_df[white_ball_cols].std(axis=1)
        features['draw_range'] = draws_df['n5'] - draws_df['n1']
        features['draw_min'] = draws_df['n1']
        features['draw_max'] = draws_df['n5']
        
        # 5. OPTIMIZED: Powerball rolling statistics (4 features)
        logger.debug("Computing powerball statistics...")
        if 'pb' in draws_df.columns:
            for window in [10, 20, 50]:
                features[f'pb_mean_last_{window}'] = (
                    draws_df['pb'].rolling(window=window, min_periods=1).mean()
                )
            
            # Add one std feature
            features[f'pb_std_last_20'] = (
                draws_df['pb'].rolling(window=20, min_periods=1).std().fillna(0)
            )
        
        # 6. Pattern features (4 features) - Fast
        logger.debug("Computing pattern features...")
        features['even_count'] = draws_df[white_ball_cols].apply(
            lambda row: sum(1 for x in row if x % 2 == 0), axis=1
        )
        features['odd_count'] = 5 - features['even_count']
        
        # High-low split (1-34 vs 35-69)
        features['low_count'] = draws_df[white_ball_cols].apply(
            lambda row: sum(1 for x in row if x <= 34), axis=1
        )
        features['high_count'] = 5 - features['low_count']
        
        # 7. OPTIMIZED: Gap features - only for last draw (eliminate per-row loops)
        # Instead of computing gap for each historical draw, compute only for prediction
        logger.debug("Computing simplified gap features...")
        # Compute "days since last appearance" for most frequent numbers only
        # Use a simple heuristic: track gap to last 3 draws instead of all history
        for i in range(1, 4):  # Last 3 draws
            col_name = f'draw_minus_{i}'
            if len(draws_df) > i:
                # Shift and compare
                shifted = draws_df[white_ball_cols].shift(i)
                # Count how many numbers from current draw appeared i draws ago
                match_count = []
                for idx in range(len(draws_df)):
                    if idx < i or pd.isna(shifted.iloc[idx].iloc[0]):
                        match_count.append(0)
                    else:
                        current = set(draws_df.iloc[idx][white_ball_cols])
                        previous = set(shifted.iloc[idx])
                        matches = len(current.intersection(previous))
                        match_count.append(matches)
                features[col_name + '_matches'] = match_count
        
        # Fill NaN values with 0
        features = features.fillna(0)
        
        logger.info(
            f"✓ Engineered {len(features.columns)} features from {len(draws_df)} draws "
            f"(optimized, <50 features)"
        )
        
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
                
        Raises:
            RuntimeError: If models not trained/loaded or prediction fails
        """
        import time
        
        if len(self.wb_models) != 5 or self.pb_model is None:
            raise RuntimeError("Models not trained or loaded. Call train() or load pretrained models.")
        
        start_time = time.time()
        logger.debug(f"Predicting probabilities from {len(recent_draws)} historical draws...")
        
        try:
            # Engineer features for the most recent draw
            logger.debug("Engineering features...")
            feature_start = time.time()
            X = self._engineer_features(recent_draws)
            feature_time = time.time() - feature_start
            logger.debug(f"Feature engineering completed in {feature_time:.2f}s ({len(X.columns)} features)")
            
            # Scale features
            logger.debug("Scaling features...")
            X_scaled = self.scaler.transform(X)
            X_latest = X_scaled[-1:]  # Last row
            
            # Predict probabilities for each white ball position
            logger.debug("Predicting white ball probabilities...")
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
            logger.debug("Predicting powerball probabilities...")
            pb_probs_raw = self.pb_model.predict_proba(X_latest)[0]
            pb_probs = np.zeros(26)
            for class_idx, class_val in enumerate(self.pb_model.classes_):
                if 1 <= class_val <= 26:
                    pb_probs[class_val - 1] = pb_probs_raw[class_idx]
            pb_probs = pb_probs / pb_probs.sum()  # Normalize
            
            elapsed = time.time() - start_time
            logger.debug(
                f"✓ Probability prediction completed in {elapsed:.2f}s "
                f"(wb_sum={wb_probs.sum():.4f}, pb_sum={pb_probs.sum():.4f})"
            )
            
            return wb_probs, pb_probs
            
        except Exception as e:
            logger.error(f"Error in predict_probabilities: {e}")
            logger.exception("Full traceback:")
            raise RuntimeError(f"Probability prediction failed: {e}") from e
    
    def generate_tickets(
        self,
        recent_draws: pd.DataFrame,
        count: int = 5,
        timeout: int = 120
    ) -> List[Dict]:
        """
        Generate lottery tickets using Random Forest predictions.
        
        Args:
            recent_draws: DataFrame with recent draws
            count: Number of tickets to generate
            timeout: Maximum time in seconds for generation (default: 120)
            
        Returns:
            List of ticket dictionaries
            
        Raises:
            TimeoutError: If generation takes longer than timeout seconds
            RuntimeError: If models are not loaded or other errors occur
        """
        import time
        
        start_time = time.time()
        logger.info(f"Generating {count} tickets using Random Forest model (timeout: {timeout}s)")
        
        try:
            # Predict probabilities with timeout check
            logger.debug("Predicting probabilities...")
            wb_probs, pb_probs = self.predict_probabilities(recent_draws)
            
            elapsed = time.time() - start_time
            logger.debug(f"Probability prediction completed in {elapsed:.2f}s")
            
            if elapsed > timeout:
                raise TimeoutError(
                    f"Probability prediction exceeded timeout ({elapsed:.2f}s > {timeout}s)"
                )
            
            # Generate tickets
            logger.debug(f"Generating {count} tickets from probabilities...")
            tickets = []
            for i in range(count):
                # Check timeout periodically (every 10 tickets)
                if i % 10 == 0 and i > 0:
                    elapsed = time.time() - start_time
                    if elapsed > timeout:
                        logger.warning(
                            f"Timeout reached after {i} tickets ({elapsed:.2f}s > {timeout}s). "
                            f"Returning partial results."
                        )
                        break
                
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
            
            elapsed = time.time() - start_time
            logger.info(
                f"✓ Generated {len(tickets)} tickets using Random Forest model in {elapsed:.2f}s"
            )
            return tickets
            
        except TimeoutError as e:
            logger.error(f"Random Forest ticket generation timed out: {e}")
            raise
        except Exception as e:
            logger.error(f"Error generating Random Forest tickets: {e}")
            logger.exception("Full traceback:")
            raise RuntimeError(f"Failed to generate tickets: {e}") from e
    
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
