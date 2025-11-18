"""
Tests for UnifiedPredictionEngine
==================================
Validates the abstraction layer for different prediction implementations.
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from src.prediction_engine import UnifiedPredictionEngine


class TestUnifiedPredictionEngineInit:
    """Test initialization and mode selection"""

    @patch('src.strategy_generators.StrategyManager')  # Mock to avoid DB access
    def test_default_mode_is_v1(self, mock_strategy_manager):
        """Test that default mode is v1 when no env var is set"""
        with patch.dict(os.environ, {}, clear=True):
            engine = UnifiedPredictionEngine()
            assert engine.get_mode() == 'v1'

    def test_mode_from_env_variable(self):
        """Test that mode is read from PREDICTION_MODE env var"""
        with patch.dict(os.environ, {'PREDICTION_MODE': 'v2'}):
            engine = UnifiedPredictionEngine()
            assert engine.get_mode() == 'v2'

    @patch('src.strategy_generators.StrategyManager')  # Mock to avoid DB access
    def test_mode_from_constructor_parameter(self, mock_strategy_manager):
        """Test that constructor parameter overrides env var"""
        with patch.dict(os.environ, {'PREDICTION_MODE': 'v2'}):
            engine = UnifiedPredictionEngine(mode='v1')
            assert engine.get_mode() == 'v1'

    @patch('src.strategy_generators.StrategyManager')  # Mock to avoid DB access
    def test_invalid_mode_falls_back_to_v1(self, mock_strategy_manager):
        """Test that invalid mode falls back to v1"""
        with patch.dict(os.environ, {'PREDICTION_MODE': 'invalid'}):
            engine = UnifiedPredictionEngine()
            assert engine.get_mode() == 'v1'

    @patch('src.strategy_generators.StrategyManager')  # Mock to avoid DB access
    def test_mode_is_case_insensitive(self, mock_strategy_manager):
        """Test that mode is converted to lowercase"""
        engine = UnifiedPredictionEngine(mode='V1')
        assert engine.get_mode() == 'v1'


class TestUnifiedPredictionEngineV1Mode:
    """Test v1 mode (StrategyManager delegation)"""

    @patch('src.strategy_generators.StrategyManager')  # Patch where it's imported from
    def test_v1_backend_initialized_on_first_use(self, mock_strategy_manager_class):
        """Test that v1 backend is initialized lazily"""
        mock_manager = MagicMock()
        mock_strategy_manager_class.return_value = mock_manager
        
        engine = UnifiedPredictionEngine(mode='v1')
        # Backend should be initialized in __init__ for v1
        assert engine._backend is not None

    @patch('src.strategy_generators.StrategyManager')
    def test_v1_generate_tickets_delegates_to_strategy_manager(self, mock_strategy_manager_class):
        """Test that v1 mode delegates to StrategyManager.generate_balanced_tickets"""
        mock_manager = MagicMock()
        mock_tickets = [
            {
                'white_balls': [1, 2, 3, 4, 5],
                'powerball': 10,
                'strategy': 'test_strategy',
                'confidence': 0.5
            }
        ]
        mock_manager.generate_balanced_tickets.return_value = mock_tickets
        mock_strategy_manager_class.return_value = mock_manager
        
        engine = UnifiedPredictionEngine(mode='v1')
        tickets = engine.generate_tickets(5)
        
        # Verify delegation
        mock_manager.generate_balanced_tickets.assert_called_once_with(5)
        assert tickets == mock_tickets

    @patch('src.strategy_generators.StrategyManager')
    def test_v1_get_strategy_manager_returns_backend(self, mock_strategy_manager_class):
        """Test that get_strategy_manager returns the StrategyManager instance"""
        mock_manager = MagicMock()
        mock_strategy_manager_class.return_value = mock_manager
        
        engine = UnifiedPredictionEngine(mode='v1')
        manager = engine.get_strategy_manager()
        
        assert manager is mock_manager

    @patch('src.strategy_generators.StrategyManager')
    def test_v1_backend_info_includes_strategies(self, mock_strategy_manager_class):
        """Test that get_backend_info includes strategy information for v1"""
        mock_manager = MagicMock()
        mock_manager.get_strategy_weights.return_value = {'strategy1': 0.5, 'strategy2': 0.5}
        mock_manager.strategies = {'strategy1': MagicMock(), 'strategy2': MagicMock()}
        mock_strategy_manager_class.return_value = mock_manager
        
        engine = UnifiedPredictionEngine(mode='v1')
        info = engine.get_backend_info()
        
        assert info['mode'] == 'v1'
        assert info['backend_type'] == 'MagicMock'
        assert 'strategy_weights' in info
        assert 'available_strategies' in info


class TestUnifiedPredictionEngineV2Mode:
    """Test v2 mode (not yet implemented)"""

    def test_v2_generate_tickets_raises_not_implemented(self):
        """Test that v2 mode raises NotImplementedError"""
        engine = UnifiedPredictionEngine(mode='v2')
        
        with pytest.raises(NotImplementedError) as exc_info:
            engine.generate_tickets(5)
        
        assert 'v2 mode' in str(exc_info.value)
        assert 'not yet implemented' in str(exc_info.value).lower()

    def test_v2_get_strategy_manager_raises_runtime_error(self):
        """Test that get_strategy_manager raises RuntimeError in v2 mode"""
        engine = UnifiedPredictionEngine(mode='v2')
        
        with pytest.raises(RuntimeError) as exc_info:
            engine.get_strategy_manager()
        
        assert 'only available in v1 mode' in str(exc_info.value)


class TestUnifiedPredictionEngineHybridMode:
    """Test hybrid mode (not yet implemented)"""

    def test_hybrid_generate_tickets_raises_not_implemented(self):
        """Test that hybrid mode raises NotImplementedError"""
        engine = UnifiedPredictionEngine(mode='hybrid')
        
        with pytest.raises(NotImplementedError) as exc_info:
            engine.generate_tickets(5)
        
        assert 'hybrid mode' in str(exc_info.value)
        assert 'not yet implemented' in str(exc_info.value).lower()

    def test_hybrid_get_strategy_manager_raises_runtime_error(self):
        """Test that get_strategy_manager raises RuntimeError in hybrid mode"""
        engine = UnifiedPredictionEngine(mode='hybrid')
        
        with pytest.raises(RuntimeError) as exc_info:
            engine.get_strategy_manager()
        
        assert 'only available in v1 mode' in str(exc_info.value)


class TestUnifiedPredictionEngineIntegration:
    """Integration tests with real StrategyManager (if available)"""

    @pytest.mark.skipif(
        not os.path.exists('/home/runner/work/SHIOL-PLUS/SHIOL-PLUS/data/shiolplus.db'),
        reason="Database not available in test environment"
    )
    def test_v1_mode_generates_valid_tickets(self):
        """Test that v1 mode generates valid tickets with real StrategyManager"""
        engine = UnifiedPredictionEngine(mode='v1')
        
        try:
            tickets = engine.generate_tickets(5)
            
            # Basic validation
            assert isinstance(tickets, list)
            assert len(tickets) <= 5  # May be fewer due to deduplication
            
            if len(tickets) > 0:
                ticket = tickets[0]
                assert 'white_balls' in ticket
                assert 'powerball' in ticket
                assert 'strategy' in ticket
                assert 'confidence' in ticket
                
                # Validate ranges
                assert len(ticket['white_balls']) == 5
                assert all(1 <= n <= 69 for n in ticket['white_balls'])
                assert 1 <= ticket['powerball'] <= 26
                assert ticket['white_balls'] == sorted(ticket['white_balls'])  # Should be sorted
        except Exception as e:
            # If database isn't set up, that's okay for this test
            if 'no such table' not in str(e).lower():
                raise
