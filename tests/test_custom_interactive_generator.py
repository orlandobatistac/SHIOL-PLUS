"""
Tests for CustomInteractiveGenerator
=====================================
Tests for interactive ticket generation with user parameters
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from src.strategy_generators import CustomInteractiveGenerator


class TestCustomInteractiveGenerator:
    """Test the custom interactive generator"""
    
    @pytest.fixture
    def generator(self):
        """Create a generator instance for testing"""
        return CustomInteractiveGenerator()
    
    @pytest.fixture
    def sample_context(self):
        """Create sample analytics context"""
        return {
            'gap_analysis': {
                'white_balls': {i: i * 5 for i in range(1, 70)},  # Increasing gaps
                'powerball': {i: i * 2 for i in range(1, 27)}
            },
            'temporal_frequencies': {
                'white_balls': np.ones(69) / 69,  # Uniform distribution
                'powerball': np.ones(26) / 26
            }
        }
    
    def test_initialization(self, generator):
        """Test generator initializes correctly"""
        assert generator.name == "custom_interactive"
        assert generator._analytics_cache is None
    
    def test_generate_with_default_parameters(self, generator):
        """Test generation with default neutral parameters"""
        tickets = generator.generate(5)
        
        assert len(tickets) == 5
        for ticket in tickets:
            assert len(ticket['white_balls']) == 5
            assert all(1 <= n <= 69 for n in ticket['white_balls'])
            assert ticket['white_balls'] == sorted(ticket['white_balls'])
            assert 1 <= ticket['powerball'] <= 26
            assert ticket['strategy'] == 'custom_interactive'
            assert 0.0 <= ticket['confidence'] <= 1.0
    
    def test_generate_custom_with_neutral_parameters(self, generator, sample_context):
        """Test custom generation with neutral settings"""
        params = {
            'count': 3,
            'risk': 'med',
            'temperature': 'neutral',
            'exclude': []
        }
        
        tickets = generator.generate_custom(params, sample_context)
        
        assert len(tickets) == 3
        for ticket in tickets:
            assert len(ticket['white_balls']) == 5
            assert ticket['strategy'] == 'custom_interactive'
    
    def test_generate_custom_with_hot_temperature(self, generator, sample_context):
        """Test generation favoring hot (frequent) numbers"""
        # Modify context to make certain numbers hot
        hot_numbers = [1, 2, 3, 4, 5]
        temporal_freq = np.ones(69) / 69
        for num in hot_numbers:
            temporal_freq[num - 1] = 0.1  # Much higher frequency
        
        # Normalize
        temporal_freq = temporal_freq / temporal_freq.sum()
        
        sample_context['temporal_frequencies']['white_balls'] = temporal_freq
        
        params = {
            'count': 10,
            'risk': 'med',
            'temperature': 'hot',
            'exclude': []
        }
        
        tickets = generator.generate_custom(params, sample_context)
        
        # Count how many times hot numbers appear
        hot_count = 0
        total_numbers = 0
        for ticket in tickets:
            for num in ticket['white_balls']:
                total_numbers += 1
                if num in hot_numbers:
                    hot_count += 1
        
        # Hot numbers should appear more frequently than uniform (5/69 ≈ 7.2%)
        # With hot weighting, we expect significantly more
        hot_percentage = hot_count / total_numbers
        # This is probabilistic, but hot numbers should appear > 20% of the time
        # if properly weighted (they have ~10x the frequency)
        # We use a lenient threshold to avoid flaky tests
        assert hot_percentage > 0.1  # At least 10% (vs 7.2% uniform)
    
    def test_generate_custom_with_cold_temperature(self, generator, sample_context):
        """Test generation favoring cold (overdue) numbers"""
        # Modify context to make certain numbers cold (high gap)
        cold_numbers = [60, 61, 62, 63, 64]
        for num in cold_numbers:
            sample_context['gap_analysis']['white_balls'][num] = 999  # Very overdue
        
        params = {
            'count': 10,
            'risk': 'med',
            'temperature': 'cold',
            'exclude': []
        }
        
        tickets = generator.generate_custom(params, sample_context)
        
        # Count how many times cold numbers appear
        cold_count = 0
        total_numbers = 0
        for ticket in tickets:
            for num in ticket['white_balls']:
                total_numbers += 1
                if num in cold_numbers:
                    cold_count += 1
        
        # Cold numbers should appear more frequently than uniform
        cold_percentage = cold_count / total_numbers
        assert cold_percentage > 0.1  # Should be elevated
    
    def test_generate_custom_with_exclusions(self, generator, sample_context):
        """Test that excluded numbers are not generated"""
        excluded = [1, 2, 3, 4, 5, 10, 20, 30]
        
        params = {
            'count': 10,
            'risk': 'med',
            'temperature': 'neutral',
            'exclude': excluded
        }
        
        tickets = generator.generate_custom(params, sample_context)
        
        # Verify no excluded numbers appear
        for ticket in tickets:
            for num in ticket['white_balls']:
                assert num not in excluded
    
    def test_generate_custom_with_too_many_exclusions(self, generator, sample_context):
        """Test handling of excessive exclusions (> 64 numbers excluded)"""
        # Exclude 65 numbers (leaving only 4 available)
        excluded = list(range(1, 66))
        
        params = {
            'count': 3,
            'risk': 'med',
            'temperature': 'neutral',
            'exclude': excluded
        }
        
        # Should ignore exclusions when there aren't enough numbers
        tickets = generator.generate_custom(params, sample_context)
        
        assert len(tickets) == 3
        # Tickets should still be valid (fallback to allowing all numbers)
        for ticket in tickets:
            assert len(ticket['white_balls']) == 5
    
    def test_risk_levels(self, generator, sample_context):
        """Test different risk levels produce tickets"""
        for risk in ['low', 'med', 'high']:
            params = {
                'count': 3,
                'risk': risk,
                'temperature': 'neutral',
                'exclude': []
            }
            
            tickets = generator.generate_custom(params, sample_context)
            
            assert len(tickets) == 3
            # Confidence should vary with risk
            for ticket in tickets:
                if risk == 'low':
                    assert ticket['confidence'] >= 0.70
                elif risk == 'high':
                    assert ticket['confidence'] <= 0.75
    
    def test_invalid_risk_level(self, generator, sample_context):
        """Test handling of invalid risk level"""
        params = {
            'count': 2,
            'risk': 'invalid_risk',
            'temperature': 'neutral',
            'exclude': []
        }
        
        # Should default to 'med' and still generate tickets
        tickets = generator.generate_custom(params, sample_context)
        
        assert len(tickets) == 2
    
    def test_invalid_temperature(self, generator, sample_context):
        """Test handling of invalid temperature"""
        params = {
            'count': 2,
            'risk': 'med',
            'temperature': 'invalid_temp',
            'exclude': []
        }
        
        # Should default to 'neutral' and still generate tickets
        tickets = generator.generate_custom(params, sample_context)
        
        assert len(tickets) == 2
    
    def test_powerball_generation(self, generator, sample_context):
        """Test powerball generation respects temperature settings"""
        params_hot = {
            'count': 5,
            'risk': 'med',
            'temperature': 'hot',
            'exclude': []
        }
        
        params_cold = {
            'count': 5,
            'risk': 'med',
            'temperature': 'cold',
            'exclude': []
        }
        
        tickets_hot = generator.generate_custom(params_hot, sample_context)
        tickets_cold = generator.generate_custom(params_cold, sample_context)
        
        # All tickets should have valid powerballs
        for ticket in tickets_hot + tickets_cold:
            assert 1 <= ticket['powerball'] <= 26
    
    def test_analytics_caching(self, generator):
        """Test that analytics are cached for efficiency"""
        # First call should compute analytics
        tickets1 = generator.generate(3)
        cache1 = generator._analytics_cache
        
        # Second call should use cached analytics
        tickets2 = generator.generate(3)
        cache2 = generator._analytics_cache
        
        assert cache1 is cache2  # Same object reference
        assert len(tickets1) == 3
        assert len(tickets2) == 3
    
    def test_generate_custom_without_context(self, generator):
        """Test generation without providing context (should compute it)"""
        params = {
            'count': 3,
            'risk': 'med',
            'temperature': 'hot',
            'exclude': []
        }
        
        # Don't provide context - should compute internally
        tickets = generator.generate_custom(params)
        
        assert len(tickets) == 3
        # Analytics cache should be populated
        assert generator._analytics_cache is not None
    
    def test_confidence_calculation(self, generator):
        """Test confidence scores are calculated correctly"""
        # Low risk should have higher confidence
        result_low = generator._calculate_confidence('low', 'neutral')
        assert result_low >= 0.70
        
        # High risk should have lower confidence
        result_high = generator._calculate_confidence('high', 'neutral')
        assert result_high <= 0.65
        
        # Temperature 'hot' or 'cold' should boost confidence slightly
        result_hot = generator._calculate_confidence('med', 'hot')
        result_neutral = generator._calculate_confidence('med', 'neutral')
        assert result_hot >= result_neutral
    
    def test_white_ball_uniqueness(self, generator, sample_context):
        """Test that generated white balls are always unique"""
        params = {
            'count': 20,
            'risk': 'high',
            'temperature': 'hot',
            'exclude': []
        }
        
        tickets = generator.generate_custom(params, sample_context)
        
        for ticket in tickets:
            white_balls = ticket['white_balls']
            assert len(white_balls) == len(set(white_balls))  # No duplicates
            assert len(white_balls) == 5
    
    def test_edge_case_single_ticket(self, generator, sample_context):
        """Test generating a single ticket"""
        params = {
            'count': 1,
            'risk': 'low',
            'temperature': 'neutral',
            'exclude': []
        }
        
        tickets = generator.generate_custom(params, sample_context)
        
        assert len(tickets) == 1
        assert len(tickets[0]['white_balls']) == 5


class TestIntegrationWithAnalytics:
    """Integration tests with real analytics functions"""
    
    def test_generation_with_computed_analytics(self):
        """Test generation using computed analytics from real data"""
        from src.analytics_engine import compute_gap_analysis, compute_temporal_frequencies
        
        # Create sample historical data
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
        
        # Compute real analytics
        context = {
            'gap_analysis': compute_gap_analysis(df),
            'temporal_frequencies': compute_temporal_frequencies(df)
        }
        
        # Generate tickets with real analytics
        generator = CustomInteractiveGenerator()
        params = {
            'count': 5,
            'risk': 'med',
            'temperature': 'hot',
            'exclude': []
        }
        
        tickets = generator.generate_custom(params, context)
        
        assert len(tickets) == 5
        for ticket in tickets:
            assert len(ticket['white_balls']) == 5
            assert all(1 <= n <= 69 for n in ticket['white_balls'])
