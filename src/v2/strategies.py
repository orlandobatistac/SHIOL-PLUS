"""
SHIOL+ v2 - Strategy Layer
===========================

Modern strategies using statistical core components:
- Temporal Frequency Strategy (TFS)
- Momentum Strategy (MS)
- Gap/Drought Strategy (GTS)
- Pattern Strategy (PS)
- Hybrid Smart Strategy (HSS)

All strategies inherit from v1 BaseStrategy for compatibility.
"""

import random
import numpy as np
from typing import List, Dict
from loguru import logger

from src.strategy_generators import BaseStrategy
from .statistical_core import (
    TemporalDecayModel,
    MomentumAnalyzer,
    GapAnalyzer,
    PatternEngine
)


class TemporalFrequencyStrategy(BaseStrategy):
    """
    Temporal Frequency Strategy (TFS)
    
    Generates tickets using recency-weighted probability pools.
    Recent draws have exponentially higher influence than older draws.
    """
    
    def __init__(self, decay_factor: float = 0.05):
        """
        Initialize TFS.
        
        Args:
            decay_factor: Exponential decay rate for temporal weighting
        """
        super().__init__("temporal_frequency_v2")
        self.temporal_model = TemporalDecayModel(decay_factor=decay_factor)
        self.weights = None
        
        # Calculate weights on init
        if not self.draws_df.empty:
            self.weights = self.temporal_model.calculate_weights(self.draws_df)
            logger.info(f"{self.name}: Temporal weights calculated (window={self.weights.window_size})")
    
    def generate(self, count: int = 5) -> List[Dict]:
        """Generate tickets using temporal weighting"""
        if self.weights is None or self.draws_df.empty:
            logger.warning(f"{self.name}: No weights available, using random fallback")
            return self._random_fallback(count)
        
        tickets = []
        
        for _ in range(count):
            try:
                # Sample white balls using temporal weights
                white_balls = sorted(np.random.choice(
                    range(1, 70),
                    size=5,
                    replace=False,
                    p=self.weights.white_ball_weights
                ).tolist())
                
                # Sample powerball using temporal weights
                powerball = int(np.random.choice(
                    range(1, 27),
                    p=self.weights.powerball_weights
                ))
                
                tickets.append({
                    'white_balls': white_balls,
                    'powerball': powerball,
                    'strategy': self.name,
                    'confidence': 0.78
                })
                
            except Exception as e:
                logger.error(f"{self.name}: Generation failed: {e}")
                tickets.extend(self._random_fallback(1))
        
        logger.debug(f"{self.name}: Generated {count} tickets")
        return tickets
    
    def _random_fallback(self, count: int) -> List[Dict]:
        """Fallback to random generation"""
        tickets = []
        for _ in range(count):
            tickets.append({
                'white_balls': sorted(random.sample(range(1, 70), 5)),
                'powerball': random.randint(1, 26),
                'strategy': self.name,
                'confidence': 0.50
            })
        return tickets


class MomentumStrategy(BaseStrategy):
    """
    Momentum Strategy (MS)
    
    Generates tickets using numbers with strong positive momentum
    (rising trends in recent draws).
    """
    
    def __init__(self, short_window: int = 10, long_window: int = 50):
        """
        Initialize Momentum Strategy.
        
        Args:
            short_window: Recent draws for momentum calculation
            long_window: Baseline draws for comparison
        """
        super().__init__("momentum_v2")
        self.momentum_analyzer = MomentumAnalyzer(short_window, long_window)
        self.momentum = None
        
        # Calculate momentum on init
        if not self.draws_df.empty:
            self.momentum = self.momentum_analyzer.analyze(self.draws_df)
            logger.info(f"{self.name}: Momentum analyzed (hot={len(self.momentum.hot_numbers)})")
    
    def generate(self, count: int = 5) -> List[Dict]:
        """Generate tickets favoring high-momentum numbers"""
        if self.momentum is None or self.draws_df.empty:
            logger.warning(f"{self.name}: No momentum data, using random fallback")
            return self._random_fallback(count)
        
        tickets = []
        
        for _ in range(count):
            try:
                # Convert momentum to positive weights (shift to [0, inf))
                shifted_momentum = self.momentum.white_ball_momentum - self.momentum.white_ball_momentum.min()
                
                # Add small epsilon to avoid zero weights
                shifted_momentum += 0.01
                
                # Normalize to probabilities
                weights = shifted_momentum / shifted_momentum.sum()
                
                # Sample white balls favoring high momentum
                white_balls = sorted(np.random.choice(
                    range(1, 70),
                    size=5,
                    replace=False,
                    p=weights
                ).tolist())
                
                # Powerball with momentum weighting
                pb_shifted = self.momentum.powerball_momentum - self.momentum.powerball_momentum.min() + 0.01
                pb_weights = pb_shifted / pb_shifted.sum()
                
                powerball = int(np.random.choice(range(1, 27), p=pb_weights))
                
                tickets.append({
                    'white_balls': white_balls,
                    'powerball': powerball,
                    'strategy': self.name,
                    'confidence': 0.72
                })
                
            except Exception as e:
                logger.error(f"{self.name}: Generation failed: {e}")
                tickets.extend(self._random_fallback(1))
        
        logger.debug(f"{self.name}: Generated {count} tickets")
        return tickets
    
    def _random_fallback(self, count: int) -> List[Dict]:
        """Fallback to random generation"""
        tickets = []
        for _ in range(count):
            tickets.append({
                'white_balls': sorted(random.sample(range(1, 70), 5)),
                'powerball': random.randint(1, 26),
                'strategy': self.name,
                'confidence': 0.50
            })
        return tickets


