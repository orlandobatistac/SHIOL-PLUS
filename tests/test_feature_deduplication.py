"""
Test Feature Deduplication in engineer_features() Method
=========================================================
Test suite to verify that duplicate features are properly removed
during the feature engineering process.
"""

import pytest
import numpy as np
import pandas as pd
from src.intelligent_generator import FeatureEngineer


class TestFeatureDeduplication:
    """Test suite for feature deduplication"""
    
    @pytest.fixture
    def sample_draws_df(self):
        """Sample historical draw data for testing"""
        dates = pd.date_range('2024-01-01', periods=100, freq='3D')
        data = {
            'draw_date': [d.strftime('%Y-%m-%d') for d in dates],
            'n1': np.random.randint(1, 70, 100),
            'n2': np.random.randint(1, 70, 100),
            'n3': np.random.randint(1, 70, 100),
            'n4': np.random.randint(1, 70, 100),
            'n5': np.random.randint(1, 70, 100),
            'pb': np.random.randint(1, 27, 100)
        }
        return pd.DataFrame(data)
    
    def test_no_duplicate_columns_after_feature_engineering(self, sample_draws_df):
        """Test that engineer_features() produces no duplicate columns"""
        # Initialize feature engineer
        fe = FeatureEngineer(sample_draws_df)
        
        # Run feature engineering with temporal analysis
        result_df = fe.engineer_features(use_temporal_analysis=True)
        
        # Check that there are no duplicate columns
        assert not result_df.columns.duplicated().any(), \
            f"Found duplicate columns: {result_df.columns[result_df.columns.duplicated()].tolist()}"
        
        # Verify all columns are unique
        assert len(result_df.columns) == len(set(result_df.columns)), \
            "Column count does not match unique column count"
    
    def test_no_duplicate_columns_without_temporal_analysis(self, sample_draws_df):
        """Test deduplication works even without temporal analysis"""
        # Initialize feature engineer
        fe = FeatureEngineer(sample_draws_df)
        
        # Run feature engineering WITHOUT temporal analysis
        result_df = fe.engineer_features(use_temporal_analysis=False)
        
        # Check that there are no duplicate columns
        assert not result_df.columns.duplicated().any(), \
            f"Found duplicate columns: {result_df.columns[result_df.columns.duplicated()].tolist()}"
    
    def test_multiple_calls_no_duplication(self, sample_draws_df):
        """Test that multiple calls to engineer_features don't accumulate duplicates"""
        # Initialize feature engineer
        fe = FeatureEngineer(sample_draws_df)
        
        # First call
        result_df_1 = fe.engineer_features(use_temporal_analysis=True)
        column_count_1 = len(result_df_1.columns)
        
        # Check no duplicates after first call
        assert not result_df_1.columns.duplicated().any(), \
            "First call produced duplicates"
        
        # Second call on same instance (simulates re-running)
        # Note: In practice, features would be re-added if data hasn't been reset
        # But deduplication should handle this
        result_df_2 = fe.engineer_features(use_temporal_analysis=True)
        
        # Check no duplicates after second call
        assert not result_df_2.columns.duplicated().any(), \
            "Second call produced duplicates"
    
    def test_temporal_features_are_created(self, sample_draws_df):
        """Test that temporal features are properly created without duplicates"""
        # Initialize feature engineer
        fe = FeatureEngineer(sample_draws_df)
        
        # Run feature engineering with temporal analysis
        result_df = fe.engineer_features(use_temporal_analysis=True)
        
        # Expected temporal features from _detect_trends()
        temporal_trend_features = [
            'increasing_trend_count',
            'decreasing_trend_count', 
            'stable_trend_count',
            'dominant_trend'
        ]
        
        # Expected temporal features from _detect_seasonal_patterns()
        temporal_seasonal_features = [
            'seasonal_number_count',
            'pb_seasonal',
            'has_seasonality'
        ]
        
        # Check that temporal trend features exist and are unique
        for feature in temporal_trend_features:
            assert feature in result_df.columns, f"Missing temporal feature: {feature}"
            # Count how many times this feature appears
            feature_count = result_df.columns.tolist().count(feature)
            assert feature_count == 1, f"Feature '{feature}' appears {feature_count} times (should be 1)"
        
        # Check that temporal seasonal features exist and are unique
        for feature in temporal_seasonal_features:
            assert feature in result_df.columns, f"Missing seasonal feature: {feature}"
            # Count how many times this feature appears
            feature_count = result_df.columns.tolist().count(feature)
            assert feature_count == 1, f"Feature '{feature}' appears {feature_count} times (should be 1)"
    
    def test_basic_features_are_unique(self, sample_draws_df):
        """Test that basic features are created without duplicates"""
        # Initialize feature engineer
        fe = FeatureEngineer(sample_draws_df)
        
        # Run feature engineering
        result_df = fe.engineer_features(use_temporal_analysis=False)
        
        # Expected basic features
        basic_features = [
            'even_count',
            'odd_count',
            'sum',
            'spread',
            'consecutive_count',
            'low_high_balance',
            'prize_tier'
        ]
        
        # Check that basic features exist and are unique
        for feature in basic_features:
            assert feature in result_df.columns, f"Missing basic feature: {feature}"
            # Count how many times this feature appears
            feature_count = result_df.columns.tolist().count(feature)
            assert feature_count == 1, f"Feature '{feature}' appears {feature_count} times (should be 1)"
    
    def test_feature_count_consistency(self, sample_draws_df):
        """Test that feature count remains consistent across multiple runs"""
        # Initialize feature engineer
        fe1 = FeatureEngineer(sample_draws_df.copy())
        result_df_1 = fe1.engineer_features(use_temporal_analysis=True)
        
        # Run again with fresh instance
        fe2 = FeatureEngineer(sample_draws_df.copy())
        result_df_2 = fe2.engineer_features(use_temporal_analysis=True)
        
        # Feature counts should be identical
        assert len(result_df_1.columns) == len(result_df_2.columns), \
            f"Feature count mismatch: {len(result_df_1.columns)} vs {len(result_df_2.columns)}"
        
        # Same features should exist in both
        assert set(result_df_1.columns) == set(result_df_2.columns), \
            "Different features between runs"
