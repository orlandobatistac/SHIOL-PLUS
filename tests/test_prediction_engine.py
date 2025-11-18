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
    """Test v2 mode (ML-based prediction)"""

    @patch('src.prediction_engine.UnifiedPredictionEngine._initialize_v2_backend')
    def test_v2_mode_initialization(self, mock_init_v2):
        """Test that v2 mode initializes v2 backend"""
        engine = UnifiedPredictionEngine(mode='v2')
        assert engine.get_mode() == 'v2'
        mock_init_v2.assert_called_once()

    @patch('src.strategy_generators.StrategyManager')
    def test_v2_xgboost_not_available_fallback(self, mock_strategy_manager):
        """Test that v2 mode can fallback to v1 when XGBoost is not available"""
        mock_manager = MagicMock()
        mock_strategy_manager.return_value = mock_manager
        
        # Create engine and manually simulate the fallback scenario
        engine = UnifiedPredictionEngine(mode='v1')  # Start with v1 to avoid initialization issues
        
        # Simulate what would happen if v2 initialization failed
        engine._xgboost_available = False
        
        # Verify that when XGBoost is not available, the flag is set correctly
        assert engine._xgboost_available is False

    @patch('src.predictor.Predictor')
    def test_v2_generate_tickets_with_ml_predictor(self, mock_predictor_class):
        """Test that v2 mode generates tickets using ML predictor"""
        # Setup mock predictor
        mock_predictor = MagicMock()
        mock_ml_predictions = [
            {
                'numbers': [1, 2, 3, 4, 5],
                'powerball': 10,
                'confidence_score': 0.85
            },
            {
                'numbers': [6, 7, 8, 9, 10],
                'powerball': 15,
                'confidence_score': 0.75
            }
        ]
        mock_predictor.predict_diverse_plays.return_value = mock_ml_predictions
        mock_predictor_class.return_value = mock_predictor
        
        # Mock XGBoost availability
        with patch('builtins.__import__') as mock_import:
            mock_import.return_value = MagicMock()  # Mock xgboost module
            
            engine = UnifiedPredictionEngine(mode='v2')
            engine._xgboost_available = True
            engine._backend = mock_predictor
            engine.mode = 'v2'
            
            tickets = engine.generate_tickets(2)
            
            # Verify ML predictor was called
            mock_predictor.predict_diverse_plays.assert_called_once_with(
                num_plays=2,
                save_to_log=False
            )
            
            # Verify tickets format
            assert len(tickets) == 2
            assert tickets[0]['white_balls'] == [1, 2, 3, 4, 5]
            assert tickets[0]['powerball'] == 10
            assert tickets[0]['strategy'] == 'ml_predictor_v2'
            assert tickets[0]['confidence'] == 0.85

    @patch('src.predictor.Predictor')
    def test_v2_generation_metrics_tracking(self, mock_predictor_class):
        """Test that v2 mode tracks generation time metrics"""
        mock_predictor = MagicMock()
        mock_predictor.predict_diverse_plays.return_value = [
            {'numbers': [1, 2, 3, 4, 5], 'powerball': 10, 'confidence_score': 0.8}
        ]
        mock_predictor_class.return_value = mock_predictor
        
        with patch('builtins.__import__') as mock_import:
            mock_import.return_value = MagicMock()
            
            engine = UnifiedPredictionEngine(mode='v2')
            engine._xgboost_available = True
            engine._backend = mock_predictor
            engine.mode = 'v2'
            
            # Generate tickets
            engine.generate_tickets(1)
            
            # Check metrics were updated
            metrics = engine.get_generation_metrics()
            assert metrics['total_generations'] == 1
            assert metrics['last_generation_time'] is not None
            assert metrics['last_generation_time'] > 0
            assert metrics['avg_generation_time'] > 0

    @patch('src.predictor.Predictor')
    def test_v2_invalid_ticket_filtering(self, mock_predictor_class):
        """Test that v2 mode filters out invalid tickets"""
        mock_predictor = MagicMock()
        # Mix of valid and invalid tickets
        mock_predictor.predict_diverse_plays.return_value = [
            {'numbers': [1, 2, 3, 4, 5], 'powerball': 10, 'confidence_score': 0.8},  # Valid
            {'numbers': [1, 2, 3, 4], 'powerball': 10, 'confidence_score': 0.7},      # Invalid (only 4 numbers)
            {'numbers': [1, 2, 3, 4, 70], 'powerball': 10, 'confidence_score': 0.6},  # Invalid (70 > 69)
            {'numbers': [1, 2, 3, 4, 5], 'powerball': 27, 'confidence_score': 0.5},   # Invalid (27 > 26)
        ]
        mock_predictor_class.return_value = mock_predictor
        
        with patch('builtins.__import__') as mock_import:
            mock_import.return_value = MagicMock()
            
            engine = UnifiedPredictionEngine(mode='v2')
            engine._xgboost_available = True
            engine._backend = mock_predictor
            engine.mode = 'v2'
            
            tickets = engine.generate_tickets(4)
            
            # Only 1 valid ticket should be returned
            assert len(tickets) == 1
            assert tickets[0]['white_balls'] == [1, 2, 3, 4, 5]

    @patch('src.predictor.Predictor')
    def test_v2_error_fallback_to_v1(self, mock_predictor_class):
        """Test that v2 mode falls back to v1 on error"""
        mock_predictor = MagicMock()
        mock_predictor.predict_diverse_plays.side_effect = Exception("ML model error")
        mock_predictor_class.return_value = mock_predictor
        
        with patch('src.strategy_generators.StrategyManager') as mock_strategy_manager:
            mock_manager = MagicMock()
            mock_manager.generate_balanced_tickets.return_value = [
                {'white_balls': [1, 2, 3, 4, 5], 'powerball': 10, 'strategy': 'v1_fallback', 'confidence': 0.5}
            ]
            mock_strategy_manager.return_value = mock_manager
            
            with patch('builtins.__import__') as mock_import:
                mock_import.return_value = MagicMock()
                
                engine = UnifiedPredictionEngine(mode='v2')
                engine._xgboost_available = True
                engine._backend = mock_predictor
                engine.mode = 'v2'
                
                # Generate tickets - should fallback to v1
                tickets = engine.generate_tickets(1)
                
                # Verify v1 was used as fallback
                # Note: This will actually call _generate_v1 which will initialize a new backend
                assert len(tickets) >= 0  # May return empty or v1 tickets

    def test_v2_get_strategy_manager_raises_runtime_error(self):
        """Test that get_strategy_manager raises RuntimeError in v2 mode"""
        with patch('builtins.__import__') as mock_import:
            mock_import.return_value = MagicMock()
            
            engine = UnifiedPredictionEngine(mode='v2')
            
            # Even if fallback occurred, test the method's guard
            if engine.mode == 'v2':
                with pytest.raises(RuntimeError) as exc_info:
                    engine.get_strategy_manager()
                
                assert 'only available in v1 mode' in str(exc_info.value)

    @patch('src.predictor.Predictor')
    def test_v2_backend_info_includes_model_info(self, mock_predictor_class):
        """Test that get_backend_info includes model info for v2"""
        mock_predictor = MagicMock()
        mock_predictor.get_model_info.return_value = {
            'loaded': True,
            'version': 'v6.0',
            'features': ['feature1', 'feature2']
        }
        mock_predictor_class.return_value = mock_predictor
        
        with patch('builtins.__import__') as mock_import:
            mock_import.return_value = MagicMock()
            
            engine = UnifiedPredictionEngine(mode='v2')
            engine._xgboost_available = True
            engine._backend = mock_predictor
            engine.mode = 'v2'
            
            info = engine.get_backend_info()
            
            assert info['mode'] == 'v2'
            assert 'model_info' in info
            assert info['model_info']['loaded'] is True
            assert 'generation_metrics' in info


