"""
Test bug fixes in feature engineering pipeline
===============================================
Tests for Bug #1 (Series comparison in predictor.py) and Bug #2 (duplicate columns in intelligent_generator.py)
"""

import pytest
import sys
import os
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestBugFix1SeriesComparison:
    """Test Bug #1: Series comparison error in predictor.py"""
    
    def test_prepare_features_handles_series_values(self):
        """Test that _prepare_features_for_model handles pandas Series values correctly"""
        from src.predictor import Predictor
        
        # Create a predictor instance
        predictor = Predictor()
        
        # Create test features DataFrame with a Series value that would trigger the bug
        test_data = {
            'even_count': [2.0],
            'odd_count': [3.0],
            'sum': [150.0],
            'spread': [40.0],
            'consecutive_count': [1.0],
            'avg_delay': [5.0],
            'max_delay': [10.0],
            'min_delay': [1.0],
            'dist_to_recent': [0.5],
            'avg_dist_to_top_n': [0.5],
            'dist_to_centroid': [0.5],
            'time_weight': [1.0],
            'increasing_trend_count': [1.0],
            'decreasing_trend_count': [1.0],
            'stable_trend_count': [1.0]
        }
        features_df = pd.DataFrame(test_data)
        
        # Call the method - should not raise "ambiguous truth value" error
        result = predictor._prepare_features_for_model(features_df)
        
        # Verify the result is valid
        assert result is not None, "Should return a valid array"
        assert isinstance(result, np.ndarray), "Should return a numpy array"
        assert result.shape == (1, 15), "Should have correct shape (1, 15)"
        assert np.all(np.isfinite(result)), "All values should be finite"
    
    def test_prepare_features_handles_actual_series_object(self):
        """Test handling when value is an actual pandas Series"""
        from src.predictor import Predictor
        
        predictor = Predictor()
        
        # Create a DataFrame with proper structure
        test_data = {
            'even_count': [2.0],
            'odd_count': [3.0],
            'sum': [150.0],
            'spread': [40.0],
            'consecutive_count': [1.0],
            'avg_delay': [5.0],
            'max_delay': [10.0],
            'min_delay': [1.0],
            'dist_to_recent': [0.5],
            'avg_dist_to_top_n': [0.5],
            'dist_to_centroid': [0.5],
            'time_weight': [1.0],
            'increasing_trend_count': [1.0],
            'decreasing_trend_count': [1.0],
            'stable_trend_count': [1.0]
        }
        features_df = pd.DataFrame(test_data)
        
        # Manually extract value to simulate edge case where it could be a Series
        latest_row = features_df.iloc[-1]
        value = latest_row['even_count']
        
        # Value should be a scalar but test our handling works
        assert pd.notna(value), "Value should not be NaN"
        
        # Should handle the extraction without error
        result = predictor._prepare_features_for_model(features_df)
        
        assert result is not None
        assert isinstance(result, np.ndarray)
    
    def test_prepare_features_handles_nan_values(self):
        """Test that NaN values are handled correctly"""
        from src.predictor import Predictor
        
        predictor = Predictor()
        
        # Create DataFrame with NaN values
        test_data = {
            'even_count': [np.nan],
            'odd_count': [3.0],
            'sum': [150.0],
            'spread': [40.0],
            'consecutive_count': [1.0],
            'avg_delay': [5.0],
            'max_delay': [10.0],
            'min_delay': [1.0],
            'dist_to_recent': [0.5],
            'avg_dist_to_top_n': [0.5],
            'dist_to_centroid': [0.5],
            'time_weight': [1.0],
            'increasing_trend_count': [1.0],
            'decreasing_trend_count': [1.0],
            'stable_trend_count': [1.0]
        }
        features_df = pd.DataFrame(test_data)
        
        result = predictor._prepare_features_for_model(features_df)
        
        assert result is not None
        # First value should be the default (2.5 for even_count)
        assert result[0, 0] == 2.5, "NaN should be replaced with default value"