class GapTheoryStrategy(BaseStrategy):
    """
    Gap/Drought Theory Strategy (GTS)
    
    Generates tickets using numbers that haven't appeared recently
    (overdue numbers based on gap analysis and Poisson return probability).
    """
    
    def __init__(self):
        """Initialize Gap Theory Strategy"""
        super().__init__("gap_theory_v2")
        self.gap_analyzer = GapAnalyzer()
        self.gaps = None
        
        # Calculate gaps on init
        if not self.draws_df.empty:
            self.gaps = self.gap_analyzer.analyze(self.draws_df)
            logger.info(f"{self.name}: Gap analysis complete (overdue={len(self.gaps.overdue_numbers)})")
    
    def generate(self, count: int = 5) -> List[Dict]:
        """Generate tickets favoring overdue numbers"""
        if self.gaps is None or self.draws_df.empty:
            logger.warning(f"{self.name}: No gap data, using random fallback")
            return self._random_fallback(count)
        
        tickets = []
        
        for _ in range(count):
            try:
                # Use return probabilities as sampling weights
                white_balls = sorted(np.random.choice(
                    range(1, 70),
                    size=5,
                    replace=False,
                    p=self.gaps.white_ball_probabilities
                ).tolist())
                
                # Powerball with gap-based weighting
                powerball = int(np.random.choice(
                    range(1, 27),
                    p=self.gaps.powerball_probabilities
                ))
                
                tickets.append({
                    'white_balls': white_balls,
                    'powerball': powerball,
                    'strategy': self.name,
                    'confidence': 0.68
                })
                
            except Exception as e:
                logger.error(f"{self.name}: Generation failed: {e}")
                tickets.extend(self._random_fallback(1))
        
        logger.debug(f"{self.name}: Generated {count} tickets")
        return tickets
    
    def _random_fallback(self, count: int) -> List[Dict]:
        """Fallback to random generation"""
        tickets = []
        for _ in range(count):
            tickets.append({
                'white_balls': sorted(random.sample(range(1, 70), 5)),
                'powerball': random.randint(1, 26),
                'strategy': self.name,
                'confidence': 0.50
            })
        return tickets


class PatternStrategy(BaseStrategy):
    """
    Pattern Strategy (PS)
    
    Generates tickets that conform to historical pattern distributions:
    - Odd/even balance
    - High/low distribution
    - Sum ranges
    - Tens-decade clustering
    """
    
    def __init__(self):
        """Initialize Pattern Strategy"""
        super().__init__("pattern_v2")
        self.pattern_engine = PatternEngine()
        self.patterns = None
        
        # Analyze patterns on init
        if not self.draws_df.empty:
            self.patterns = self.pattern_engine.analyze(self.draws_df)
            logger.info(f"{self.name}: Pattern analysis complete")
    
    def generate(self, count: int = 5) -> List[Dict]:
        """Generate tickets conforming to historical patterns"""
        if self.patterns is None or self.draws_df.empty:
            logger.warning(f"{self.name}: No pattern data, using random fallback")
            return self._random_fallback(count)
        
        tickets = []
        
        for _ in range(count):
            # Generate with pattern constraints
            ticket = self._generate_pattern_conforming_ticket()
            tickets.append(ticket)
        
        logger.debug(f"{self.name}: Generated {count} tickets")
        return tickets
    
    def _generate_pattern_conforming_ticket(self) -> Dict:
        """Generate a single ticket conforming to patterns"""
        max_attempts = 100
        
        for attempt in range(max_attempts):
            # Generate random ticket
            white_balls = sorted(random.sample(range(1, 70), 5))
            
            # Check pattern conformity
            conformity_score = self.pattern_engine.score_pattern_conformity(white_balls)
            
            # Accept if conformity is high (>0.5)
            if conformity_score > 0.5:
                powerball = random.randint(1, 26)
                return {
                    'white_balls': white_balls,
                    'powerball': powerball,
                    'strategy': self.name,
                    'confidence': min(0.65 + conformity_score * 0.2, 0.85)
                }
        
        # Fallback if no conforming ticket found
        logger.warning(f"{self.name}: Could not find conforming ticket in {max_attempts} attempts")
        return {
            'white_balls': sorted(random.sample(range(1, 70), 5)),
            'powerball': random.randint(1, 26),
            'strategy': self.name,
            'confidence': 0.50
        }
    
    def _random_fallback(self, count: int) -> List[Dict]:
        """Fallback to random generation"""
        tickets = []
        for _ in range(count):
            tickets.append({
                'white_balls': sorted(random.sample(range(1, 70), 5)),
                'powerball': random.randint(1, 26),
                'strategy': self.name,
                'confidence': 0.50
            })
        return tickets


