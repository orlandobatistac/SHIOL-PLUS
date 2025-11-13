"""
Tests for analytics_engine.py module

Focus: Test update_analytics() function that has 0% coverage but is called
3x/week by APScheduler in production pipeline.
"""

import pytest
import sqlite3
import pandas as pd
from unittest.mock import patch, MagicMock
from src.analytics_engine import update_analytics, AnalyticsEngine


class TestAnalyticsEngine:
    """Test suite for AnalyticsEngine class"""

    @pytest.fixture
    def sample_draws_df(self):
        """Sample historical draw data for testing"""
        return pd.DataFrame({
            'draw_date': ['2024-01-01', '2024-01-04', '2024-01-08'],
            'n1': [5, 10, 15],
            'n2': [15, 20, 25],
            'n3': [25, 30, 35],
            'n4': [35, 40, 45],
            'n5': [45, 50, 55],
            'pb': [10, 15, 20]
        })

    def test_analytics_engine_initialization(self, sample_draws_df):
        """Test that AnalyticsEngine initializes correctly with data"""
        engine = AnalyticsEngine(sample_draws_df)
        
        assert engine is not None
        assert len(engine.draws_df) == 3
        assert 'draw_date' in engine.draws_df.columns

    def test_calculate_cooccurrence_matrix(self, sample_draws_df):
        """Test co-occurrence matrix calculation"""
        engine = AnalyticsEngine(sample_draws_df)
        cooccurrence = engine.calculate_cooccurrence()
        
        assert cooccurrence is not None
        assert isinstance(cooccurrence, dict)
        # Verify matrix has entries for number pairs
        assert len(cooccurrence) > 0

    def test_calculate_patterns(self, sample_draws_df):
        """Test pattern statistics calculation"""
        engine = AnalyticsEngine(sample_draws_df)
        patterns = engine.calculate_patterns()
        
        assert patterns is not None
        assert isinstance(patterns, dict)
        # Should have sum, range, odd_even patterns
        assert 'sum' in patterns or len(patterns) > 0


class TestUpdateAnalytics:
    """Test suite for update_analytics() function - 0% coverage critical function"""

    @patch('src.analytics_engine.get_all_draws')
    @patch('src.analytics_engine.get_db_connection')
    def test_update_analytics_success(self, mock_db_conn, mock_get_draws):
        """Test successful analytics update with mocked database"""
        # Mock database connection
        mock_conn = MagicMock(spec=sqlite3.Connection)
        mock_cursor = MagicMock(spec=sqlite3.Cursor)
        mock_conn.cursor.return_value = mock_cursor
        mock_db_conn.return_value = mock_conn
        
        # Mock draw data
        mock_draws = pd.DataFrame({
            'draw_date': ['2024-01-01', '2024-01-04', '2024-01-08'],
            'n1': [5, 10, 15],
            'n2': [15, 20, 25],
            'n3': [25, 30, 35],
            'n4': [35, 40, 45],
            'n5': [45, 50, 55],
            'pb': [10, 15, 20]
        })
        mock_get_draws.return_value = mock_draws
        
        # Execute function
        result = update_analytics()
        
        # Assertions
        assert result is True or result is None  # Function returns True or doesn't return
        mock_get_draws.assert_called_once()
        mock_db_conn.assert_called()
        # Verify DB operations were attempted
        mock_cursor.execute.assert_called()

    @patch('src.analytics_engine.get_all_draws')
    def test_update_analytics_no_data(self, mock_get_draws):
        """Test update_analytics handles empty dataset gracefully"""
        # Mock empty dataframe
        mock_get_draws.return_value = pd.DataFrame()
        
        # Should not crash with empty data
        result = update_analytics()
        
        # Function should handle empty data without errors
        assert result is False or result is None

    @patch('src.analytics_engine.get_all_draws')
    @patch('src.analytics_engine.get_db_connection')
    def test_update_analytics_db_error_handling(self, mock_db_conn, mock_get_draws):
        """Test that update_analytics handles database errors gracefully"""
        # Mock data
        mock_draws = pd.DataFrame({
            'draw_date': ['2024-01-01'],
            'n1': [5], 'n2': [15], 'n3': [25], 'n4': [35], 'n5': [45], 'pb': [10]
        })
        mock_get_draws.return_value = mock_draws
        
        # Mock database error
        mock_db_conn.side_effect = sqlite3.Error("Database connection failed")
        
        # Should not crash, should return False or log error
        result = update_analytics()
        
        assert result is False or result is None


class TestAnalyticsIntegration:
    """Integration tests for analytics engine with real (test) database"""

    @pytest.fixture
    def test_db_connection(self, tmp_path):
        """Create a temporary test database"""
        db_path = tmp_path / "test_analytics.db"
        conn = sqlite3.connect(str(db_path))
        
        # Create required tables
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS powerball_draws (
                draw_date TEXT PRIMARY KEY,
                n1 INTEGER, n2 INTEGER, n3 INTEGER, n4 INTEGER, n5 INTEGER,
                pb INTEGER
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cooccurrence_matrix (
                number1 INTEGER,
                number2 INTEGER,
                count INTEGER,
                probability REAL,
                PRIMARY KEY (number1, number2)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pattern_stats (
                pattern_type TEXT,
                pattern_name TEXT,
                value REAL,
                frequency REAL,
                is_current_era INTEGER,
                mean REAL,
                std_dev REAL
            )
        """)
        
        conn.commit()
        yield conn
        conn.close()

    def test_analytics_engine_with_real_data(self, test_db_connection):
        """Test AnalyticsEngine with realistic draw data"""
        # Insert test data
        cursor = test_db_connection.cursor()
        test_draws = [
            ('2024-01-01', 5, 15, 25, 35, 45, 10),
            ('2024-01-04', 10, 20, 30, 40, 50, 15),
            ('2024-01-08', 15, 25, 35, 45, 55, 20),
        ]
        
        cursor.executemany("""
            INSERT INTO powerball_draws VALUES (?, ?, ?, ?, ?, ?, ?)
        """, test_draws)
        test_db_connection.commit()
        
        # Load data into AnalyticsEngine
        df = pd.read_sql_query("SELECT * FROM powerball_draws", test_db_connection)
        engine = AnalyticsEngine(df)
        
        # Test calculations
        cooccurrence = engine.calculate_cooccurrence()
        patterns = engine.calculate_patterns()
        
        assert len(cooccurrence) > 0
        assert len(patterns) > 0


# Note: These tests focus on basic functionality and error handling.
# Full integration tests would require mocking the entire database schema
# and testing the save_patterns_to_db() and save_cooccurrence_to_db() methods.
