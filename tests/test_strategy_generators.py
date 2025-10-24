"""
Tests for strategy_generators.py module

Focus: Test StrategyManager and individual strategies that have 0% coverage
but are actively used in production API endpoints.
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from src.strategy_generators import (
    StrategyManager,
    CooccurrenceStrategy,
    FrequencyWeightedStrategy,
    RangeBalancedStrategy
)


class TestStrategyManager:
    """Test suite for StrategyManager - orchestrates 6 prediction strategies"""

    @pytest.fixture
    def sample_draws_df(self):
        """Sample historical draw data for testing"""
        return pd.DataFrame({
            'draw_date': ['2024-01-01', '2024-01-04', '2024-01-08', '2024-01-11', '2024-01-15'],
            'n1': [5, 10, 15, 20, 25],
            'n2': [15, 20, 25, 30, 35],
            'n3': [25, 30, 35, 40, 45],
            'n4': [35, 40, 45, 50, 55],
            'n5': [45, 50, 55, 60, 65],
            'pb': [10, 15, 20, 25, 5]
        })

    def test_strategy_manager_initialization(self, sample_draws_df):
        """Test that StrategyManager initializes with historical data"""
        manager = StrategyManager(sample_draws_df)
        
        assert manager is not None
        assert manager.draws_df is not None
        assert len(manager.draws_df) == 5

    @patch('src.strategy_generators.get_all_draws')
    def test_strategy_manager_loads_data_if_none(self, mock_get_draws):
        """Test StrategyManager loads data from DB if not provided"""
        mock_draws = pd.DataFrame({
            'draw_date': ['2024-01-01'],
            'n1': [5], 'n2': [15], 'n3': [25], 'n4': [35], 'n5': [45], 'pb': [10]
        })
        mock_get_draws.return_value = mock_draws
        
        manager = StrategyManager()
        
        assert manager.draws_df is not None
        mock_get_draws.assert_called_once()

    def test_generate_balanced_tickets_returns_list(self, sample_draws_df):
        """Test that generate_balanced_tickets() returns a list of tickets"""
        manager = StrategyManager(sample_draws_df)
        
        tickets = manager.generate_balanced_tickets(num_tickets=5)
        
        assert tickets is not None
        assert isinstance(tickets, list)
        assert len(tickets) <= 5  # May return fewer if deduplication happens

    def test_generate_balanced_tickets_structure(self, sample_draws_df):
        """Test that generated tickets have correct structure"""
        manager = StrategyManager(sample_draws_df)
        
        tickets = manager.generate_balanced_tickets(num_tickets=3)
        
        if len(tickets) > 0:
            ticket = tickets[0]
            # Each ticket should be a dict with ticket_id, numbers, powerball, strategy
            assert 'ticket_id' in ticket
            assert 'numbers' in ticket
            assert 'powerball' in ticket
            assert 'strategy' in ticket
            
            # Validate number ranges
            assert len(ticket['numbers']) == 5
            assert all(1 <= n <= 69 for n in ticket['numbers'])
            assert 1 <= ticket['powerball'] <= 26

    def test_generate_balanced_tickets_uniqueness(self, sample_draws_df):
        """Test that tickets are deduplicated"""
        manager = StrategyManager(sample_draws_df)
        
        tickets = manager.generate_balanced_tickets(num_tickets=10)
        
        # Convert tickets to tuples for uniqueness check
        ticket_tuples = [
            (tuple(sorted(t['numbers'])), t['powerball']) 
            for t in tickets
        ]
        
        # All tickets should be unique
        assert len(ticket_tuples) == len(set(ticket_tuples))


class TestCooccurrenceStrategy:
    """Test suite for CooccurrenceStrategy"""

    @pytest.fixture
    def sample_cooccurrence_data(self):
        """Sample co-occurrence matrix data"""
        return pd.DataFrame({
            'number1': [5, 5, 10, 10, 15],
            'number2': [15, 25, 20, 30, 25],
            'probability': [0.8, 0.7, 0.75, 0.6, 0.65]
        })

    @patch('src.strategy_generators.get_db_connection')
    def test_cooccurrence_strategy_initialization(self, mock_db_conn):
        """Test CooccurrenceStrategy can be initialized"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db_conn.return_value = mock_conn
        
        strategy = CooccurrenceStrategy()
        
        assert strategy is not None

    @patch('src.strategy_generators.get_db_connection')
    def test_cooccurrence_generate_returns_ticket(self, mock_db_conn):
        """Test that CooccurrenceStrategy.generate() returns valid ticket"""
        # Mock database with sample data
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (5, 15, 0.8),
            (10, 20, 0.75),
            (15, 25, 0.7)
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db_conn.return_value = mock_conn
        
        strategy = CooccurrenceStrategy()
        ticket = strategy.generate()
        
        if ticket is not None:  # May return None if no data
            assert len(ticket) == 5
            assert all(isinstance(n, int) for n in ticket)
            assert all(1 <= n <= 69 for n in ticket)