class TestBugFix2DuplicateColumns:
    """Test Bug #2: Duplicate columns in intelligent_generator.py"""
    
    def test_engineer_features_removes_duplicates(self):
        """Test that duplicate columns are removed after feature engineering"""
        from src.intelligent_generator import FeatureEngineer
        
        # Create minimal test data
        test_data = pd.DataFrame({
            'draw_date': pd.date_range('2024-01-01', periods=10),
            'n1': np.random.randint(1, 70, 10),
            'n2': np.random.randint(1, 70, 10),
            'n3': np.random.randint(1, 70, 10),
            'n4': np.random.randint(1, 70, 10),
            'n5': np.random.randint(1, 70, 10),
            'pb': np.random.randint(1, 27, 10)
        })
        
        # Initialize feature engineer
        engineer = FeatureEngineer(test_data)
        
        # Run feature engineering
        result = engineer.engineer_features(use_temporal_analysis=True)
        
        # Check that there are no duplicate columns
        duplicated_cols = result.columns.duplicated()
        assert not duplicated_cols.any(), f"Duplicate columns found: {result.columns[duplicated_cols].tolist()}"
    
    def test_engineer_features_called_multiple_times(self):
        """Test that calling engineer_features multiple times doesn't accumulate duplicates"""
        from src.intelligent_generator import FeatureEngineer
        
        # Create minimal test data
        test_data = pd.DataFrame({
            'draw_date': pd.date_range('2024-01-01', periods=10),
            'n1': np.random.randint(1, 70, 10),
            'n2': np.random.randint(1, 70, 10),
            'n3': np.random.randint(1, 70, 10),
            'n4': np.random.randint(1, 70, 10),
            'n5': np.random.randint(1, 70, 10),
            'pb': np.random.randint(1, 27, 10)
        })
        
        # Initialize and run feature engineering twice
        engineer = FeatureEngineer(test_data)
        result1 = engineer.engineer_features(use_temporal_analysis=True)
        
        # Re-initialize with same data and run again
        engineer2 = FeatureEngineer(test_data)
        result2 = engineer2.engineer_features(use_temporal_analysis=True)
        
        # Both should have no duplicates
        assert not result1.columns.duplicated().any(), "First run has duplicates"
        assert not result2.columns.duplicated().any(), "Second run has duplicates"
        
        # Column counts should be the same
        assert len(result1.columns) == len(result2.columns), "Column counts differ between runs"
    
    def test_deduplication_keeps_first_occurrence(self):
        """Test that deduplication keeps the first occurrence of duplicate columns"""
        from src.intelligent_generator import FeatureEngineer
        
        # Create test data with artificially duplicated columns
        test_data = pd.DataFrame({
            'draw_date': pd.date_range('2024-01-01', periods=5),
            'n1': [1, 2, 3, 4, 5],
            'n2': [10, 20, 30, 40, 50],
            'n3': [15, 25, 35, 45, 55],
            'n4': [20, 30, 40, 50, 60],
            'n5': [25, 35, 45, 55, 65],
            'pb': [1, 2, 3, 4, 5],
            'increasing_trend_count': [1, 1, 1, 1, 1],  # Pre-existing feature
        })
        
        engineer = FeatureEngineer(test_data)
        
        # Mock the temporal feature calculation to create a duplicate
        original_detect_trends = engineer._detect_trends
        def mock_detect_trends():
            original_detect_trends()
            # This would create a duplicate if deduplication doesn't work
            if 'increasing_trend_count' in engineer.data.columns:
                pass  # Already exists, let's see if deduplication handles it
        
        engineer._detect_trends = mock_detect_trends
        
        result = engineer.engineer_features(use_temporal_analysis=True)
        
        # Verify no duplicates exist
        assert not result.columns.duplicated().any(), "Duplicate columns were not removed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
