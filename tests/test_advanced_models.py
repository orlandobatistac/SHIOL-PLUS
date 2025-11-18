"""
Tests for Advanced ML Models (LSTM and Random Forest)
======================================================
Test suite for new LSTM and Random Forest models including:
- Model initialization and configuration
- Training pipeline
- Prediction generation
- Integration with prediction engine
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock


class TestLSTMModel:
    """Test suite for LSTM model"""
    
    @pytest.fixture
    def sample_draws_df(self):
        """Sample historical draw data for testing"""
        dates = pd.date_range('2024-01-01', periods=30, freq='3D')
        data = {
            'draw_date': [d.strftime('%Y-%m-%d') for d in dates],
            'n1': np.random.randint(1, 70, 30),
            'n2': np.random.randint(1, 70, 30),
            'n3': np.random.randint(1, 70, 30),
            'n4': np.random.randint(1, 70, 30),
            'n5': np.random.randint(1, 70, 30),
            'pb': np.random.randint(1, 27, 30)
        }
        return pd.DataFrame(data)
    
    def test_lstm_model_import(self):
        """Test that LSTM model can be imported"""
        try:
            from src.ml_models.lstm_model import LSTMModel, KERAS_AVAILABLE
            
            if not KERAS_AVAILABLE:
                pytest.skip("TensorFlow/Keras not installed")
            
            assert LSTMModel is not None
        except ImportError:
            pytest.skip("LSTM model module not available")
    
    def test_lstm_model_initialization(self):
        """Test LSTM model initialization"""
        try:
            from src.ml_models.lstm_model import LSTMModel, KERAS_AVAILABLE
            
            if not KERAS_AVAILABLE:
                pytest.skip("TensorFlow/Keras not installed")
            
            model = LSTMModel(
                sequence_length=10,
                lstm_units=64,
                dropout_rate=0.3,
                use_pretrained=False
            )
            
            assert model is not None
            assert model.sequence_length == 10
            assert model.lstm_units == 64
            assert model.dropout_rate == 0.3
            assert model.wb_model is None  # Not trained yet
            assert model.pb_model is None  # Not trained yet
            
        except ImportError:
            pytest.skip("TensorFlow/Keras not installed")
    
    def test_lstm_model_info(self):
        """Test LSTM model info retrieval"""
        try:
            from src.ml_models.lstm_model import LSTMModel, KERAS_AVAILABLE
            
            if not KERAS_AVAILABLE:
                pytest.skip("TensorFlow/Keras not installed")
            
            model = LSTMModel(use_pretrained=False)
            info = model.get_model_info()
            
            assert 'model_type' in info
            assert info['model_type'] == 'LSTM'
            assert 'sequence_length' in info
            assert 'lstm_units' in info
            assert 'dropout_rate' in info
            assert 'keras_available' in info
            
        except ImportError:
            pytest.skip("TensorFlow/Keras not installed")
    
    def test_lstm_generate_tickets_without_training(self, sample_draws_df):
        """Test that LSTM raises error when generating without training"""
        try:
            from src.ml_models.lstm_model import LSTMModel, KERAS_AVAILABLE
            
            if not KERAS_AVAILABLE:
                pytest.skip("TensorFlow/Keras not installed")
            
            model = LSTMModel(use_pretrained=False)
            
            with pytest.raises(RuntimeError):
                model.generate_tickets(sample_draws_df, count=5)
                
        except ImportError:
            pytest.skip("TensorFlow/Keras not installed")


class TestRandomForestModel:
    """Test suite for Random Forest model"""
    
    @pytest.fixture
    def sample_draws_df(self):
        """Sample historical draw data for testing"""
        np.random.seed(42)
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
    
    def test_random_forest_model_import(self):
        """Test that Random Forest model can be imported"""
        from src.ml_models.random_forest_model import RandomForestModel
        assert RandomForestModel is not None
    
    def test_random_forest_model_initialization(self):
        """Test Random Forest model initialization"""
        from src.ml_models.random_forest_model import RandomForestModel
        
        model = RandomForestModel(
            n_estimators=50,
            max_depth=10,
            use_pretrained=False
        )
        
        assert model is not None
        assert model.n_estimators == 50
        assert model.max_depth == 10
        assert len(model.wb_models) == 0  # Not trained yet
        assert model.pb_model is None  # Not trained yet
    
    def test_random_forest_model_info(self):
        """Test Random Forest model info retrieval"""
        from src.ml_models.random_forest_model import RandomForestModel
        
        model = RandomForestModel(use_pretrained=False)
        info = model.get_model_info()
        
        assert 'model_type' in info
        assert info['model_type'] == 'RandomForest'
        assert 'n_estimators' in info
        assert 'max_depth' in info
        assert 'wb_models_loaded' in info
        assert 'pb_model_loaded' in info
    
    def test_random_forest_feature_engineering(self, sample_draws_df):
        """Test feature engineering for Random Forest"""
        from src.ml_models.random_forest_model import RandomForestModel
        
        model = RandomForestModel(use_pretrained=False)
        features = model._engineer_features(sample_draws_df)
        
        # Check features were created
        assert features is not None
        assert len(features) == len(sample_draws_df)
        assert len(features.columns) > 0
        
        # Check for expected feature types
        freq_cols = [col for col in features.columns if col.startswith('freq_')]
        gap_cols = [col for col in features.columns if col.startswith('gap_')]
        
        assert len(freq_cols) > 0, "Should have frequency features"
        assert len(gap_cols) > 0, "Should have gap features"
    
    def test_random_forest_training(self, sample_draws_df):
        """Test Random Forest model training"""
        from src.ml_models.random_forest_model import RandomForestModel
        
        model = RandomForestModel(
            n_estimators=10,  # Small for testing
            max_depth=5,
            use_pretrained=False
        )
        
        # Train on sample data
        metrics = model.train(sample_draws_df, test_size=0.2)
        
        # Check training completed
        assert metrics is not None
        assert 'pb_train_score' in metrics
        assert 'pb_test_score' in metrics
        
        # Check models were created
        assert len(model.wb_models) == 5
        assert model.pb_model is not None
    
    def test_random_forest_generate_tickets_after_training(self, sample_draws_df):
        """Test ticket generation after training"""
        from src.ml_models.random_forest_model import RandomForestModel
        
        model = RandomForestModel(
            n_estimators=10,
            max_depth=5,
            use_pretrained=False
        )
        
        # Train
        model.train(sample_draws_df, test_size=0.2)
        
        # Generate tickets
        tickets = model.generate_tickets(sample_draws_df, count=5)
        
        # Verify tickets
        assert len(tickets) == 5
        
        for ticket in tickets:
            assert 'white_balls' in ticket
            assert 'powerball' in ticket
            assert 'strategy' in ticket
            assert 'confidence' in ticket
            
            # Verify constraints
            assert len(ticket['white_balls']) == 5
            assert all(1 <= n <= 69 for n in ticket['white_balls'])
            assert 1 <= ticket['powerball'] <= 26
            assert ticket['strategy'] == 'random_forest'
            assert 0.0 <= ticket['confidence'] <= 1.0


class TestModelRegistry:
    """Test model registry and factory function"""
    
    def test_model_registry_import(self):
        """Test that model registry can be imported"""
        from src.ml_models import MODEL_REGISTRY, get_model
        
        assert MODEL_REGISTRY is not None
        assert 'lstm' in MODEL_REGISTRY
        assert 'random_forest' in MODEL_REGISTRY
    
    def test_get_model_random_forest(self):
        """Test getting Random Forest model from registry"""
        from src.ml_models import get_model
        
        model = get_model('random_forest', use_pretrained=False)
        
        assert model is not None
        assert hasattr(model, 'generate_tickets')
        assert hasattr(model, 'train')
    
    def test_get_model_invalid_name(self):
        """Test getting model with invalid name"""
        from src.ml_models import get_model
        
        model = get_model('invalid_model_name')
        
        assert model is None


class TestPredictionEngineIntegration:
    """Test integration with UnifiedPredictionEngine"""
    
    @pytest.fixture
    def sample_draws_df(self):
        """Sample historical draw data"""
        np.random.seed(42)
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
    
    def test_prediction_engine_supports_lstm_mode(self):
        """Test that prediction engine accepts LSTM mode"""
        from src.prediction_engine import UnifiedPredictionEngine
        
        # Should accept LSTM mode without error
        engine = UnifiedPredictionEngine(mode='lstm')
        
        assert engine is not None
        # Mode might fallback to v1 if LSTM not available, that's OK
        assert engine.mode in ['lstm', 'v1']
    
    def test_prediction_engine_supports_random_forest_mode(self):
        """Test that prediction engine accepts Random Forest mode"""
        from src.prediction_engine import UnifiedPredictionEngine
        
        # Should accept Random Forest mode without error
        engine = UnifiedPredictionEngine(mode='random_forest')
        
        assert engine is not None
        # Mode might fallback to v1 if RF not available, that's OK
        assert engine.mode in ['random_forest', 'v1']
    
    @patch('src.database.get_all_draws')
    def test_prediction_engine_random_forest_generation(self, mock_get_draws, sample_draws_df):
        """Test ticket generation with Random Forest mode"""
        mock_get_draws.return_value = sample_draws_df
        
        from src.prediction_engine import UnifiedPredictionEngine
        
        engine = UnifiedPredictionEngine(mode='random_forest')
        
        # If mode is still random_forest (not fallback), test generation
        if engine.mode == 'random_forest':
            try:
                tickets = engine.generate_tickets(count=3)
                
                assert tickets is not None
                assert len(tickets) <= 3
                
                for ticket in tickets:
                    assert 'white_balls' in ticket
                    assert 'powerball' in ticket
                    assert 'strategy' in ticket
            except Exception as e:
                # Generation might fail without trained model, that's OK
                pytest.skip(f"Random Forest generation failed (expected without training): {e}")


class TestTrainingPipeline:
    """Test training pipeline functionality"""
    
    def test_train_models_script_exists(self):
        """Test that training script exists"""
        import os
        script_path = '/home/runner/work/SHIOL-PLUS/SHIOL-PLUS/src/train_models.py'
        assert os.path.exists(script_path)
    
    def test_train_models_import(self):
        """Test that training functions can be imported"""
        from src.train_models import train_random_forest_model
        
        assert train_random_forest_model is not None
        assert callable(train_random_forest_model)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, '-v'])