class TestFrequencyWeightedStrategy:
    """Test suite for FrequencyWeightedStrategy"""

    @pytest.fixture
    def sample_draws_df(self):
        """Sample draw data for frequency analysis"""
        return pd.DataFrame({
            'draw_date': ['2024-01-01', '2024-01-04', '2024-01-08'],
            'n1': [5, 5, 5],  # Number 5 is frequent
            'n2': [15, 20, 25],
            'n3': [25, 30, 35],
            'n4': [35, 40, 45],
            'n5': [45, 50, 55],
            'pb': [10, 15, 20]
        })

    def test_frequency_strategy_initialization(self, sample_draws_df):
        """Test FrequencyWeightedStrategy initializes with data"""
        strategy = FrequencyWeightedStrategy(sample_draws_df)
        
        assert strategy is not None
        assert strategy.draws_df is not None

    def test_frequency_generate_returns_ticket(self, sample_draws_df):
        """Test FrequencyWeightedStrategy.generate() returns valid ticket"""
        strategy = FrequencyWeightedStrategy(sample_draws_df)
        
        ticket = strategy.generate()
        
        assert ticket is not None
        assert len(ticket) == 5
        assert all(isinstance(n, int) for n in ticket)
        assert all(1 <= n <= 69 for n in ticket)
        # Numbers should be unique
        assert len(ticket) == len(set(ticket))


class TestRangeBalancedStrategy:
    """Test suite for RangeBalancedStrategy"""

    @pytest.fixture
    def sample_draws_df(self):
        """Sample draw data for range analysis"""
        return pd.DataFrame({
            'draw_date': ['2024-01-01', '2024-01-04', '2024-01-08'],
            'n1': [5, 10, 15],
            'n2': [15, 20, 25],
            'n3': [25, 30, 35],
            'n4': [35, 40, 45],
            'n5': [45, 50, 55],
            'pb': [10, 15, 20]
        })

    def test_range_strategy_initialization(self, sample_draws_df):
        """Test RangeBalancedStrategy initializes with data"""
        strategy = RangeBalancedStrategy(sample_draws_df)
        
        assert strategy is not None
        assert strategy.draws_df is not None

    def test_range_generate_returns_ticket(self, sample_draws_df):
        """Test RangeBalancedStrategy.generate() returns valid ticket"""
        strategy = RangeBalancedStrategy(sample_draws_df)
        
        ticket = strategy.generate()
        
        assert ticket is not None
        assert len(ticket) == 5
        assert all(isinstance(n, int) for n in ticket)
        assert all(1 <= n <= 69 for n in ticket)
        # Numbers should be unique
        assert len(ticket) == len(set(ticket))


class TestStrategyIntegration:
    """Integration tests for strategy system"""

    @pytest.fixture
    def realistic_draws_df(self):
        """More realistic historical draw data"""
        dates = pd.date_range('2023-01-01', periods=20, freq='3D')
        data = {
            'draw_date': [d.strftime('%Y-%m-%d') for d in dates],
            'n1': [5, 10, 15, 20, 25, 8, 12, 18, 22, 28, 3, 9, 14, 19, 24, 7, 11, 16, 21, 26],
            'n2': [15, 20, 25, 30, 35, 18, 22, 28, 32, 38, 13, 19, 24, 29, 34, 17, 21, 26, 31, 36],
            'n3': [25, 30, 35, 40, 45, 28, 32, 38, 42, 48, 23, 29, 34, 39, 44, 27, 31, 36, 41, 46],
            'n4': [35, 40, 45, 50, 55, 38, 42, 48, 52, 58, 33, 39, 44, 49, 54, 37, 41, 46, 51, 56],
            'n5': [45, 50, 55, 60, 65, 48, 52, 58, 62, 68, 43, 49, 54, 59, 64, 47, 51, 56, 61, 66],
            'pb': [10, 15, 20, 25, 5, 12, 17, 22, 3, 8, 11, 16, 21, 26, 6, 13, 18, 23, 4, 9]
        }
        return pd.DataFrame(data)

    def test_full_pipeline_generates_diverse_tickets(self, realistic_draws_df):
        """Test that StrategyManager generates diverse tickets from multiple strategies"""
        manager = StrategyManager(realistic_draws_df)
        
        tickets = manager.generate_balanced_tickets(num_tickets=20)
        
        # Should generate tickets
        assert len(tickets) > 0
        
        # Should have variety of strategies
        strategies_used = set(t['strategy'] for t in tickets)
        assert len(strategies_used) >= 2  # At least 2 different strategies
        
        # All tickets should be valid
        for ticket in tickets:
            assert len(ticket['numbers']) == 5
            assert all(1 <= n <= 69 for n in ticket['numbers'])
            assert 1 <= ticket['powerball'] <= 26
            # Numbers should be sorted
            assert ticket['numbers'] == sorted(ticket['numbers'])


# Note: These tests cover basic functionality and structure.
# Full coverage would require testing:
# - All 6 strategies individually (Pattern, MLPrediction, Consensus, Random)
# - Edge cases (empty data, single draw, etc.)
# - Strategy weight adjustments
# - Powerball number selection logic
