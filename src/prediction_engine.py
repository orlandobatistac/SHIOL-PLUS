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
            return self._generate_hybrid(count)
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
    
    def _generate_hybrid(self, count: int) -> List[Dict]:
        """
        Generate tickets using hybrid mode (combination of v1 and v2).
        
        This method combines predictions from both v1 (StrategyManager) and v2 (ML Predictor)
        implementations using configurable weights. By default, it uses 70% v2 and 30% v1.
        
        Features:
        - Weighted combination: Allocates tickets based on HYBRID_V2_WEIGHT and HYBRID_V1_WEIGHT
        - Automatic fallback: If v2 fails, falls back to 100% v1
        - Deduplication: Removes duplicate tickets to ensure unique predictions
        - Preserves diversity: Maintains strategy diversity from both implementations
        
        Args:
            count: Total number of tickets to generate
            
        Returns:
            List of deduplicated ticket dictionaries from both v1 and v2 sources
        """
        # Get weights from environment variables or use defaults
        v2_weight = float(os.getenv('HYBRID_V2_WEIGHT', '0.7'))  # 70% v2 by default
        v1_weight = float(os.getenv('HYBRID_V1_WEIGHT', '0.3'))  # 30% v1 by default
        
        # Validate and normalize weights
        total_weight = v2_weight + v1_weight
        if total_weight <= 0:
            logger.warning("Invalid hybrid weights (sum <= 0), using default 70/30 split")
            v2_weight, v1_weight = 0.7, 0.3
            total_weight = 1.0
        else:
            # Normalize weights to sum to 1.0
            v2_weight = v2_weight / total_weight
            v1_weight = v1_weight / total_weight
        
        # Calculate ticket counts for each mode (ensure at least 1 from each if count >= 2)
        v2_count = max(1, int(count * v2_weight)) if count >= 2 else count
        v1_count = max(1, count - v2_count) if count >= 2 else 0
        
        # Adjust if total exceeds requested count
        if v2_count + v1_count > count:
            if v2_weight >= v1_weight:
                v1_count = count - v2_count
            else:
                v2_count = count - v1_count
        
        logger.info(
            f"Hybrid mode: generating {v2_count} v2 tickets ({v2_weight*100:.0f}%) "
            f"and {v1_count} v1 tickets ({v1_weight*100:.0f}%)"
        )
        
        # Track generation time
        start_time = time.time()
        all_tickets = []
        
        # Generate v2 tickets first (with fallback to v1 if fails)
        try:
            if v2_count > 0:
                logger.debug(f"Generating {v2_count} tickets from v2 (ML Predictor)")
                v2_tickets = self._generate_v2(v2_count)
                
                # Tag tickets with source for transparency
                for ticket in v2_tickets:
                    if 'source' not in ticket:
                        ticket['source'] = 'v2_ml'
                
                all_tickets.extend(v2_tickets)
                logger.debug(f"Successfully generated {len(v2_tickets)} v2 tickets")
        except Exception as e:
            logger.error(f"v2 generation failed in hybrid mode: {e}")
            logger.warning(f"Falling back: will generate {v2_count + v1_count} v1 tickets instead")
            # Fallback: generate all tickets from v1
            v1_count += v2_count
            v2_count = 0
        
        # Generate v1 tickets
        if v1_count > 0:
            logger.debug(f"Generating {v1_count} tickets from v1 (StrategyManager)")
            try:
                v1_tickets = self._generate_v1(v1_count)
                
                # Tag tickets with source for transparency
                for ticket in v1_tickets:
                    if 'source' not in ticket:
                        ticket['source'] = 'v1_strategy'
                
                all_tickets.extend(v1_tickets)
                logger.debug(f"Successfully generated {len(v1_tickets)} v1 tickets")
            except Exception as e:
                logger.error(f"v1 generation failed in hybrid mode: {e}")
                # If even v1 fails, we're in trouble - return whatever we have
        
        # Deduplication: Remove duplicate tickets based on white_balls + powerball
        deduplicated_tickets = self._deduplicate_tickets(all_tickets)
        
        # Calculate and store metrics
        generation_time = time.time() - start_time
        self._update_generation_metrics(generation_time)
        
        logger.info(
            f"Hybrid mode generated {len(all_tickets)} tickets "
            f"({len(deduplicated_tickets)} after deduplication) in {generation_time:.3f}s"
        )
        
        return deduplicated_tickets
    
    def _deduplicate_tickets(self, tickets: List[Dict]) -> List[Dict]:
        """
        Remove duplicate tickets based on white_balls and powerball combination.
        
        Preserves the first occurrence of each unique ticket, maintaining
        the diversity and confidence scores from the original generation.
        
        Args:
            tickets: List of ticket dictionaries to deduplicate
            
        Returns:
            List of unique tickets (first occurrence preserved)
        """
        seen = set()
        deduplicated = []
        
        for ticket in tickets:
            # Create a hashable key from white_balls and powerball
            white_balls = tuple(sorted(ticket.get('white_balls', [])))
            powerball = ticket.get('powerball', 0)
            key = (white_balls, powerball)
            
            if key not in seen:
                seen.add(key)
                deduplicated.append(ticket)
            else:
                logger.debug(
                    f"Removed duplicate ticket: {list(white_balls)} + PB {powerball}"
                )
        
        return deduplicated
    
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
