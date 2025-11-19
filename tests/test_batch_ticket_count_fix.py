"""
Test to verify that ticket generation respects the count parameter for large batches.

This test specifically validates the fix for the bug where batch_size=100
only generated 10 tickets per mode.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock

from src.batch_generator import BatchTicketGenerator
from src.prediction_engine import UnifiedPredictionEngine


class TestBatchTicketCountFix:
    """Test that verifies the batch ticket count bug is fixed."""
    
    @patch('src.batch_generator.insert_batch_tickets')
    @patch('src.batch_generator.UnifiedPredictionEngine')
    def test_batch_generator_generates_100_tickets_per_mode(self, mock_engine_class, mock_insert):
        """
        Test that BatchTicketGenerator with batch_size=100 generates 100 tickets per mode.
        
        This is the main test for the bug fix.
        """
        # Mock the prediction engine to return exactly the requested count
        def mock_generate_tickets(count):
            """Mock that generates exactly 'count' tickets"""
            return [
                {
                    'white_balls': [1, 2, 3, 4, 5],
                    'powerball': 10,
                    'strategy': 'test',
                    'confidence': 0.8
                }
                for _ in range(count)
            ]
        
        mock_engine = MagicMock()
        mock_engine.generate_tickets.side_effect = mock_generate_tickets
        mock_engine_class.return_value = mock_engine
        
        # Mock database insert to return the count of inserted tickets
        mock_insert.side_effect = lambda tickets, mode, pipeline_run_id: len(tickets)
        
        # Create generator with batch_size=100
        generator = BatchTicketGenerator(
            batch_size=100,
            modes=['random_forest', 'lstm'],
            auto_cleanup=False
        )
        
        # Run batch generation
        result = generator.generate_batch(
            pipeline_run_id='test-run-100',
            async_mode=False
        )
        
        # Verify that generate_tickets was called with count=100 for each mode
        calls = mock_engine.generate_tickets.call_args_list
        assert len(calls) == 2, f"Expected 2 calls to generate_tickets, got {len(calls)}"
        
        for call in calls:
            args, kwargs = call
            count = kwargs.get('count') or (args[0] if args else None)
            assert count == 100, f"Expected count=100, got count={count}"
        
        # Verify that 100 tickets were inserted for each mode
        insert_calls = mock_insert.call_args_list
        assert len(insert_calls) == 2, f"Expected 2 insert calls, got {len(insert_calls)}"
        
        for call in insert_calls:
            args, kwargs = call
            tickets = args[0]
            assert len(tickets) == 100, f"Expected 100 tickets, got {len(tickets)}"
        
        # Verify the result shows 200 total tickets (100 per mode)
        assert result['result']['total_tickets'] == 200, \
            f"Expected 200 total tickets, got {result['result']['total_tickets']}"
    
    def test_predict_diverse_plays_scales_num_candidates(self):
        """
        Test that predict_diverse_plays scales num_candidates for large num_plays.
        
        This tests the specific fix in predictor.py.
        """
        # Skip this test if predictor module can't be imported
        try:
            from src.predictor import Predictor
        except ImportError:
            pytest.skip("Predictor module not available")
        
        with patch('src.predictor.DeterministicGenerator') as mock_det_gen_class:
            # Mock the deterministic generator
            mock_det_gen = MagicMock()
            mock_predictions = [
                {
                    'numbers': [i, i+1, i+2, i+3, i+4],
                    'powerball': (i % 26) + 1,
                    'score_total': 0.8 - i * 0.001
                }
                for i in range(1, 101)  # Generate 100 predictions
            ]
            mock_det_gen.generate_diverse_predictions.return_value = mock_predictions
            mock_det_gen_class.return_value = mock_det_gen
            
            # Create predictor
            with patch('src.predictor.DataLoader'):
                predictor = Predictor()
                predictor.deterministic_generator = mock_det_gen
                predictor.historical_data = pd.DataFrame({'dummy': [1, 2, 3]})  # Non-empty
            
            # Mock predict_probabilities to return dummy probs
            with patch.object(predictor, 'predict_probabilities', return_value=(
                np.ones(69) / 69,  # wb_probs
                np.ones(26) / 26   # pb_probs
            )):
                # Call with num_plays=100
                predictions = predictor.predict_diverse_plays(num_plays=100, save_to_log=False)
            
            # Verify that generate_diverse_predictions was called with scaled num_candidates
            call_args = mock_det_gen.generate_diverse_predictions.call_args
            args, kwargs = call_args
            
            assert 'num_candidates' in kwargs, "num_candidates not passed to generate_diverse_predictions"
            num_candidates = kwargs['num_candidates']
            
            # For num_plays=100, expected num_candidates = max(2000, 100 * 50) = 5000
            expected_candidates = max(2000, 100 * 50)
            assert num_candidates == expected_candidates, \
                f"Expected num_candidates={expected_candidates}, got {num_candidates}"
            
            # Verify that all 100 predictions were returned
            assert len(predictions) == 100, f"Expected 100 predictions, got {len(predictions)}"
    
    def test_predict_diverse_plays_uses_default_for_small_batches(self):
        """
        Test that predict_diverse_plays uses default num_candidates for small num_plays.
        """
        # Skip this test if predictor module can't be imported
        try:
            from src.predictor import Predictor
        except ImportError:
            pytest.skip("Predictor module not available")
        
        with patch('src.predictor.DeterministicGenerator') as mock_det_gen_class:
            # Mock the deterministic generator
            mock_det_gen = MagicMock()
            mock_predictions = [
                {
                    'numbers': [i, i+1, i+2, i+3, i+4],
                    'powerball': (i % 26) + 1,
                    'score_total': 0.8
                }
                for i in range(1, 6)  # Generate 5 predictions
            ]
            mock_det_gen.generate_diverse_predictions.return_value = mock_predictions
            mock_det_gen_class.return_value = mock_det_gen
            
            # Create predictor
            with patch('src.predictor.DataLoader'):
                predictor = Predictor()
                predictor.deterministic_generator = mock_det_gen
                predictor.historical_data = pd.DataFrame({'dummy': [1, 2, 3]})  # Non-empty
            
            # Mock predict_probabilities
            with patch.object(predictor, 'predict_probabilities', return_value=(
                np.ones(69) / 69,
                np.ones(26) / 26
            )):
                # Call with num_plays=5 (small batch)
                predictions = predictor.predict_diverse_plays(num_plays=5, save_to_log=False)
            
            # Verify that generate_diverse_predictions was called with default num_candidates
            call_args = mock_det_gen.generate_diverse_predictions.call_args
            args, kwargs = call_args
            
            assert 'num_candidates' in kwargs, "num_candidates not passed"
            num_candidates = kwargs['num_candidates']
            
            # For num_plays=5, expected num_candidates = 2000 (default)
            assert num_candidates == 2000, \
                f"Expected num_candidates=2000 for small batch, got {num_candidates}"


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v'])
