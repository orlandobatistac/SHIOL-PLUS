"""
SHIOL+ v2 - Modern Statistical Lottery Prediction Engine
==========================================================

Phase 1 Implementation:
- Temporal statistical models
- Momentum detection
- Gap/drought theory
- Pattern conformity
- Multi-dimensional scoring
- Analytics endpoint

This module provides an evolved prediction system while maintaining
full backward compatibility with v1 APIs.
"""

__version__ = "2.0.0-alpha"

from .statistical_core import (
    TemporalDecayModel,
    MomentumAnalyzer,
    GapAnalyzer,
    PatternEngine
)

from .strategies import (
    TemporalFrequencyStrategy,
    MomentumStrategy,
    GapTheoryStrategy,
    PatternStrategy,
    HybridSmartStrategy
)

from .scoring import ScoringEngine
from .analytics_api import analytics_router

__all__ = [
    # Statistical Core
    'TemporalDecayModel',
    'MomentumAnalyzer',
    'GapAnalyzer',
    'PatternEngine',
    
    # Strategies
    'TemporalFrequencyStrategy',
    'MomentumStrategy',
    'GapTheoryStrategy',
    'PatternStrategy',
    'HybridSmartStrategy',
    
    # Scoring
    'ScoringEngine',
    
    # API
    'analytics_router',
]