class HybridSmartStrategy(BaseStrategy):
    """
    Hybrid Smart Strategy (HSS)
    
    Combines multiple analytical dimensions:
    - 2 hot numbers (temporal decay)
    - 1 momentum number (rising trend)
    - 1 cold number (gap theory)
    - 1 balanced number (pattern conformity)
    
    Must pass pattern constraints for conformity.
    """
    
    def __init__(self):
        """Initialize Hybrid Smart Strategy"""
        super().__init__("hybrid_smart_v2")
        
        # Initialize all analytical components
        self.temporal_model = TemporalDecayModel(decay_factor=0.05)
        self.momentum_analyzer = MomentumAnalyzer(short_window=10, long_window=50)
        self.gap_analyzer = GapAnalyzer()
        self.pattern_engine = PatternEngine()
        
        # Analyze on init
        if not self.draws_df.empty:
            self.weights = self.temporal_model.calculate_weights(self.draws_df)
            self.momentum = self.momentum_analyzer.analyze(self.draws_df)
            self.gaps = self.gap_analyzer.analyze(self.draws_df)
            self.patterns = self.pattern_engine.analyze(self.draws_df)
            logger.info(f"{self.name}: All analytical components initialized")
        else:
            self.weights = None
            self.momentum = None
            self.gaps = None
            self.patterns = None
    
    def generate(self, count: int = 5) -> List[Dict]:
        """Generate hybrid tickets combining multiple strategies"""
        if any(x is None for x in [self.weights, self.momentum, self.gaps, self.patterns]):
            logger.warning(f"{self.name}: Incomplete analysis, using random fallback")
            return self._random_fallback(count)
        
        tickets = []
        
        for _ in range(count):
            ticket = self._generate_hybrid_ticket()
            tickets.append(ticket)
        
        logger.debug(f"{self.name}: Generated {count} tickets")
        return tickets
    
    def _generate_hybrid_ticket(self) -> Dict:
        """Generate a single hybrid ticket"""
        max_attempts = 50
        
        for attempt in range(max_attempts):
            white_balls = []
            
            try:
                # 1. Pick 2 hot numbers (high temporal weight)
                hot_candidates = self._get_top_temporal_numbers(5)
                hot_selected = random.sample(hot_candidates, min(2, len(hot_candidates)))
                white_balls.extend(hot_selected)
                
                # 2. Pick 1 momentum number (positive momentum)
                if self.momentum.hot_numbers:
                    momentum_pool = [n for n in self.momentum.hot_numbers if n not in white_balls]
                    if momentum_pool:
                        white_balls.append(random.choice(momentum_pool))
                
                # 3. Pick 1 cold number (high gap)
                if len(white_balls) < 5:
                    cold_pool = [n for n in self.gaps.overdue_numbers[:10] if n not in white_balls]
                    if cold_pool:
                        white_balls.append(random.choice(cold_pool))
                
                # 4. Fill remaining with balanced selection
                while len(white_balls) < 5:
                    available = [n for n in range(1, 70) if n not in white_balls]
                    if not available:
                        break
                    white_balls.append(random.choice(available))
                
                # Ensure we have exactly 5 unique numbers
                if len(white_balls) != 5 or len(set(white_balls)) != 5:
                    continue
                
                white_balls = sorted(white_balls)
                
                # Check pattern conformity
                conformity_score = self.pattern_engine.score_pattern_conformity(white_balls)
                
                # Accept if conformity is reasonable (>0.4)
                if conformity_score > 0.4:
                    # Powerball: blend temporal and gap weights
                    pb_weights = (self.weights.powerball_weights + self.gaps.powerball_probabilities) / 2
                    pb_weights = pb_weights / pb_weights.sum()
                    
                    powerball = int(np.random.choice(range(1, 27), p=pb_weights))
                    
                    return {
                        'white_balls': white_balls,
                        'powerball': powerball,
                        'strategy': self.name,
                        'confidence': 0.80
                    }
                    
            except Exception as e:
                logger.debug(f"{self.name}: Attempt {attempt} failed: {e}")
                continue
        
        # Fallback
        logger.warning(f"{self.name}: Could not generate hybrid ticket, using fallback")
        return {
            'white_balls': sorted(random.sample(range(1, 70), 5)),
            'powerball': random.randint(1, 26),
            'strategy': self.name,
            'confidence': 0.55
        }
    
    def _get_top_temporal_numbers(self, top_n: int) -> List[int]:
        """Get numbers with highest temporal weights"""
        indices = np.argsort(self.weights.white_ball_weights)[::-1][:top_n]
        return [int(i + 1) for i in indices]
    
    def _random_fallback(self, count: int) -> List[Dict]:
        """Fallback to random generation"""
        tickets = []
        for _ in range(count):
            tickets.append({
                'white_balls': sorted(random.sample(range(1, 70), 5)),
                'powerball': random.randint(1, 26),
                'strategy': self.name,
                'confidence': 0.50
            })
        return tickets
