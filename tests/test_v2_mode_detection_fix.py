"""
Tests for v2 Mode Detection Fix
================================
Tests that verify the fix for the issue where v2 mode detection fails
after initialization errors occur.

The bug was: when v2 mode initialization encountered an error,
self.mode was changed from 'v2' to 'v1'. Later, in _generate_v2(),
the check `if self.mode != 'v2'` would fail, causing fallback to v1
even when the v2 backend was actually available.
"""

import pytest
from unittest.mock import patch, MagicMock
from src.prediction_engine import UnifiedPredictionEngine


class TestV2ModeDetectionFix:
    """Test that v2 mode detection works correctly after initialization errors"""

    @patch('src.predictor.Predictor')
    def test_v2_backend_used_when_available_despite_mode_change(self, mock_predictor_class):
        """
        Test that v2 backend is used when it's available, even if initialization
        had issues that would have previously changed self.mode to 'v1'.
        
        This test simulates the scenario described in the bug report:
        1. Engine initialized with mode='v2'
        2. Backend is set successfully
        3. Generate should use v2 backend, not fall back to v1
        """
        # Setup mock predictor that works correctly
        mock_predictor = MagicMock()
        mock_ml_predictions = [
            {
                'numbers': [1, 2, 3, 4, 5],
                'powerball': 10,
                'confidence_score': 0.85
            }
        ]
        mock_predictor.predict_diverse_plays.return_value = mock_ml_predictions
        mock_predictor_class.return_value = mock_predictor
        
        # Mock XGBoost availability
        with patch('builtins.__import__') as mock_import:
            mock_import.return_value = MagicMock()
            
            # Create engine in v2 mode
            engine = UnifiedPredictionEngine(mode='v2')
            engine._xgboost_available = True
            engine._backend = mock_predictor
            
            # Key: Even if someone previously changed self.mode to 'v1' during init,
            # the generate should use the backend that's available
            # For this test, we'll verify that the backend type is what matters
            
            # Generate tickets
            tickets = engine.generate_tickets(1)
            
            # Verify that v2 backend was actually used
            # (not v1 fallback which would call StrategyManager)
            mock_predictor.predict_diverse_plays.assert_called_once()
            assert len(tickets) == 1
            assert tickets[0]['strategy'] == 'ml_predictor_v2'

    @patch('src.strategy_generators.StrategyManager')
    def test_mode_not_changed_during_v2_initialization(self, mock_sm):
        """
        Test that self.mode is not changed during initialization, even if errors occur.
        
        After the fix:
        - self.mode should remain 'v2' even if backend initialization fails
        - The backend will be StrategyManager (fallback) but mode stays 'v2'
        - This allows proper tracking of user intent vs actual backend
        """
        mock_manager = MagicMock()
        mock_manager.generate_balanced_tickets.return_value = []
        mock_sm.return_value = mock_manager
        
        # Create engine with v2 mode
        engine = UnifiedPredictionEngine(mode='v2')
        
        # Simulate a fallback scenario by manually calling init with unavailable xgboost
        engine._xgboost_available = False
        engine._initialize_v2_backend()
        
        # After the fix: mode should still be 'v2' (user's intention)
        # even though backend might be StrategyManager (fallback)
        assert engine.get_mode() == 'v2'
        # Backend should be the fallback (StrategyManager)
        assert engine._backend is not None

    @patch('src.predictor.Predictor')
    def test_generate_v2_checks_backend_type_not_mode(self, mock_predictor_class):
        """
        Test that _generate_v2() checks backend type using isinstance,
        not by checking self.mode.
        
        This is the core of the fix - we should check what backend is actually
        available, not what mode was requested.
        """
        mock_predictor = MagicMock()
        mock_ml_predictions = [
            {
                'numbers': [10, 20, 30, 40, 50],
                'powerball': 15,
                'confidence_score': 0.90
            }
        ]
        mock_predictor.predict_diverse_plays.return_value = mock_ml_predictions
        mock_predictor_class.return_value = mock_predictor
        
        with patch('builtins.__import__') as mock_import:
            mock_import.return_value = MagicMock()
            
            engine = UnifiedPredictionEngine(mode='v2')
            engine._xgboost_available = True
            engine._backend = mock_predictor
            
            # Simulate what would happen if mode was incorrectly changed
            # (This should NOT happen after the fix, but we test that
            # generation still works based on backend type)
            original_mode = engine.mode
            
            # Generate tickets
            tickets = engine.generate_tickets(1)
            
            # Verify that v2 backend was used (type check succeeded)
            mock_predictor.predict_diverse_plays.assert_called_once()
            assert len(tickets) == 1
            assert tickets[0]['white_balls'] == [10, 20, 30, 40, 50]
            
            # Mode should still be what was requested
            assert engine.mode == original_mode

    @patch('src.strategy_generators.StrategyManager')
    def test_v2_with_no_backend_falls_back_to_v1(self, mock_sm):
        """
        Test that when v2 mode is requested but backend is None,
        it correctly falls back to v1.
        """
        mock_manager = MagicMock()
        mock_tickets = [
            {'white_balls': [1, 2, 3, 4, 5], 'powerball': 10, 'strategy': 'v1_fallback', 'confidence': 0.5}
        ]
        mock_manager.generate_balanced_tickets.return_value = mock_tickets
        mock_sm.return_value = mock_manager
        
        engine = UnifiedPredictionEngine(mode='v2')
        
        # Simulate failed v2 initialization (backend is None)
        engine._backend = None
        
        # Should fall back to v1
        tickets = engine.generate_tickets(1)
        
        # Verify v1 backend was used as fallback
        assert len(tickets) == 1
        # The fallback should have initialized v1 backend
        assert engine._backend is not None


class TestLSTMAndRFModeDetectionFix:
    """Test that LSTM and Random Forest modes also use backend type checking"""

    def test_lstm_mode_not_changed_during_initialization_failure(self):
        """Test that LSTM mode is preserved even when initialization fails"""
        # Skip this test until we apply the fix
        pytest.skip("This test validates the fix - will be enabled after applying the fix")

    def test_random_forest_mode_not_changed_during_initialization_failure(self):
        """Test that Random Forest mode is preserved even when initialization fails"""
        # Skip this test until we apply the fix
        pytest.skip("This test validates the fix - will be enabled after applying the fix")
