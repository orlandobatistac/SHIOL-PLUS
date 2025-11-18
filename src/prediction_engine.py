"""
SHIOL+ Unified Prediction Engine
=================================
Abstraction layer for different prediction implementations (v1/v2/hybrid).
Allows switching between implementations via PREDICTION_MODE environment variable.
"""

import os
from typing import List, Dict
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
        if self.mode == 'v1':
            self._initialize_v1_backend()
    
    def _initialize_v1_backend(self):
        """Initialize v1 backend (StrategyManager)"""
        from src.strategy_generators import StrategyManager
        self._backend = StrategyManager()
        logger.debug("v1 backend (StrategyManager) initialized")
    
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
            
        Raises:
            NotImplementedError: If mode is v2 or hybrid (not yet implemented)
        """
        if self.mode == 'v1':
            return self._generate_v1(count)
        elif self.mode == 'v2':
            raise NotImplementedError(
                "v2 mode (ML-based prediction) is not yet implemented. "
                "Use PREDICTION_MODE=v1 for current implementation."
            )
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
    
    def get_mode(self) -> str:
        """Get current prediction mode"""
        return self.mode
    
    def get_backend_info(self) -> Dict:
        """
        Get information about the current backend.
        
        Returns:
            Dict with backend metadata
        """
        info = {
            'mode': self.mode,
            'backend_type': type(self._backend).__name__ if self._backend else None
        }
        
        if self.mode == 'v1' and self._backend:
            # Include strategy weights for v1
            try:
                info['strategy_weights'] = self._backend.get_strategy_weights()
                info['available_strategies'] = list(self._backend.strategies.keys())
            except Exception as e:
                logger.warning(f"Could not get v1 backend info: {e}")
        
        return info
    
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
