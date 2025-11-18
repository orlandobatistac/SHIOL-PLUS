"""
SHIOL+ Unified Prediction Engine
=================================
Abstraction layer for different prediction implementations (v1/v2/hybrid).
Allows switching between implementations via PREDICTION_MODE environment variable.
"""

import os
import time
from typing import List, Dict, Optional
from loguru import logger


class UnifiedPredictionEngine:
    """
    Unified interface for ticket generation across different implementations.
    
    Modes:
        - v1: Current StrategyManager implementation (default)
        - v2: Future ML-based implementation (not implemented)
        - hybrid: Combination of v1 and v2 (not implemented)
    
    Usage:
        engine = UnifiedPredictionEngine()
        tickets = engine.generate_tickets(count=5)
    """
    
    def __init__(self, mode: str = None):
        """
        Initialize prediction engine with specified mode.
        
        Args:
            mode: Override for PREDICTION_MODE env var. One of: 'v1', 'v2', 'hybrid'
                  If None, reads from PREDICTION_MODE env var (default: 'v1')
        """
        # Get mode from parameter or environment variable
        self.mode = mode or os.getenv('PREDICTION_MODE', 'v1').lower()
        
        # Validate mode
        valid_modes = ['v1', 'v2', 'hybrid']
        if self.mode not in valid_modes:
            logger.warning(
                f"Invalid PREDICTION_MODE '{self.mode}', falling back to 'v1'. "
                f"Valid modes: {valid_modes}"
            )
            self.mode = 'v1'
        
        logger.info(f"UnifiedPredictionEngine initialized with mode: {self.mode}")
        
        # Initialize backend based on mode
        self._backend = None
        self._xgboost_available = None  # Lazy check for XGBoost availability
        self._generation_metrics = {
            'last_generation_time': None,
            'total_generations': 0,
            'avg_generation_time': 0.0
        }
        
        if self.mode == 'v1':
            self._initialize_v1_backend()
        elif self.mode == 'v2':
            self._initialize_v2_backend()
    
    def _initialize_v1_backend(self):
        """Initialize v1 backend (StrategyManager)"""
        from src.strategy_generators import StrategyManager
        self._backend = StrategyManager()
        logger.debug("v1 backend (StrategyManager) initialized")
    
    def _initialize_v2_backend(self):
        """
        Initialize v2 backend (ML-based Predictor) with lazy XGBoost loading.
        
        This method checks for XGBoost availability and initializes the ML predictor.
        If XGBoost is not available, it falls back to v1 mode.
        """
        # Lazy check for XGBoost availability
        if self._xgboost_available is None:
            try:
                import xgboost
                self._xgboost_available = True
                logger.debug("XGBoost is available for v2 mode")
            except ImportError:
                self._xgboost_available = False
                logger.warning(
                    "XGBoost not installed. Install with: pip install xgboost. "
                    "Falling back to v1 mode."
                )
        
        # If XGBoost is not available, fallback to v1
        if not self._xgboost_available:
            logger.warning("v2 mode requires XGBoost. Falling back to v1 mode.")
            self.mode = 'v1'
            self._initialize_v1_backend()
            return
        
        # Import and initialize ML Predictor (only if XGBoost is available)
        try:
            from src.predictor import Predictor
            self._backend = Predictor()
            logger.info("v2 backend (ML Predictor) initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize v2 backend: {e}")
            logger.warning("Falling back to v1 mode due to initialization error")
            self.mode = 'v1'
            self._initialize_v1_backend()
    
    def generate_tickets(self, count: int = 5) -> List[Dict]:
        """
        Generate prediction tickets using the configured implementation.
        
        Args:
            count: Number of tickets to generate (default 5)
            
        Returns:
            List of ticket dictionaries with format:
            {
                'white_balls': [int, int, int, int, int],  # sorted, 1-69
                'powerball': int,  # 1-26
                'strategy': str,   # strategy name
                'confidence': float  # 0.0-1.0
            }
        """
        if self.mode == 'v1':
            return self._generate_v1(count)
        elif self.mode == 'v2':
            return self._generate_v2(count)
        elif self.mode == 'hybrid':
            raise NotImplementedError(
                "hybrid mode (v1 + v2 combination) is not yet implemented. "
                "Use PREDICTION_MODE=v1 for current implementation."
            )
        else:
            # Should never reach here due to validation in __init__
            raise ValueError(f"Unknown mode: {self.mode}")
    
    def _generate_v1(self, count: int) -> List[Dict]:
        """
        Generate tickets using v1 implementation (StrategyManager).
        
        This delegates directly to StrategyManager.generate_balanced_tickets()
        to maintain identical behavior.
        """
        if self._backend is None:
            self._initialize_v1_backend()
        
        return self._backend.generate_balanced_tickets(count)
    
    def _generate_v2(self, count: int) -> List[Dict]:
        """
        Generate tickets using v2 implementation (ML-based Predictor).
        
        This method uses the ML predictor from src.predictor to generate
        high-quality predictions using XGBoost models. Includes time
        metrics tracking for performance monitoring.
        
        Args:
            count: Number of tickets to generate
            
        Returns:
            List of ticket dictionaries in standard format
        """
        # Track generation time
        start_time = time.time()
        
        try:
            # Initialize backend if not already done
            if self._backend is None:
                self._initialize_v2_backend()
            
            # Check if backend is still None (fallback occurred)
            if self._backend is None or self.mode != 'v2':
                logger.warning("v2 backend not available, using v1 fallback")
                return self._generate_v1(count)
            
            # Generate diverse plays using ML predictor
            logger.info(f"Generating {count} tickets using ML predictor (v2 mode)")
            
            # Use predict_diverse_plays for high-quality, diverse predictions
            ml_predictions = self._backend.predict_diverse_plays(
                num_plays=count,
                save_to_log=False
            )
            
            # Convert ML predictor format to standard ticket format
            tickets = []
            for pred in ml_predictions:
                ticket = {
                    'white_balls': pred.get('numbers', []),
                    'powerball': pred.get('powerball', 1),
                    'strategy': 'ml_predictor_v2',
                    'confidence': pred.get('confidence_score', 0.75)
                }
                
                # Validate ticket format
                if (len(ticket['white_balls']) == 5 and
                    all(1 <= n <= 69 for n in ticket['white_balls']) and
                    1 <= ticket['powerball'] <= 26):
                    tickets.append(ticket)
                else:
                    logger.warning(f"Invalid ticket generated by ML predictor: {ticket}")
            
            # Calculate and store metrics
            generation_time = time.time() - start_time
            self._update_generation_metrics(generation_time)
            
            logger.info(
                f"Generated {len(tickets)} tickets using v2 mode in {generation_time:.3f}s "
                f"(avg: {self._generation_metrics['avg_generation_time']:.3f}s)"
            )
            
            return tickets
            
        except Exception as e:
            generation_time = time.time() - start_time
            logger.error(
                f"Error in v2 generation after {generation_time:.3f}s: {e}. "
                "Falling back to v1 mode."
            )
            # Fallback to v1 if ML generation fails
            return self._generate_v1(count)
    
    def _update_generation_metrics(self, generation_time: float):
        """
        Update generation time metrics.
        
        Args:
            generation_time: Time taken for the generation in seconds
        """
        self._generation_metrics['last_generation_time'] = generation_time
        self._generation_metrics['total_generations'] += 1
        
        # Calculate running average
        total = self._generation_metrics['total_generations']
        avg = self._generation_metrics['avg_generation_time']
        self._generation_metrics['avg_generation_time'] = (
            (avg * (total - 1) + generation_time) / total
        )
    
    def get_mode(self) -> str:
        """Get current prediction mode"""
        return self.mode
    
    def get_backend_info(self) -> Dict:
        """
        Get information about the current backend.
        
        Returns:
            Dict with backend metadata including generation metrics
        """
        info = {
            'mode': self.mode,
            'backend_type': type(self._backend).__name__ if self._backend else None,
            'generation_metrics': self._generation_metrics.copy()
        }
        
        if self.mode == 'v1' and self._backend:
            # Include strategy weights for v1
            try:
                info['strategy_weights'] = self._backend.get_strategy_weights()
                info['available_strategies'] = list(self._backend.strategies.keys())
            except Exception as e:
                logger.warning(f"Could not get v1 backend info: {e}")
        
        elif self.mode == 'v2' and self._backend:
            # Include model info for v2
            try:
                info['model_info'] = self._backend.get_model_info()
                info['xgboost_available'] = self._xgboost_available
            except Exception as e:
                logger.warning(f"Could not get v2 backend info: {e}")
        
        return info
    
    def get_generation_metrics(self) -> Dict:
        """
        Get generation time metrics.
        
        Returns:
            Dict containing generation time statistics
        """
        return self._generation_metrics.copy()
    
    def get_strategy_manager(self):
        """
        Get direct access to StrategyManager (v1 mode only).
        
        This is provided for advanced use cases that need direct access
        to individual strategies (e.g., PLP v2 API).
        
        Returns:
            StrategyManager instance if mode is v1, None otherwise
            
        Raises:
            RuntimeError: If called in v2 or hybrid mode
        """
        if self.mode != 'v1':
            raise RuntimeError(
                f"get_strategy_manager() is only available in v1 mode, "
                f"current mode: {self.mode}"
            )
        
        if self._backend is None:
            self._initialize_v1_backend()
        
        return self._backend
