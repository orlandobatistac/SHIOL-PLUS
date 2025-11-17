"""
SHIOL+ v2 - Multi-Dimensional Scoring Engine
=============================================

Provides comprehensive ticket quality scoring across multiple dimensions:
- Diversity Score (entropy-based)
- Balance Index (range distribution)
- Pattern Conformity Score
- Historical Similarity Score

Used to rank and evaluate generated tickets.
"""

import numpy as np
from typing import List, Dict, Tuple
from loguru import logger
from scipy.stats import entropy
from dataclasses import dataclass

from .statistical_core import PatternEngine


@dataclass
class TicketScore:
    """Container for multi-dimensional ticket scoring"""
    diversity_score: float  # 0.0 - 1.0
    balance_score: float    # 0.0 - 1.0
    pattern_score: float    # 0.0 - 1.0
    similarity_score: float # 0.0 - 1.0
    overall_score: float    # Weighted average
    breakdown: Dict[str, float]  # Detailed breakdown


class ScoringEngine:
    """
    Multi-dimensional ticket scoring engine.
    
    Evaluates tickets across four key dimensions and provides
    an overall quality score with detailed breakdown.
    """
    
    def __init__(self, draws_df=None):
        """
        Initialize scoring engine.
        
        Args:
            draws_df: Historical draws for pattern and similarity analysis
        """
        self.draws_df = draws_df
        self.pattern_engine = None
        
        # Initialize pattern engine if draws available
        if draws_df is not None and not draws_df.empty:
            self.pattern_engine = PatternEngine()
            self.pattern_engine.analyze(draws_df)
            logger.info("ScoringEngine initialized with pattern analysis")
        else:
            logger.info("ScoringEngine initialized (no pattern analysis)")
    
    def score_ticket(self, white_balls: List[int], powerball: int) -> TicketScore:
        """
        Score a single ticket across all dimensions.
        
        Args:
            white_balls: List of 5 white ball numbers (1-69)
            powerball: Powerball number (1-26)
            
        Returns:
            TicketScore with comprehensive quality metrics
        """
        # Calculate individual scores
        diversity = self._calculate_diversity_score(white_balls)
        balance = self._calculate_balance_score(white_balls)
        pattern = self._calculate_pattern_score(white_balls)
        similarity = self._calculate_similarity_score(white_balls)
        
        # Weighted overall score
        # Diversity: 25%, Balance: 25%, Pattern: 35%, Similarity: 15%
        overall = (
            diversity * 0.25 +
            balance * 0.25 +
            pattern * 0.35 +
            similarity * 0.15
        )
        
        # Detailed breakdown
        breakdown = {
            'diversity': diversity,
            'balance': balance,
            'pattern': pattern,
            'similarity': similarity,
            'spread': float(white_balls[-1] - white_balls[0]),
            'sum': float(sum(white_balls)),
            'odd_count': sum(1 for n in white_balls if n % 2 == 1),
            'powerball': powerball
        }
        
        return TicketScore(
            diversity_score=diversity,
            balance_score=balance,
            pattern_score=pattern,
            similarity_score=similarity,
            overall_score=overall,
            breakdown=breakdown
        )
    
    def score_tickets(self, tickets: List[Dict]) -> List[TicketScore]:
        """
        Score multiple tickets.
        
        Args:
            tickets: List of ticket dicts with 'white_balls' and 'powerball'
            
        Returns:
            List of TicketScore objects
        """
        scores = []
        
        for ticket in tickets:
            try:
                white_balls = ticket['white_balls']
                powerball = ticket['powerball']
                score = self.score_ticket(white_balls, powerball)
                scores.append(score)
            except Exception as e:
                logger.error(f"Error scoring ticket: {e}")
                # Return neutral score
                scores.append(TicketScore(
                    diversity_score=0.5,
                    balance_score=0.5,
                    pattern_score=0.5,
                    similarity_score=0.5,
                    overall_score=0.5,
                    breakdown={}
                ))
        
        return scores
    
    def _calculate_diversity_score(self, white_balls: List[int]) -> float:
        """
        Calculate diversity/entropy score.
        
        Measures how evenly numbers are distributed across the range.
        Higher entropy = better diversity.
        
        Returns:
            Score 0.0 - 1.0
        """
        # Divide range 1-69 into 7 bins (decades)
        bins = [0, 10, 20, 30, 40, 50, 60, 70]
        hist, _ = np.histogram(white_balls, bins=bins)
        
        # Calculate entropy (max = log2(7) ≈ 2.807)
        hist_normalized = hist / hist.sum() if hist.sum() > 0 else hist
        ent = entropy(hist_normalized + 1e-10, base=2)  # Add epsilon to avoid log(0)
        
        # Normalize to [0, 1]
        max_entropy = np.log2(7)
        score = ent / max_entropy
        
        return float(min(score, 1.0))
    
    def _calculate_balance_score(self, white_balls: List[int]) -> float:
        """
        Calculate balance index.
        
        Measures how well numbers are distributed across low/mid/high ranges.
        Ideal distribution: 2 low, 2 mid, 1 high (or similar).
        
        Returns:
            Score 0.0 - 1.0
        """
        # Count distribution
        low_count = sum(1 for n in white_balls if n <= 23)
        mid_count = sum(1 for n in white_balls if 24 <= n <= 46)
        high_count = sum(1 for n in white_balls if n >= 47)
        
        # Ideal distribution (from historical analysis)
        ideal_low = 2
        ideal_mid = 2
        ideal_high = 1
        
        # Calculate deviation from ideal
        deviation = (
            abs(low_count - ideal_low) +
            abs(mid_count - ideal_mid) +
            abs(high_count - ideal_high)
        )
        
        # Normalize: max deviation is 5 (all in one range)
        # Score: 1.0 = perfect, 0.0 = worst
        score = 1.0 - (deviation / 5.0)
        
        return float(max(score, 0.0))
    
    def _calculate_pattern_score(self, white_balls: List[int]) -> float:
        """
        Calculate pattern conformity score.
        
        Uses PatternEngine to evaluate conformity to historical patterns
        (odd/even, sum, range, clustering).
        
        Returns:
            Score 0.0 - 1.0
        """
        if self.pattern_engine is None:
            # No pattern data, return neutral
            return 0.5
        
        try:
            score = self.pattern_engine.score_pattern_conformity(white_balls)
            return float(score)
        except Exception as e:
            logger.error(f"Pattern scoring failed: {e}")
            return 0.5
    
    def _calculate_similarity_score(self, white_balls: List[int]) -> float:
        """
        Calculate historical similarity score.
        
        Measures how similar this ticket is to historical winning combinations.
        Some similarity is good (follows patterns), but not too much (avoid duplicates).
        
        Returns:
            Score 0.0 - 1.0 (optimal around 0.4-0.6)
        """
        if self.draws_df is None or self.draws_df.empty:
            return 0.5
        
        max_similarity = 0.0
        white_set = set(white_balls)
        
        # Sample recent draws (last 100) for efficiency
        recent_draws = self.draws_df.tail(100)
        
        for _, draw in recent_draws.iterrows():
            historical_set = {draw['n1'], draw['n2'], draw['n3'], draw['n4'], draw['n5']}
            
            # Calculate Jaccard similarity (intersection / union)
            intersection = len(white_set & historical_set)
            union = len(white_set | historical_set)
            
            if union > 0:
                similarity = intersection / union
                max_similarity = max(max_similarity, similarity)
        
        # Optimal similarity is around 0.4-0.6 (2-3 matching numbers)
        # Too low = no pattern recognition
        # Too high = potential duplicate
        optimal = 0.5
        score = 1.0 - abs(max_similarity - optimal) / optimal
        
        return float(max(score, 0.0))
    
    def rank_tickets(self, tickets: List[Dict]) -> List[Tuple[Dict, TicketScore]]:
        """
        Score and rank tickets by overall quality.
        
        Args:
            tickets: List of ticket dictionaries
            
        Returns:
            List of (ticket, score) tuples sorted by descending overall score
        """
        scored = []
        
        for ticket in tickets:
            try:
                score = self.score_ticket(ticket['white_balls'], ticket['powerball'])
                scored.append((ticket, score))
            except Exception as e:
                logger.error(f"Error ranking ticket: {e}")
        
        # Sort by overall score descending
        scored.sort(key=lambda x: x[1].overall_score, reverse=True)
        
        logger.debug(f"Ranked {len(scored)} tickets")
        return scored
    
    def get_quality_summary(self, tickets: List[Dict]) -> Dict:
        """
        Get aggregate quality metrics for a set of tickets.
        
        Args:
            tickets: List of ticket dictionaries
            
        Returns:
            Dictionary with average scores and distribution
        """
        if not tickets:
            return {
                'avg_diversity': 0.0,
                'avg_balance': 0.0,
                'avg_pattern': 0.0,
                'avg_similarity': 0.0,
                'avg_overall': 0.0,
                'count': 0
            }
        
        scores = self.score_tickets(tickets)
        
        return {
            'avg_diversity': float(np.mean([s.diversity_score for s in scores])),
            'avg_balance': float(np.mean([s.balance_score for s in scores])),
            'avg_pattern': float(np.mean([s.pattern_score for s in scores])),
            'avg_similarity': float(np.mean([s.similarity_score for s in scores])),
            'avg_overall': float(np.mean([s.overall_score for s in scores])),
            'std_overall': float(np.std([s.overall_score for s in scores])),
            'min_overall': float(min(s.overall_score for s in scores)),
            'max_overall': float(max(s.overall_score for s in scores)),
            'count': len(tickets)
        }
