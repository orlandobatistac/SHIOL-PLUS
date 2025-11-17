"""
Tests for SHIOL+ v2 Components
===============================

Tests for:
- Statistical Core (Temporal, Momentum, Gap, Pattern)
- Strategies (TFS, MS, GTS, PS, HSS)
- Scoring Engine
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, MagicMock

# Import v2 components
from src.v2.statistical_core import (
    TemporalDecayModel,
    MomentumAnalyzer,
    GapAnalyzer,
    PatternEngine
)
from src.v2.strategies import (
    TemporalFrequencyStrategy,
    MomentumStrategy,
    GapTheoryStrategy,
    PatternStrategy,
    HybridSmartStrategy
)
from src.v2.scoring import ScoringEngine


@pytest.fixture
def sample_draws():
    """Create sample draw data for testing"""
    # Create 100 sample draws
    draws = []
    for i in range(100):
        draw = {
            'draw_date': f'2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}',
            'n1': (i % 69) + 1,
            'n2': ((i + 10) % 69) + 1,
            'n3': ((i + 20) % 69) + 1,
            'n4': ((i + 30) % 69) + 1,
            'n5': ((i + 40) % 69) + 1,
            'pb': (i % 26) + 1
        }
        draws.append(draw)
    
    return pd.DataFrame(draws)


class TestTemporalDecayModel:
    """Tests for TemporalDecayModel"""
    
    def test_initialization(self):
        """Test model initialization"""
        model = TemporalDecayModel(decay_factor=0.05)
        assert model.decay_factor == 0.05
        assert model.adaptive_window is True
    
    def test_calculate_weights_empty_df(self):
        """Test weight calculation with empty DataFrame"""
        model = TemporalDecayModel()
        weights = model.calculate_weights(pd.DataFrame())
        
        # Should return uniform weights
        assert weights.white_ball_weights.shape == (69,)
        assert weights.powerball_weights.shape == (26,)
        assert np.allclose(weights.white_ball_weights.sum(), 1.0)
        assert np.allclose(weights.powerball_weights.sum(), 1.0)
    
    def test_calculate_weights_with_data(self, sample_draws):
        """Test weight calculation with sample data"""
        model = TemporalDecayModel(decay_factor=0.05)
        weights = model.calculate_weights(sample_draws)
        
        # Check shapes
        assert weights.white_ball_weights.shape == (69,)
        assert weights.powerball_weights.shape == (26,)
        
        # Check normalization
        assert np.allclose(weights.white_ball_weights.sum(), 1.0)
        assert np.allclose(weights.powerball_weights.sum(), 1.0)
        
        # Check window size
        assert weights.window_size > 0
        assert weights.window_size <= len(sample_draws)


class TestMomentumAnalyzer:
    """Tests for MomentumAnalyzer"""
    
    def test_initialization(self):
        """Test analyzer initialization"""
        analyzer = MomentumAnalyzer(short_window=10, long_window=50)
        assert analyzer.short_window == 10
        assert analyzer.long_window == 50
    
    def test_analyze_insufficient_data(self):
        """Test analysis with insufficient data"""
        analyzer = MomentumAnalyzer(short_window=10, long_window=50)
        small_df = pd.DataFrame([{
            'n1': 1, 'n2': 2, 'n3': 3, 'n4': 4, 'n5': 5, 'pb': 1
        }])
        
        momentum = analyzer.analyze(small_df)
        
        # Should return zeros
        assert momentum.white_ball_momentum.shape == (69,)
        assert len(momentum.hot_numbers) == 0
        assert len(momentum.cold_numbers) == 0
    
    def test_analyze_with_data(self, sample_draws):
        """Test momentum analysis with sample data"""
        analyzer = MomentumAnalyzer(short_window=10, long_window=50)
        momentum = analyzer.analyze(sample_draws)
        
        # Check shapes
        assert momentum.white_ball_momentum.shape == (69,)
        assert momentum.powerball_momentum.shape == (26,)
        
        # Check hot/cold lists
        assert len(momentum.hot_numbers) <= 10
        assert len(momentum.cold_numbers) <= 10
        
        # All numbers should be in valid range
        for num in momentum.hot_numbers:
            assert 1 <= num <= 69


class TestGapAnalyzer:
    """Tests for GapAnalyzer"""
    
    def test_initialization(self):
        """Test analyzer initialization"""
        analyzer = GapAnalyzer()
        assert analyzer is not None
    
    def test_analyze_empty_df(self):
        """Test analysis with empty DataFrame"""
        analyzer = GapAnalyzer()
        gaps = analyzer.analyze(pd.DataFrame())
        
        # Should return zeros/defaults
        assert gaps.white_ball_gaps.shape == (69,)
        assert gaps.powerball_gaps.shape == (26,)
        assert len(gaps.overdue_numbers) == 0
    
    def test_analyze_with_data(self, sample_draws):
        """Test gap analysis with sample data"""
        analyzer = GapAnalyzer()
        gaps = analyzer.analyze(sample_draws)
        
        # Check shapes
        assert gaps.white_ball_gaps.shape == (69,)
        assert gaps.powerball_gaps.shape == (26,)
        
        # Check probabilities are normalized
        assert np.allclose(gaps.white_ball_probabilities.sum(), 1.0)
        assert np.allclose(gaps.powerball_probabilities.sum(), 1.0)
        
        # Check overdue numbers
        assert len(gaps.overdue_numbers) <= 15
        for num in gaps.overdue_numbers:
            assert 1 <= num <= 69


class TestPatternEngine:
    """Tests for PatternEngine"""
    
    def test_initialization(self):
        """Test engine initialization"""
        engine = PatternEngine()
        assert engine.patterns is None
    
    def test_analyze_empty_df(self):
        """Test analysis with empty DataFrame"""
        engine = PatternEngine()
        patterns = engine.analyze(pd.DataFrame())
        
        # Should return defaults
        assert patterns.odd_even_distribution is not None
        assert patterns.sum_range is not None
    
    def test_analyze_with_data(self, sample_draws):
        """Test pattern analysis with sample data"""
        engine = PatternEngine()
        patterns = engine.analyze(sample_draws)
        
        # Check odd/even distribution
        assert '0' in patterns.odd_even_distribution
        assert '5' in patterns.odd_even_distribution
        
        # Distribution should sum to ~1.0
        total = sum(patterns.odd_even_distribution.values())
        assert 0.9 <= total <= 1.1
        
        # Check sum stats
        mean, std = patterns.sum_range
        assert mean > 0
        assert std > 0
    
    def test_score_pattern_conformity(self, sample_draws):
        """Test pattern conformity scoring"""
        engine = PatternEngine()
        engine.analyze(sample_draws)
        
        # Score a typical ticket
        white_balls = [5, 15, 25, 35, 45]
        score = engine.score_pattern_conformity(white_balls)
        
        # Score should be between 0 and 1
        assert 0.0 <= score <= 1.0


class TestStrategies:
    """Tests for v2 strategies"""
    
    def test_temporal_frequency_strategy(self, sample_draws):
        """Test Temporal Frequency Strategy"""
        # Mock the BaseStrategy initialization
        strategy = TemporalFrequencyStrategy(decay_factor=0.05)
        strategy.draws_df = sample_draws
        strategy.weights = strategy.temporal_model.calculate_weights(sample_draws)
        
        # Generate tickets
        tickets = strategy.generate(count=5)
        
        # Validate
        assert len(tickets) == 5
        for ticket in tickets:
            assert 'white_balls' in ticket
            assert 'powerball' in ticket
            assert 'strategy' in ticket
            assert len(ticket['white_balls']) == 5
            assert 1 <= ticket['powerball'] <= 26
    
    def test_momentum_strategy(self, sample_draws):
        """Test Momentum Strategy"""
        strategy = MomentumStrategy(short_window=10, long_window=50)
        strategy.draws_df = sample_draws
        strategy.momentum = strategy.momentum_analyzer.analyze(sample_draws)
        
        tickets = strategy.generate(count=5)
        
        assert len(tickets) == 5
        for ticket in tickets:
            assert len(ticket['white_balls']) == 5
            assert ticket['strategy'] == 'momentum_v2'
    
    def test_gap_theory_strategy(self, sample_draws):
        """Test Gap Theory Strategy"""
        strategy = GapTheoryStrategy()
        strategy.draws_df = sample_draws
        strategy.gaps = strategy.gap_analyzer.analyze(sample_draws)
        
        tickets = strategy.generate(count=5)
        
        assert len(tickets) == 5
        for ticket in tickets:
            assert len(ticket['white_balls']) == 5
            assert ticket['strategy'] == 'gap_theory_v2'
    
    def test_pattern_strategy(self, sample_draws):
        """Test Pattern Strategy"""
        strategy = PatternStrategy()
        strategy.draws_df = sample_draws
        strategy.patterns = strategy.pattern_engine.analyze(sample_draws)
        
        tickets = strategy.generate(count=5)
        
        assert len(tickets) == 5
        for ticket in tickets:
            assert len(ticket['white_balls']) == 5
            assert ticket['strategy'] == 'pattern_v2'
    
    def test_hybrid_smart_strategy(self, sample_draws):
        """Test Hybrid Smart Strategy"""
        strategy = HybridSmartStrategy()
        strategy.draws_df = sample_draws
        
        # Initialize all components
        strategy.weights = strategy.temporal_model.calculate_weights(sample_draws)
        strategy.momentum = strategy.momentum_analyzer.analyze(sample_draws)
        strategy.gaps = strategy.gap_analyzer.analyze(sample_draws)
        strategy.patterns = strategy.pattern_engine.analyze(sample_draws)
        
        tickets = strategy.generate(count=5)
        
        assert len(tickets) == 5
        for ticket in tickets:
            assert len(ticket['white_balls']) == 5
            assert ticket['strategy'] == 'hybrid_smart_v2'


class TestScoringEngine:
    """Tests for ScoringEngine"""
    
    def test_initialization(self, sample_draws):
        """Test scoring engine initialization"""
        engine = ScoringEngine(draws_df=sample_draws)
        assert engine.draws_df is not None
        assert engine.pattern_engine is not None
    
    def test_score_ticket(self, sample_draws):
        """Test ticket scoring"""
        engine = ScoringEngine(draws_df=sample_draws)
        
        white_balls = [5, 15, 25, 35, 45]
        powerball = 10
        
        score = engine.score_ticket(white_balls, powerball)
        
        # Check score ranges
        assert 0.0 <= score.diversity_score <= 1.0
        assert 0.0 <= score.balance_score <= 1.0
        assert 0.0 <= score.pattern_score <= 1.0
        assert 0.0 <= score.similarity_score <= 1.0
        assert 0.0 <= score.overall_score <= 1.0
        
        # Check breakdown
        assert 'diversity' in score.breakdown
        assert 'sum' in score.breakdown
    
    def test_rank_tickets(self, sample_draws):
        """Test ticket ranking"""
        engine = ScoringEngine(draws_df=sample_draws)
        
        tickets = [
            {'white_balls': [1, 2, 3, 4, 5], 'powerball': 1},
            {'white_balls': [10, 20, 30, 40, 50], 'powerball': 10},
            {'white_balls': [5, 15, 25, 35, 45], 'powerball': 5}
        ]
        
        ranked = engine.rank_tickets(tickets)
        
        # Should have same length
        assert len(ranked) == len(tickets)
        
        # First ticket should have highest score
        if len(ranked) > 1:
            assert ranked[0][1].overall_score >= ranked[1][1].overall_score
    
    def test_quality_summary(self, sample_draws):
        """Test quality summary generation"""
        engine = ScoringEngine(draws_df=sample_draws)
        
        tickets = [
            {'white_balls': [5, 15, 25, 35, 45], 'powerball': 10},
            {'white_balls': [10, 20, 30, 40, 50], 'powerball': 5}
        ]
        
        summary = engine.get_quality_summary(tickets)
        
        # Check summary fields
        assert 'avg_diversity' in summary
        assert 'avg_overall' in summary
        assert 'count' in summary
        assert summary['count'] == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
