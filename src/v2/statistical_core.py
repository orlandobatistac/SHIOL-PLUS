"""
SHIOL+ v2 - Statistical Core Module
====================================

Provides temporal analysis, momentum detection, gap theory, and pattern analysis
for intelligent lottery prediction.

Components:
- TemporalDecayModel: Exponential recency weighting
- MomentumAnalyzer: Trend detection (rising/falling numbers)
- GapAnalyzer: Drought theory with return probability
- PatternEngine: Conformity analysis (odd/even, ranges, sum, clustering)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from loguru import logger
from datetime import datetime, timedelta


@dataclass
class TemporalWeights:
    """Container for temporal weights of each number"""
    white_ball_weights: np.ndarray  # Shape: (69,)
    powerball_weights: np.ndarray   # Shape: (26,)
    decay_factor: float
    window_size: int


class TemporalDecayModel:
    """
    Exponential temporal decay model for recency-based number weighting.
    
    Recent draws have higher influence than older draws, with configurable
    decay rate and adaptive windowing based on variance.
    
    Formula: weight(t) = exp(-λ * (current_draw - t))
    where λ is the decay factor and t is the draw index.
    """
    
    def __init__(self, decay_factor: float = 0.05, adaptive_window: bool = True):
        """
        Initialize temporal decay model.
        
        Args:
            decay_factor: Exponential decay rate (higher = faster decay)
            adaptive_window: If True, adjust window based on variance
        """
        self.decay_factor = decay_factor
        self.adaptive_window = adaptive_window
        logger.info(f"TemporalDecayModel initialized (decay={decay_factor}, adaptive={adaptive_window})")
    
    def calculate_weights(self, draws_df: pd.DataFrame) -> TemporalWeights:
        """
        Calculate temporal weights for all numbers based on draw history.
        
        Args:
            draws_df: DataFrame with columns [draw_date, n1, n2, n3, n4, n5, pb]
            
        Returns:
            TemporalWeights object with weighted probabilities
        """
        if draws_df.empty:
            logger.warning("No draws available, using uniform weights")
            return TemporalWeights(
                white_ball_weights=np.ones(69) / 69,
                powerball_weights=np.ones(26) / 26,
                decay_factor=self.decay_factor,
                window_size=0
            )
        
        # Determine window size
        window_size = self._get_adaptive_window(draws_df) if self.adaptive_window else len(draws_df)
        recent_draws = draws_df.tail(window_size)
        
        # Calculate temporal weights for white balls
        wb_weights = self._calculate_white_ball_weights(recent_draws)
        
        # Calculate temporal weights for powerball (current era only)
        pb_weights = self._calculate_powerball_weights(recent_draws)
        
        logger.debug(f"Temporal weights calculated (window={window_size}, decay={self.decay_factor})")
        
        return TemporalWeights(
            white_ball_weights=wb_weights,
            powerball_weights=pb_weights,
            decay_factor=self.decay_factor,
            window_size=window_size
        )
    
    def _get_adaptive_window(self, draws_df: pd.DataFrame) -> int:
        """
        Calculate adaptive window size based on variance in recent draws.
        
        Higher variance → shorter window (recent patterns dominate)
        Lower variance → longer window (more historical data)
        """
        if len(draws_df) < 20:
            return len(draws_df)
        
        # Analyze variance in last 50 draws
        recent = draws_df.tail(50)
        
        # Calculate variance in number frequencies
        all_numbers = []
        for _, draw in recent.iterrows():
            all_numbers.extend([draw['n1'], draw['n2'], draw['n3'], draw['n4'], draw['n5']])
        
        variance = np.var(all_numbers)
        
        # Map variance to window size (50-200 draws)
        # High variance (>400) → 50 draws
        # Low variance (<200) → 200 draws
        if variance > 400:
            window = 50
        elif variance < 200:
            window = 200
        else:
            # Linear interpolation
            window = int(200 - (variance - 200) * (150 / 200))
        
        return min(window, len(draws_df))
    
    def _calculate_white_ball_weights(self, draws_df: pd.DataFrame) -> np.ndarray:
        """Calculate exponentially decayed weights for white balls (1-69)"""
        weights = np.zeros(69)
        n_draws = len(draws_df)
        
        for idx, (_, draw) in enumerate(draws_df.iterrows()):
            # Time distance from most recent draw (0 = most recent)
            time_distance = n_draws - idx - 1
            
            # Exponential decay weight
            decay_weight = np.exp(-self.decay_factor * time_distance)
            
            # Add weight to each number in this draw
            for num in [draw['n1'], draw['n2'], draw['n3'], draw['n4'], draw['n5']]:
                if 1 <= num <= 69:
                    weights[num - 1] += decay_weight
        
        # Normalize to probabilities
        total = weights.sum()
        if total > 0:
            weights = weights / total
        else:
            weights = np.ones(69) / 69
        
        return weights
    
    def _calculate_powerball_weights(self, draws_df: pd.DataFrame) -> np.ndarray:
        """Calculate exponentially decayed weights for powerball (1-26, current era only)"""
        weights = np.zeros(26)
        
        # Filter to current era (pb between 1-26)
        current_era = draws_df[(draws_df['pb'] >= 1) & (draws_df['pb'] <= 26)]
        
        if current_era.empty:
            logger.warning("No current-era draws for PB weights, using uniform")
            return np.ones(26) / 26
        
        n_draws = len(current_era)
        
        for idx, (_, draw) in enumerate(current_era.iterrows()):
            time_distance = n_draws - idx - 1
            decay_weight = np.exp(-self.decay_factor * time_distance)
            
            pb = int(draw['pb'])
            if 1 <= pb <= 26:
                weights[pb - 1] += decay_weight
        
        # Normalize
        total = weights.sum()
        if total > 0:
            weights = weights / total
        else:
            weights = np.ones(26) / 26
        
        return weights


@dataclass
class MomentumScores:
    """Container for momentum analysis results"""
    white_ball_momentum: np.ndarray  # Shape: (69,) - positive = rising, negative = falling
    powerball_momentum: np.ndarray   # Shape: (26,)
    hot_numbers: List[int]  # Numbers with strongest positive momentum
    cold_numbers: List[int]  # Numbers with strongest negative momentum
    window_size: int


class MomentumAnalyzer:
    """
    Detects rising and falling trends in number frequencies.
    
    Uses short-term vs long-term frequency comparison to identify
    numbers gaining or losing momentum.
    
    Momentum = (recent_frequency - historical_frequency) / historical_frequency
    """
    
    def __init__(self, short_window: int = 10, long_window: int = 50):
        """
        Initialize momentum analyzer.
        
        Args:
            short_window: Number of recent draws for short-term frequency
            long_window: Number of draws for long-term baseline
        """
        self.short_window = short_window
        self.long_window = long_window
        logger.info(f"MomentumAnalyzer initialized (short={short_window}, long={long_window})")
    
    def analyze(self, draws_df: pd.DataFrame) -> MomentumScores:
        """
        Analyze momentum for all numbers.
        
        Args:
            draws_df: DataFrame with draw history
            
        Returns:
            MomentumScores with momentum values for each number
        """
        if len(draws_df) < self.long_window:
            logger.warning(f"Insufficient draws for momentum analysis (need {self.long_window}, have {len(draws_df)})")
            return MomentumScores(
                white_ball_momentum=np.zeros(69),
                powerball_momentum=np.zeros(26),
                hot_numbers=[],
                cold_numbers=[],
                window_size=len(draws_df)
            )
        
        # Calculate white ball momentum
        wb_momentum = self._calculate_white_ball_momentum(draws_df)
        
        # Calculate powerball momentum (current era)
        pb_momentum = self._calculate_powerball_momentum(draws_df)
        
        # Identify hot/cold numbers (top 10 momentum)
        hot_numbers = self._get_top_momentum_numbers(wb_momentum, top_n=10, direction='hot')
        cold_numbers = self._get_top_momentum_numbers(wb_momentum, top_n=10, direction='cold')
        
        logger.debug(f"Momentum analysis complete (hot={len(hot_numbers)}, cold={len(cold_numbers)})")
        
        return MomentumScores(
            white_ball_momentum=wb_momentum,
            powerball_momentum=pb_momentum,
            hot_numbers=hot_numbers,
            cold_numbers=cold_numbers,
            window_size=self.long_window
        )
    
    def _calculate_white_ball_momentum(self, draws_df: pd.DataFrame) -> np.ndarray:
        """Calculate momentum scores for white balls (1-69)"""
        # Short-term frequency (recent draws)
        short_freq = self._calculate_frequency(draws_df.tail(self.short_window), 69)
        
        # Long-term frequency (baseline)
        long_freq = self._calculate_frequency(draws_df.tail(self.long_window), 69)
        
        # Momentum = (short - long) / long (percentage change)
        # Avoid division by zero
        momentum = np.zeros(69)
        for i in range(69):
            if long_freq[i] > 0:
                momentum[i] = (short_freq[i] - long_freq[i]) / long_freq[i]
            elif short_freq[i] > 0:
                momentum[i] = 1.0  # Appeared recently but not historically
        
        return momentum
    
    def _calculate_powerball_momentum(self, draws_df: pd.DataFrame) -> np.ndarray:
        """Calculate momentum scores for powerball (1-26, current era)"""
        # Filter to current era
        current_era = draws_df[(draws_df['pb'] >= 1) & (draws_df['pb'] <= 26)]
        
        if len(current_era) < self.long_window:
            return np.zeros(26)
        
        short_freq = self._calculate_pb_frequency(current_era.tail(self.short_window))
        long_freq = self._calculate_pb_frequency(current_era.tail(self.long_window))
        
        momentum = np.zeros(26)
        for i in range(26):
            if long_freq[i] > 0:
                momentum[i] = (short_freq[i] - long_freq[i]) / long_freq[i]
            elif short_freq[i] > 0:
                momentum[i] = 1.0
        
        return momentum
    
    def _calculate_frequency(self, draws_df: pd.DataFrame, max_num: int) -> np.ndarray:
        """Calculate normalized frequency for white balls"""
        freq = np.zeros(max_num)
        
        for _, draw in draws_df.iterrows():
            for num in [draw['n1'], draw['n2'], draw['n3'], draw['n4'], draw['n5']]:
                if 1 <= num <= max_num:
                    freq[num - 1] += 1
        
        # Normalize to [0, 1]
        total = freq.sum()
        if total > 0:
            freq = freq / total
        
        return freq
    
    def _calculate_pb_frequency(self, draws_df: pd.DataFrame) -> np.ndarray:
        """Calculate normalized frequency for powerball"""
        freq = np.zeros(26)
        
        for _, draw in draws_df.iterrows():
            pb = int(draw['pb'])
            if 1 <= pb <= 26:
                freq[pb - 1] += 1
        
        total = freq.sum()
        if total > 0:
            freq = freq / total
        
        return freq
    
    def _get_top_momentum_numbers(self, momentum: np.ndarray, top_n: int, direction: str) -> List[int]:
        """Get numbers with highest momentum (hot) or lowest momentum (cold)"""
        if direction == 'hot':
            # Sort descending (highest momentum first)
            indices = np.argsort(momentum)[::-1][:top_n]
        else:  # cold
            # Sort ascending (lowest/most negative momentum first)
            indices = np.argsort(momentum)[:top_n]
        
        # Convert to 1-indexed numbers
        return [int(i + 1) for i in indices]


@dataclass
class GapAnalysis:
    """Container for gap/drought analysis results"""
    white_ball_gaps: np.ndarray  # Shape: (69,) - draws since last appearance
    powerball_gaps: np.ndarray   # Shape: (26,)
    white_ball_probabilities: np.ndarray  # Return probability based on Poisson
    powerball_probabilities: np.ndarray
    overdue_numbers: List[int]  # Numbers with longest gaps
    


class GapAnalyzer:
    """
    Gap/Drought Theory analyzer.
    
    Calculates how long each number has been absent and estimates
    return probability using Poisson distribution.
    
    Theory: Numbers that haven't appeared in a while have increasing
    probability of appearing (regression to the mean).
    """
    
    def __init__(self):
        """Initialize gap analyzer"""
        logger.info("GapAnalyzer initialized")
    
    def analyze(self, draws_df: pd.DataFrame) -> GapAnalysis:
        """
        Analyze gaps for all numbers.
        
        Args:
            draws_df: DataFrame with draw history (sorted by date, oldest first)
            
        Returns:
            GapAnalysis with gap statistics and return probabilities
        """
        if draws_df.empty:
            logger.warning("No draws available for gap analysis")
            return GapAnalysis(
                white_ball_gaps=np.zeros(69),
                powerball_gaps=np.zeros(26),
                white_ball_probabilities=np.ones(69) / 69,
                powerball_probabilities=np.ones(26) / 26,
                overdue_numbers=[]
            )
        
        # Calculate gaps
        wb_gaps = self._calculate_white_ball_gaps(draws_df)
        pb_gaps = self._calculate_powerball_gaps(draws_df)
        
        # Calculate return probabilities (Poisson-based)
        wb_probs = self._calculate_return_probabilities(wb_gaps, expected_freq=5/69)
        pb_probs = self._calculate_return_probabilities(pb_gaps, expected_freq=1/26)
        
        # Identify overdue numbers (top 15 by gap)
        overdue = self._get_overdue_numbers(wb_gaps, top_n=15)
        
        logger.debug(f"Gap analysis complete (overdue={len(overdue)})")
        
        return GapAnalysis(
            white_ball_gaps=wb_gaps,
            powerball_gaps=pb_gaps,
            white_ball_probabilities=wb_probs,
            powerball_probabilities=pb_probs,
            overdue_numbers=overdue
        )
    
    def _calculate_white_ball_gaps(self, draws_df: pd.DataFrame) -> np.ndarray:
        """Calculate gaps (draws since last appearance) for white balls"""
        gaps = np.full(69, len(draws_df))  # Initialize with max gap
        
        # Iterate from most recent to oldest
        for idx, (_, draw) in enumerate(reversed(list(draws_df.iterrows()))):
            for num in [draw['n1'], draw['n2'], draw['n3'], draw['n4'], draw['n5']]:
                if 1 <= num <= 69:
                    # If not yet recorded, record this gap
                    if gaps[num - 1] == len(draws_df):
                        gaps[num - 1] = idx
        
        return gaps
    
    def _calculate_powerball_gaps(self, draws_df: pd.DataFrame) -> np.ndarray:
        """Calculate gaps for powerball (current era only)"""
        current_era = draws_df[(draws_df['pb'] >= 1) & (draws_df['pb'] <= 26)]
        
        if current_era.empty:
            return np.zeros(26)
        
        gaps = np.full(26, len(current_era))
        
        for idx, (_, draw) in enumerate(reversed(list(current_era.iterrows()))):
            pb = int(draw['pb'])
            if 1 <= pb <= 26:
                if gaps[pb - 1] == len(current_era):
                    gaps[pb - 1] = idx
        
        return gaps
    
    def _calculate_return_probabilities(self, gaps: np.ndarray, expected_freq: float) -> np.ndarray:
        """
        Calculate return probability using Poisson distribution.
        
        P(return) = 1 - exp(-λ * gap)
        where λ is the expected frequency per draw
        """
        # Poisson-based return probability
        # Higher gap → higher probability of appearing soon
        probabilities = 1 - np.exp(-expected_freq * gaps)
        
        # Normalize to sum to 1.0
        total = probabilities.sum()
        if total > 0:
            probabilities = probabilities / total
        else:
            probabilities = np.ones(len(gaps)) / len(gaps)
        
        return probabilities
    
    def _get_overdue_numbers(self, gaps: np.ndarray, top_n: int) -> List[int]:
        """Get numbers with longest gaps (most overdue)"""
        # Sort by gap descending
        indices = np.argsort(gaps)[::-1][:top_n]
        return [int(i + 1) for i in indices]


@dataclass
class PatternAnalysis:
    """Container for pattern analysis results"""
    odd_even_distribution: Dict[str, float]  # Historical distribution
    high_low_distribution: Dict[str, float]
    sum_range: Tuple[float, float]  # (mean, std)
    tens_clustering: Dict[str, float]  # Decade distribution
    typical_patterns: List[Dict]  # Common pattern templates


class PatternEngine:
    """
    Pattern conformity analysis engine.
    
    Analyzes historical patterns in:
    - Odd/Even balance
    - High/Low distribution
    - Sum ranges
    - Tens-decade clustering
    
    Used to validate and score tickets based on historical conformity.
    """
    
    def __init__(self):
        """Initialize pattern engine"""
        self.patterns = None
        logger.info("PatternEngine initialized")
    
    def analyze(self, draws_df: pd.DataFrame) -> PatternAnalysis:
        """
        Analyze all pattern dimensions from historical draws.
        
        Args:
            draws_df: DataFrame with draw history
            
        Returns:
            PatternAnalysis with historical pattern statistics
        """
        if draws_df.empty:
            logger.warning("No draws for pattern analysis")
            return self._empty_analysis()
        
        # Analyze each pattern dimension
        odd_even = self._analyze_odd_even(draws_df)
        high_low = self._analyze_high_low(draws_df)
        sum_stats = self._analyze_sum_range(draws_df)
        tens = self._analyze_tens_clustering(draws_df)
        templates = self._extract_typical_patterns(draws_df)
        
        analysis = PatternAnalysis(
            odd_even_distribution=odd_even,
            high_low_distribution=high_low,
            sum_range=sum_stats,
            tens_clustering=tens,
            typical_patterns=templates
        )
        
        # Cache for scoring
        self.patterns = analysis
        
        logger.debug("Pattern analysis complete")
        return analysis
    
    def _empty_analysis(self) -> PatternAnalysis:
        """Return empty analysis when no data available"""
        return PatternAnalysis(
            odd_even_distribution={'0': 0.05, '1': 0.15, '2': 0.30, '3': 0.30, '4': 0.15, '5': 0.05},
            high_low_distribution={'low': 0.33, 'mid': 0.34, 'high': 0.33},
            sum_range=(175.0, 40.0),
            tens_clustering={'0-9': 0.10, '10-19': 0.15, '20-29': 0.15, '30-39': 0.15, 
                           '40-49': 0.15, '50-59': 0.15, '60-69': 0.15},
            typical_patterns=[]
        )
    
    def _analyze_odd_even(self, draws_df: pd.DataFrame) -> Dict[str, float]:
        """Analyze odd/even distribution (0-5 odds per draw)"""
        distribution = {str(i): 0 for i in range(6)}
        
        for _, draw in draws_df.iterrows():
            numbers = [draw['n1'], draw['n2'], draw['n3'], draw['n4'], draw['n5']]
            odd_count = sum(1 for n in numbers if n % 2 == 1)
            distribution[str(odd_count)] += 1
        
        # Normalize
        total = sum(distribution.values())
        if total > 0:
            distribution = {k: v/total for k, v in distribution.items()}
        
        return distribution
    
    def _analyze_high_low(self, draws_df: pd.DataFrame) -> Dict[str, float]:
        """Analyze low (1-23), mid (24-46), high (47-69) distribution"""
        counts = {'low': 0, 'mid': 0, 'high': 0}
        total_numbers = 0
        
        for _, draw in draws_df.iterrows():
            numbers = [draw['n1'], draw['n2'], draw['n3'], draw['n4'], draw['n5']]
            for n in numbers:
                if n <= 23:
                    counts['low'] += 1
                elif n <= 46:
                    counts['mid'] += 1
                else:
                    counts['high'] += 1
                total_numbers += 1
        
        # Normalize
        if total_numbers > 0:
            counts = {k: v/total_numbers for k, v in counts.items()}
        
        return counts
    
    def _analyze_sum_range(self, draws_df: pd.DataFrame) -> Tuple[float, float]:
        """Analyze sum of 5 white balls (mean, std)"""
        sums = []
        
        for _, draw in draws_df.iterrows():
            total = draw['n1'] + draw['n2'] + draw['n3'] + draw['n4'] + draw['n5']
            sums.append(total)
        
        if sums:
            return (float(np.mean(sums)), float(np.std(sums)))
        else:
            return (175.0, 40.0)  # Default values
    
    def _analyze_tens_clustering(self, draws_df: pd.DataFrame) -> Dict[str, float]:
        """Analyze distribution across tens decades (0-9, 10-19, ..., 60-69)"""
        decades = {f'{i*10}-{i*10+9}': 0 for i in range(7)}
        total_numbers = 0
        
        for _, draw in draws_df.iterrows():
            numbers = [draw['n1'], draw['n2'], draw['n3'], draw['n4'], draw['n5']]
            for n in numbers:
                decade = (n - 1) // 10  # 0-6
                key = f'{decade*10}-{decade*10+9}'
                if key in decades:
                    decades[key] += 1
                total_numbers += 1
        
        # Normalize
        if total_numbers > 0:
            decades = {k: v/total_numbers for k, v in decades.items()}
        
        return decades
    
    def _extract_typical_patterns(self, draws_df: pd.DataFrame) -> List[Dict]:
        """Extract common pattern templates from historical draws"""
        templates = []
        
        # Sample up to 10 representative draws
        sample_size = min(10, len(draws_df))
        samples = draws_df.sample(n=sample_size) if len(draws_df) > 0 else draws_df
        
        for _, draw in samples.iterrows():
            numbers = sorted([draw['n1'], draw['n2'], draw['n3'], draw['n4'], draw['n5']])
            odd_count = sum(1 for n in numbers if n % 2 == 1)
            total_sum = sum(numbers)
            spread = numbers[-1] - numbers[0]
            
            templates.append({
                'numbers': numbers,
                'odd_count': odd_count,
                'sum': total_sum,
                'spread': spread
            })
        
        return templates
    
    def score_pattern_conformity(self, white_balls: List[int]) -> float:
        """
        Score a ticket's conformity to historical patterns.
        
        Args:
            white_balls: List of 5 white ball numbers
            
        Returns:
            Conformity score (0.0 - 1.0)
        """
        if self.patterns is None:
            logger.warning("Patterns not analyzed yet, returning neutral score")
            return 0.5
        
        score = 0.0
        
        # 1. Odd/even conformity
        odd_count = sum(1 for n in white_balls if n % 2 == 1)
        odd_even_prob = self.patterns.odd_even_distribution.get(str(odd_count), 0.05)
        score += odd_even_prob * 0.25
        
        # 2. Sum conformity
        total_sum = sum(white_balls)
        mean_sum, std_sum = self.patterns.sum_range
        
        # Check if sum is within ±2 standard deviations (95% of draws)
        if abs(total_sum - mean_sum) <= 2 * std_sum:
            sum_score = 1.0 - min(abs(total_sum - mean_sum) / (2 * std_sum), 1.0)
            score += sum_score * 0.35
        
        # 3. High/low balance
        low_count = sum(1 for n in white_balls if n <= 23)
        mid_count = sum(1 for n in white_balls if 24 <= n <= 46)
        high_count = sum(1 for n in white_balls if n >= 47)
        
        # Compare to historical distribution
        expected_low = self.patterns.high_low_distribution.get('low', 0.33) * 5
        expected_mid = self.patterns.high_low_distribution.get('mid', 0.34) * 5
        expected_high = self.patterns.high_low_distribution.get('high', 0.33) * 5
        
        balance_error = (abs(low_count - expected_low) + 
                        abs(mid_count - expected_mid) + 
                        abs(high_count - expected_high)) / 3
        
        balance_score = max(0, 1.0 - balance_error / 2.0)
        score += balance_score * 0.25
        
        # 4. Tens diversity (prefer spread across decades)
        decades = set((n - 1) // 10 for n in white_balls)
        diversity_score = len(decades) / 5.0  # Max 5 different decades
        score += diversity_score * 0.15
        
        return min(score, 1.0)