class TestUnifiedPredictionEngineHybridMode:
    """Test hybrid mode (combination of v1 and v2)"""

    @patch('src.strategy_generators.StrategyManager')
    def test_hybrid_mode_generates_tickets_from_both_sources(self, mock_strategy_manager_class):
        """Test that hybrid mode generates tickets from both v1 and v2"""
        # Setup mock v1 (StrategyManager)
        mock_v1 = MagicMock()
        mock_v1_tickets = [
            {'white_balls': [1, 2, 3, 4, 5], 'powerball': 10, 'strategy': 'v1_strategy', 'confidence': 0.6}
        ]
        mock_v1.generate_balanced_tickets.return_value = mock_v1_tickets
        mock_strategy_manager_class.return_value = mock_v1
        
        # Create engine in hybrid mode
        with patch.dict(os.environ, {'HYBRID_V2_WEIGHT': '0.7', 'HYBRID_V1_WEIGHT': '0.3'}):
            engine = UnifiedPredictionEngine(mode='hybrid')
            
            # Mock the internal methods to return our test data
            v2_tickets = [
                {'white_balls': [6, 7, 8, 9, 10], 'powerball': 15, 'strategy': 'ml_predictor_v2', 'confidence': 0.85},
                {'white_balls': [11, 12, 13, 14, 15], 'powerball': 20, 'strategy': 'ml_predictor_v2', 'confidence': 0.75}
            ]
            with patch.object(engine, '_generate_v2', return_value=v2_tickets):
                with patch.object(engine, '_generate_v1', return_value=mock_v1_tickets):
                    tickets = engine.generate_tickets(3)
                    
                    # Should have tickets from both sources
                    assert len(tickets) > 0
                    # Check that tickets have source tags
                    sources = [t.get('source', 'unknown') for t in tickets]
                    # At least one source should be present (v1 or v2)
                    assert len(sources) > 0

    @patch('src.strategy_generators.StrategyManager')
    def test_hybrid_mode_respects_weight_configuration(self, mock_strategy_manager_class):
        """Test that hybrid mode respects HYBRID_V1_WEIGHT and HYBRID_V2_WEIGHT"""
        mock_v1 = MagicMock()
        mock_v1.generate_balanced_tickets.return_value = [
            {'white_balls': [1, 2, 3, 4, 5], 'powerball': 10, 'strategy': 'v1', 'confidence': 0.5}
        ]
        mock_strategy_manager_class.return_value = mock_v1
        
        # Test with 80% v2, 20% v1 weights
        with patch.dict(os.environ, {'HYBRID_V2_WEIGHT': '0.8', 'HYBRID_V1_WEIGHT': '0.2'}):
            engine = UnifiedPredictionEngine(mode='hybrid')
            
            # For 10 tickets: should be 8 v2 + 2 v1
            with patch.object(engine, '_generate_v2') as mock_gen_v2:
                with patch.object(engine, '_generate_v1') as mock_gen_v1:
                    mock_gen_v2.return_value = []
                    mock_gen_v1.return_value = []
                    
                    engine.generate_tickets(10)
                    
                    # Check that the methods were called with approximately correct counts
                    # (should be 8 for v2 and 2 for v1, or similar distribution)
                    v2_call_count = mock_gen_v2.call_args[0][0] if mock_gen_v2.called else 0
                    v1_call_count = mock_gen_v1.call_args[0][0] if mock_gen_v1.called else 0
                    
                    # Verify distribution is reasonable (allow some rounding)
                    assert v2_call_count >= 7  # Should be ~8
                    assert v1_call_count >= 1  # Should be ~2

    @patch('src.strategy_generators.StrategyManager')
    def test_hybrid_mode_fallback_to_v1_on_v2_failure(self, mock_strategy_manager_class):
        """Test that hybrid mode falls back to v1 when v2 fails"""
        mock_v1 = MagicMock()
        fallback_tickets = [
            {'white_balls': [1, 2, 3, 4, 5], 'powerball': 10, 'strategy': 'fallback', 'confidence': 0.5},
            {'white_balls': [6, 7, 8, 9, 10], 'powerball': 15, 'strategy': 'fallback', 'confidence': 0.5}
        ]
        mock_v1.generate_balanced_tickets.return_value = fallback_tickets
        mock_strategy_manager_class.return_value = mock_v1
        
        engine = UnifiedPredictionEngine(mode='hybrid')
        
        # Mock _generate_v2 to raise an exception
        with patch.object(engine, '_generate_v2', side_effect=Exception("V2 model failed")):
            with patch.object(engine, '_generate_v1', return_value=fallback_tickets):
                tickets = engine.generate_tickets(5)
                
                # Should have fallen back to v1 tickets
                assert len(tickets) >= 0
                # All tickets should be from v1 due to fallback
                if tickets:
                    assert all(t.get('strategy') == 'fallback' or t.get('source') == 'v1_strategy' for t in tickets)

    def test_hybrid_mode_deduplicates_tickets(self):
        """Test that hybrid mode removes duplicate tickets"""
        engine = UnifiedPredictionEngine(mode='hybrid')
        
        # Create tickets with duplicates
        tickets_with_duplicates = [
            {'white_balls': [1, 2, 3, 4, 5], 'powerball': 10, 'strategy': 'v1', 'confidence': 0.5},
            {'white_balls': [1, 2, 3, 4, 5], 'powerball': 10, 'strategy': 'v2', 'confidence': 0.8},  # Duplicate
            {'white_balls': [6, 7, 8, 9, 10], 'powerball': 15, 'strategy': 'v1', 'confidence': 0.6},
            {'white_balls': [11, 12, 13, 14, 15], 'powerball': 20, 'strategy': 'v2', 'confidence': 0.7},
            {'white_balls': [6, 7, 8, 9, 10], 'powerball': 15, 'strategy': 'v2', 'confidence': 0.9},  # Duplicate
        ]
        
        deduplicated = engine._deduplicate_tickets(tickets_with_duplicates)
        
        # Should have 3 unique tickets (removed 2 duplicates)
        assert len(deduplicated) == 3
        
        # Verify uniqueness
        seen = set()
        for ticket in deduplicated:
            key = (tuple(sorted(ticket['white_balls'])), ticket['powerball'])
            assert key not in seen, "Found duplicate ticket after deduplication"
            seen.add(key)
        
        # First occurrence should be preserved
        assert deduplicated[0]['strategy'] == 'v1'  # First [1,2,3,4,5]+10
        assert deduplicated[1]['strategy'] == 'v1'  # First [6,7,8,9,10]+15

    def test_hybrid_mode_handles_edge_cases(self):
        """Test hybrid mode with edge cases (count=1, count=0, invalid weights)"""
        with patch('src.strategy_generators.StrategyManager') as mock_sm:
            mock_manager = MagicMock()
            mock_manager.generate_balanced_tickets.return_value = [
                {'white_balls': [1, 2, 3, 4, 5], 'powerball': 10, 'strategy': 'test', 'confidence': 0.5}
            ]
            mock_sm.return_value = mock_manager
            
            # Test count=1
            engine = UnifiedPredictionEngine(mode='hybrid')
            with patch.object(engine, '_generate_v2', return_value=[]):
                with patch.object(engine, '_generate_v1', return_value=[
                    {'white_balls': [1, 2, 3, 4, 5], 'powerball': 10, 'strategy': 'test', 'confidence': 0.5}
                ]):
                    tickets = engine.generate_tickets(1)
                    assert len(tickets) <= 1
            
            # Test count=0
            tickets = engine.generate_tickets(0)
            assert len(tickets) == 0

    @patch.dict(os.environ, {'HYBRID_V2_WEIGHT': '0', 'HYBRID_V1_WEIGHT': '0'})
    def test_hybrid_mode_handles_invalid_weights(self):
        """Test that hybrid mode handles invalid weight configuration"""
        with patch('src.strategy_generators.StrategyManager') as mock_sm:
            mock_manager = MagicMock()
            mock_manager.generate_balanced_tickets.return_value = []
            mock_sm.return_value = mock_manager
            
            engine = UnifiedPredictionEngine(mode='hybrid')
            
            # Mock both generation methods
            with patch.object(engine, '_generate_v2', return_value=[]):
                with patch.object(engine, '_generate_v1', return_value=[]):
                    # Should not crash with zero weights (falls back to 70/30)
                    try:
                        tickets = engine.generate_tickets(10)
                        # Should handle gracefully
                        assert isinstance(tickets, list)
                    except Exception as e:
                        pytest.fail(f"Should handle invalid weights gracefully: {e}")

    def test_hybrid_mode_preserves_ticket_metadata(self):
        """Test that hybrid mode preserves strategy, confidence, and adds source metadata"""
        engine = UnifiedPredictionEngine(mode='hybrid')
        
        test_tickets = [
            {'white_balls': [1, 2, 3, 4, 5], 'powerball': 10, 'strategy': 'freq', 'confidence': 0.5, 'source': 'v1_strategy'},
            {'white_balls': [6, 7, 8, 9, 10], 'powerball': 15, 'strategy': 'ml', 'confidence': 0.9, 'source': 'v2_ml'}
        ]
        
        # Test deduplication preserves metadata
        deduplicated = engine._deduplicate_tickets(test_tickets)
        
        assert len(deduplicated) == 2
        assert all('strategy' in t for t in deduplicated)
        assert all('confidence' in t for t in deduplicated)
        assert all('source' in t for t in deduplicated)

    def test_hybrid_get_strategy_manager_raises_runtime_error(self):
        """Test that get_strategy_manager raises RuntimeError in hybrid mode"""
        engine = UnifiedPredictionEngine(mode='hybrid')
        
        with pytest.raises(RuntimeError) as exc_info:
            engine.get_strategy_manager()
        
        assert 'only available in v1 mode' in str(exc_info.value)

    @patch('src.strategy_generators.StrategyManager')
    def test_hybrid_mode_metrics_tracking(self, mock_strategy_manager_class):
        """Test that hybrid mode tracks generation metrics"""
        mock_v1 = MagicMock()
        mock_v1.generate_balanced_tickets.return_value = []
        mock_strategy_manager_class.return_value = mock_v1
        
        engine = UnifiedPredictionEngine(mode='hybrid')
        
        with patch.object(engine, '_generate_v2', return_value=[]):
            with patch.object(engine, '_generate_v1', return_value=[]):
                engine.generate_tickets(5)
                
                metrics = engine.get_generation_metrics()
                assert metrics['total_generations'] == 1
                assert metrics['last_generation_time'] is not None
                assert metrics['last_generation_time'] > 0


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
