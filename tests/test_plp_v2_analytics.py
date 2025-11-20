"""
Tests for new PLP V2 analytics functions
=========================================
Tests for compute_gap_analysis, compute_temporal_frequencies,
compute_momentum_scores, and get_analytics_overview
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.analytics_engine import (
    compute_gap_analysis,
    compute_temporal_frequencies,
    compute_momentum_scores,
    get_analytics_overview
)


class TestComputeGapAnalysis:
    """Test gap analysis function"""
    
    def test_gap_analysis_with_valid_data(self):
        """Test gap analysis with normal data"""
        # Create sample data with known gaps
        today = datetime.now()
        df = pd.DataFrame({
            'draw_date': [
                today - timedelta(days=30),
                today - timedelta(days=20),
                today - timedelta(days=10)
            ],
            'n1': [1, 2, 3],
            'n2': [5, 6, 7],
            'n3': [10, 11, 12],
            'n4': [20, 21, 22],
            'n5': [30, 31, 32],
            'pb': [5, 10, 15]
        })
        
        result = compute_gap_analysis(df)
        
        # Verify structure
        assert 'white_balls' in result
        assert 'powerball' in result
        assert len(result['white_balls']) == 69
        assert len(result['powerball']) == 26
        
        # Verify gaps for numbers we know appeared
        # Most recent draw was 10 days ago
        # Number 3 appeared in that most recent draw (10 days ago)
        # So gap from most recent draw to when it last appeared = 0
        assert result['white_balls'][3] == 0
        
        # Number 32 also appeared in the most recent draw
        assert result['white_balls'][32] == 0
        
        # Number 1 appeared 30 days ago
        # Gap from most recent draw (10 days ago) to when it appeared (30 days ago) = 20 days
        assert result['white_balls'][1] == 20
        
        # Number 2 appeared 20 days ago
        # Gap from most recent draw to when it appeared = 10 days
        assert result['white_balls'][2] == 10
        
        # Powerball 15 appeared in most recent draw (10 days ago)
        assert result['powerball'][15] == 0
        
        # Number that never appeared should have gap of 999
        assert result['white_balls'][69] == 999
    
    def test_gap_analysis_empty_dataframe(self):
        """Test gap analysis handles empty dataframe gracefully"""
        df = pd.DataFrame()
        
        result = compute_gap_analysis(df)
        
        # Should return default gaps (all 0)
        assert 'white_balls' in result
        assert 'powerball' in result
        assert len(result['white_balls']) == 69
        assert len(result['powerball']) == 26
        assert result['white_balls'][1] == 0
    
    def test_gap_analysis_single_draw(self):
        """Test gap analysis with single draw"""
        today = datetime.now()
        df = pd.DataFrame({
            'draw_date': [today],
            'n1': [5], 'n2': [15], 'n3': [25], 'n4': [35], 'n5': [45],
            'pb': [10]
        })
        
        result = compute_gap_analysis(df)
        
        # Numbers that appeared should have gap of 0
        assert result['white_balls'][5] == 0
        assert result['white_balls'][15] == 0
        assert result['powerball'][10] == 0
        
        # Numbers that didn't appear should have gap of 999
        assert result['white_balls'][1] == 999


class TestComputeTemporalFrequencies:
    """Test temporal frequency calculation with exponential decay"""
    
    def test_temporal_frequencies_with_valid_data(self):
        """Test temporal frequencies with normal data"""
        today = datetime.now()
        df = pd.DataFrame({
            'draw_date': [
                today - timedelta(days=30),
                today - timedelta(days=20),
                today - timedelta(days=10)
            ],
            'n1': [1, 1, 1],  # Number 1 appears in all draws
            'n2': [5, 6, 7],
            'n3': [10, 11, 12],
            'n4': [20, 21, 22],
            'n5': [30, 31, 32],
            'pb': [5, 5, 5]  # Powerball 5 appears in all draws
        })
        
        result = compute_temporal_frequencies(df, decay_rate=0.05)
        
        # Verify structure
        assert 'white_balls' in result
        assert 'powerball' in result
        assert len(result['white_balls']) == 69
        assert len(result['powerball']) == 26
        
        # Verify probabilities sum to 1
        assert np.isclose(result['white_balls'].sum(), 1.0, atol=1e-6)
        assert np.isclose(result['powerball'].sum(), 1.0, atol=1e-6)
        
        # Number 1 appeared in all draws, so it should have higher frequency
        # than numbers that appeared once
        assert result['white_balls'][0] > result['white_balls'][4]  # n1 > n2
    
    def test_temporal_frequencies_empty_dataframe(self):
        """Test temporal frequencies handles empty dataframe"""
        df = pd.DataFrame()
        
        result = compute_temporal_frequencies(df)
        
        # Should return uniform distribution
        assert 'white_balls' in result
        assert 'powerball' in result
        assert np.isclose(result['white_balls'].sum(), 1.0)
        assert np.isclose(result['powerball'].sum(), 1.0)
        # All frequencies should be equal (uniform)
        assert np.allclose(result['white_balls'], 1/69, atol=1e-6)
    
    def test_temporal_frequencies_decay_rate(self):
        """Test that higher decay rate reduces influence of old draws"""
        today = datetime.now()
        df = pd.DataFrame({
            'draw_date': [
                today - timedelta(days=100),  # Old draw
                today - timedelta(days=1)     # Recent draw
            ],
            'n1': [1, 2],
            'n2': [5, 6],
            'n3': [10, 11],
            'n4': [20, 21],
            'n5': [30, 31],
            'pb': [5, 10]
        })
        
        # Low decay (old draws still matter)
        result_low = compute_temporal_frequencies(df, decay_rate=0.01)
        
        # High decay (old draws matter less)
        result_high = compute_temporal_frequencies(df, decay_rate=0.1)
        
        # With high decay, number 2 (recent) should have higher frequency
        # relative to number 1 (old) compared to low decay
        ratio_low = result_low['white_balls'][1] / result_low['white_balls'][0]
        ratio_high = result_high['white_balls'][1] / result_high['white_balls'][0]
        
        assert ratio_high > ratio_low


class TestComputeMomentumScores:
    """Test momentum score calculation"""
    
    def test_momentum_scores_with_valid_data(self):
        """Test momentum scores with normal data"""
        # Create data where number 1 appears more in recent draws (rising)
        # and number 69 appears less in recent draws (falling)
        dates = [datetime.now() - timedelta(days=i) for i in range(20, 0, -1)]
        
        # Create n1 column: 69 in first 10 rows (older), 1 in last 10 rows (recent)
        n1_values = [69] * 10 + [1] * 10
        
        df = pd.DataFrame({
            'draw_date': dates,
            'n1': n1_values,
            'n2': [5, 6, 7, 8, 9] * 4,
            'n3': [10, 11, 12, 13, 14] * 4,
            'n4': [20, 21, 22, 23, 24] * 4,
            'n5': [30, 31, 32, 33, 34] * 4,
            'pb': [5] * 20
        })
        
        result = compute_momentum_scores(df, window=20)
        
        # Verify structure
        assert 'white_balls' in result
        assert 'powerball' in result
        assert len(result['white_balls']) == 69
        assert len(result['powerball']) == 26
        
        # Number 1 appears in last 10 draws (recent half), so should have positive momentum
        assert result['white_balls'][1] > 0
        
        # Number 69 appears in first 10 draws (older half), so should have negative momentum
        assert result['white_balls'][69] < 0
        
        # Momentum scores should be between -1 and 1
        for score in result['white_balls'].values():
            assert -1.0 <= score <= 1.0
    
    def test_momentum_scores_insufficient_data(self):
        """Test momentum scores handles insufficient data"""
        df = pd.DataFrame({
            'draw_date': [datetime.now()],
            'n1': [1], 'n2': [5], 'n3': [10], 'n4': [20], 'n5': [30],
            'pb': [5]
        })
        
        result = compute_momentum_scores(df, window=20)
        
        # Should return neutral momentum (0.0) for all numbers
        assert all(score == 0.0 for score in result['white_balls'].values())
        assert all(score == 0.0 for score in result['powerball'].values())
    
    def test_momentum_scores_stable_numbers(self):
        """Test momentum scores for numbers appearing consistently"""
        # Create data where number 5 appears in both halves equally
        dates = [datetime.now() - timedelta(days=i) for i in range(20, 0, -1)]
        
        df = pd.DataFrame({
            'draw_date': dates,
            'n1': [5] * 20,  # Appears consistently
            'n2': [10] * 20,
            'n3': [15] * 20,
            'n4': [20] * 20,
            'n5': [25] * 20,
            'pb': [5] * 20
        })
        
        result = compute_momentum_scores(df, window=20)
        
        # Number 5 appears equally in both halves, momentum should be near 0
        assert abs(result['white_balls'][5]) < 0.2


class TestGetAnalyticsOverview:
    """Test the facade function that returns all analytics"""
    
    def test_analytics_overview_structure(self):
        """Test that analytics overview returns expected structure"""
        result = get_analytics_overview()
        
        # Verify all expected keys are present
        assert 'gap_analysis' in result
        assert 'temporal_frequencies' in result
        assert 'momentum_scores' in result
        assert 'pattern_statistics' in result
        assert 'data_summary' in result
        
        # Verify nested structure
        assert 'white_balls' in result['gap_analysis']
        assert 'powerball' in result['gap_analysis']
        assert 'white_balls' in result['temporal_frequencies']
        assert 'powerball' in result['temporal_frequencies']
        assert 'white_balls' in result['momentum_scores']
        assert 'powerball' in result['momentum_scores']
        
        # Verify data summary fields
        assert 'total_draws' in result['data_summary']
        assert 'most_recent_date' in result['data_summary']
        assert 'current_era_draws' in result['data_summary']
    
    def test_analytics_overview_with_no_data(self, monkeypatch):
        """Test analytics overview handles no data gracefully"""
        # Mock get_all_draws to return empty dataframe
        def mock_get_all_draws():
            return pd.DataFrame()
        
        monkeypatch.setattr('src.analytics_engine.get_all_draws', mock_get_all_draws)
        
        result = get_analytics_overview()
        
        # Should return default values without errors
        assert result['data_summary']['total_draws'] == 0
        assert result['data_summary']['most_recent_date'] is None


class TestIntegration:
    """Integration tests combining multiple analytics functions"""
    
    def test_analytics_consistency(self):
        """Test that all analytics functions work together consistently"""
        # Create sample data
        today = datetime.now()
        dates = [today - timedelta(days=i) for i in range(30, 0, -1)]
        
        df = pd.DataFrame({
            'draw_date': dates,
            'n1': list(range(1, 31)),
            'n2': list(range(10, 40)),
            'n3': list(range(20, 50)),
            'n4': list(range(30, 60)),
            'n5': list(range(40, 70)),
            'pb': [i % 26 + 1 for i in range(30)]
        })
        
        # Compute all analytics
        gap = compute_gap_analysis(df)
        temporal = compute_temporal_frequencies(df)
        momentum = compute_momentum_scores(df, window=20)
        
        # Verify they all return data for same number ranges
        assert set(gap['white_balls'].keys()) == set(range(1, 70))
        assert len(temporal['white_balls']) == 69
        assert set(momentum['white_balls'].keys()) == set(range(1, 70))
        
        # Verify probabilities are valid
        assert np.isclose(temporal['white_balls'].sum(), 1.0)
        assert np.isclose(temporal['powerball'].sum(), 1.0)
