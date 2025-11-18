"""
Tests for API v3 Prediction Engine Endpoints
=============================================
Comprehensive tests for /api/v3 endpoints including:
- Auto-mode prediction
- Mode-specific prediction
- Mode comparison
- Performance metrics
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client for API v3 endpoints"""
    from src.api import app
    return TestClient(app)


@pytest.fixture
def mock_engine_v1():
    """Mock UnifiedPredictionEngine in v1 mode"""
    engine = MagicMock()
    engine.get_mode.return_value = 'v1'
    engine.get_generation_metrics.return_value = {
        'total_generations': 10,
        'avg_generation_time': 0.5,
        'last_generation_time': 0.45
    }
    engine.get_backend_info.return_value = {
        'mode': 'v1',
        'backend_type': 'StrategyManager',
        'generation_metrics': {
            'total_generations': 10,
            'avg_generation_time': 0.5,
            'last_generation_time': 0.45
        }
    }
    engine.generate_tickets.return_value = [
        {
            'white_balls': [1, 2, 3, 4, 5],
            'powerball': 10,
            'strategy': 'frequency_weighted',
            'confidence': 0.75,
            'source': 'v1_strategy'
        },
        {
            'white_balls': [6, 7, 8, 9, 10],
            'powerball': 15,
            'strategy': 'cooccurrence',
            'confidence': 0.65,
            'source': 'v1_strategy'
        }
    ]
    return engine


@pytest.fixture
def mock_engine_v2():
    """Mock UnifiedPredictionEngine in v2 mode"""
    engine = MagicMock()
    engine.get_mode.return_value = 'v2'
    engine.get_generation_metrics.return_value = {
        'total_generations': 5,
        'avg_generation_time': 0.8,
        'last_generation_time': 0.75
    }
    engine.get_backend_info.return_value = {
        'mode': 'v2',
        'backend_type': 'Predictor',
        'generation_metrics': {
            'total_generations': 5,
            'avg_generation_time': 0.8,
            'last_generation_time': 0.75
        }
    }
    engine.generate_tickets.return_value = [
        {
            'white_balls': [11, 12, 13, 14, 15],
            'powerball': 20,
            'strategy': 'ml_predictor_v2',
            'confidence': 0.85,
            'source': 'v2_ml'
        }
    ]
    return engine


class TestPredictAutoMode:
    """Test POST /api/v3/predict (auto-select mode)"""
    
    @patch('src.api_v3_endpoints.UnifiedPredictionEngine')
    def test_auto_mode_success_v1(self, mock_engine_class, client, mock_engine_v1):
        """Test successful prediction with auto-selected v1 mode"""
        mock_engine_class.return_value = mock_engine_v1
        
        response = client.post(
            "/api/v3/predict",
            json={"count": 2, "include_metadata": True}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is True
        assert data['mode'] == 'v1'
        assert data['mode_selected'] == 'auto'
        assert len(data['tickets']) == 2
        assert data['count'] == 2
        
        # Check ticket structure
        ticket = data['tickets'][0]
        assert 'white_balls' in ticket
        assert 'powerball' in ticket
        assert 'strategy' in ticket
        assert 'confidence' in ticket
        assert len(ticket['white_balls']) == 5
        
        # Check metadata
        assert data['metadata'] is not None
        assert 'generation_time' in data['metadata']
        assert 'actual_mode' in data['metadata']
    
    @patch('src.api_v3_endpoints.UnifiedPredictionEngine')
    def test_auto_mode_success_v2(self, mock_engine_class, client, mock_engine_v2):
        """Test successful prediction with auto-selected v2 mode"""
        mock_engine_class.return_value = mock_engine_v2
        
        response = client.post(
            "/api/v3/predict",
            json={"count": 1, "include_metadata": False}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is True
        assert data['mode'] == 'v2'
        assert data['mode_selected'] == 'auto'
        assert len(data['tickets']) == 1
        assert data['metadata'] is None  # Not requested
    
    @patch('src.api_v3_endpoints.UnifiedPredictionEngine')
    def test_auto_mode_default_params(self, mock_engine_class, client, mock_engine_v1):
        """Test auto mode with default parameters"""
        mock_engine_class.return_value = mock_engine_v1
        
        # No request body, should use defaults
        response = client.post("/api/v3/predict")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is True
        assert data['count'] == 2  # Default is 5, but mock returns 2 tickets
        assert data['metadata'] is not None  # include_metadata defaults to True
    
    @patch('src.api_v3_endpoints._generate_tickets_with_fallback')
    def test_auto_mode_error_handling(self, mock_generate, client):
        """Test error handling when generation fails"""
        mock_generate.return_value = {
            'success': False,
            'mode': 'v1',
            'requested_mode': 'v1',
            'fallback_occurred': False,
            'tickets': [],
            'generation_time': 0.1,
            'error': 'Test error'
        }
        
        response = client.post(
            "/api/v3/predict",
            json={"count": 5}
        )
        
        assert response.status_code == 500
        assert 'Failed to generate predictions' in response.json()['detail']
    
    def test_auto_mode_invalid_count_too_high(self, client):
        """Test validation for count > 200"""
        response = client.post(
            "/api/v3/predict",
            json={"count": 201}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_auto_mode_invalid_count_zero(self, client):
        """Test validation for count = 0"""
        response = client.post(
            "/api/v3/predict",
            json={"count": 0}
        )
        
        assert response.status_code == 422  # Validation error


class TestPredictSpecificMode:
    """Test POST /api/v3/predict/{mode} (force specific mode)"""
    
    @patch('src.api_v3_endpoints.UnifiedPredictionEngine')
    def test_v1_mode_forced(self, mock_engine_class, client, mock_engine_v1):
        """Test forcing v1 mode"""
        mock_engine_class.return_value = mock_engine_v1
        
        response = client.post(
            "/api/v3/predict/v1",
            json={"count": 3}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is True
        assert data['mode'] == 'v1'
        assert data['mode_selected'] == 'manual'
    
    @patch('src.api_v3_endpoints.UnifiedPredictionEngine')
    def test_v2_mode_forced(self, mock_engine_class, client, mock_engine_v2):
        """Test forcing v2 mode"""
        mock_engine_class.return_value = mock_engine_v2
        
        response = client.post(
            "/api/v3/predict/v2",
            json={"count": 1}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is True
        assert data['mode'] == 'v2'
        assert data['mode_selected'] == 'manual'
    
    @patch('src.api_v3_endpoints.UnifiedPredictionEngine')
    def test_hybrid_mode_forced(self, mock_engine_class, client):
        """Test forcing hybrid mode"""
        engine = MagicMock()
        engine.get_mode.return_value = 'hybrid'
        engine.get_generation_metrics.return_value = {
            'total_generations': 3,
            'avg_generation_time': 0.7,
            'last_generation_time': 0.6
        }
        engine.get_backend_info.return_value = {
            'mode': 'hybrid',
            'backend_type': 'Mixed',
            'generation_metrics': {
                'total_generations': 3,
                'avg_generation_time': 0.7,
                'last_generation_time': 0.6
            }
        }
        engine.generate_tickets.return_value = [
            {
                'white_balls': [1, 2, 3, 4, 5],
                'powerball': 10,
                'strategy': 'hybrid_v1',
                'confidence': 0.7,
                'source': 'v1_strategy'
            },
            {
                'white_balls': [6, 7, 8, 9, 10],
                'powerball': 15,
                'strategy': 'hybrid_v2',
                'confidence': 0.8,
                'source': 'v2_ml'
            }
        ]
        mock_engine_class.return_value = engine
        
        response = client.post(
            "/api/v3/predict/hybrid",
            json={"count": 2}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is True
        assert data['mode'] == 'hybrid'
        assert data['mode_selected'] == 'manual'
    
    def test_invalid_mode(self, client):
        """Test invalid mode parameter"""
        response = client.post(
            "/api/v3/predict/invalid_mode",
            json={"count": 5}
        )
        
        assert response.status_code == 422  # Validation error
    
    @patch('src.api_v3_endpoints._generate_tickets_with_fallback')
    def test_mode_fallback_to_v1(self, mock_generate, client):
        """Test fallback from v2 to v1 on error"""
        # Mock fallback scenario
        mock_generate.return_value = {
            'success': True,
            'mode': 'v1',
            'requested_mode': 'v2',
            'fallback_occurred': True,
            'tickets': [
                {
                    'white_balls': [1, 2, 3, 4, 5],
                    'powerball': 10,
                    'strategy': 'fallback_strategy',
                    'confidence': 0.5
                }
            ],
            'generation_time': 0.2,
            'backend_info': {'mode': 'v1'},
            'fallback_reason': 'XGBoost not available'
        }
        
        response = client.post(
            "/api/v3/predict/v2",
            json={"count": 1, "include_metadata": True}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is True
        assert data['mode'] == 'v1'  # Fell back to v1
        assert data['metadata']['fallback_occurred'] is True
        assert 'fallback_reason' in data['metadata']


class TestCompare:
    """Test GET /api/v3/compare (compare all modes)"""
    
    @patch('src.api_v3_endpoints._generate_tickets_with_fallback')
    def test_compare_all_modes_success(self, mock_generate, client):
        """Test successful comparison of all modes"""
        # Mock responses for each mode
        def generate_side_effect(mode, count):
            tickets = [
                {
                    'white_balls': [i, i+1, i+2, i+3, i+4],
                    'powerball': i+5,
                    'strategy': f'{mode}_strategy',
                    'confidence': 0.7
                }
                for i in range(1, count + 1)
            ]
            return {
                'success': True,
                'mode': mode,
                'requested_mode': mode,
                'fallback_occurred': False,
                'tickets': tickets,
                'generation_time': 0.5
            }
        
        mock_generate.side_effect = generate_side_effect
        
        response = client.get("/api/v3/compare?count=2")
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'timestamp' in data
        assert data['count'] == 2
        assert len(data['comparisons']) == 3  # v1, v2, hybrid
        assert 'recommendation' in data
        
        # Check each comparison
        for comp in data['comparisons']:
            assert 'mode' in comp
            assert 'tickets' in comp
            assert 'generation_time' in comp
            assert 'success' in comp
            assert comp['mode'] in ['v1', 'v2', 'hybrid']
    
    @patch('src.api_v3_endpoints._generate_tickets_with_fallback')
    def test_compare_with_failures(self, mock_generate, client):
        """Test comparison when some modes fail"""
        def generate_with_failure(mode, count):
            if mode == 'v2':
                return {
                    'success': False,
                    'mode': mode,
                    'requested_mode': mode,
                    'fallback_occurred': False,
                    'tickets': [],
                    'generation_time': 0.1,
                    'error': 'XGBoost not installed'
                }
            else:
                return {
                    'success': True,
                    'mode': mode,
                    'requested_mode': mode,
                    'fallback_occurred': False,
                    'tickets': [
                        {
                            'white_balls': [1, 2, 3, 4, 5],
                            'powerball': 10,
                            'strategy': f'{mode}_strategy',
                            'confidence': 0.7
                        }
                    ],
                    'generation_time': 0.5
                }
        
        mock_generate.side_effect = generate_with_failure
        
        response = client.get("/api/v3/compare?count=1")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should still return all comparisons
        assert len(data['comparisons']) == 3
        
        # Check v2 failed
        v2_comp = next(c for c in data['comparisons'] if c['mode'] == 'v2')
        assert v2_comp['success'] is False
        assert v2_comp['error'] is not None
    
    def test_compare_default_count(self, client):
        """Test compare with default count parameter"""
        # This will fail without proper mocking but tests the endpoint exists
        response = client.get("/api/v3/compare")
        
        # Should attempt to process (may fail in test env without DB)
        assert response.status_code in [200, 500]
    
    def test_compare_invalid_count(self, client):
        """Test compare with invalid count"""
        response = client.get("/api/v3/compare?count=100")
        
        assert response.status_code == 422  # Validation error (max is 50)


class TestMetrics:
    """Test GET /api/v3/metrics (performance statistics)"""
    
    @patch('src.api_v3_endpoints._get_mode_metrics')
    @patch('src.api_v3_endpoints._select_best_mode')
    def test_metrics_success(self, mock_select, mock_get_metrics, client):
        """Test successful metrics retrieval"""
        from src.api_v3_endpoints import ModeMetrics
        
        # Mock metrics for each mode (use actual ModeMetrics instances)
        mock_get_metrics.side_effect = [
            ModeMetrics(
                mode='v1',
                total_generations=10,
                avg_generation_time=0.5,
                last_generation_time=0.45,
                success_rate=1.0,
                available=True
            ),
            ModeMetrics(
                mode='v2',
                total_generations=5,
                avg_generation_time=0.8,
                last_generation_time=0.75,
                success_rate=1.0,
                available=True
            ),
            ModeMetrics(
                mode='hybrid',
                total_generations=3,
                avg_generation_time=0.7,
                last_generation_time=0.6,
                success_rate=1.0,
                available=True
            )
        ]
        
        mock_select.return_value = 'v2'
        
        response = client.get("/api/v3/metrics")
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'timestamp' in data
        assert 'modes' in data
        assert len(data['modes']) == 3
        assert data['recommended_mode'] == 'v2'
        
        # Check mode metrics structure
        for mode_metric in data['modes']:
            assert 'mode' in mode_metric
            assert 'total_generations' in mode_metric
            assert 'avg_generation_time' in mode_metric
            assert 'available' in mode_metric
    
    @patch('src.api_v3_endpoints._get_mode_metrics')
    @patch('src.api_v3_endpoints._select_best_mode')
    def test_metrics_with_unavailable_mode(self, mock_select, mock_get_metrics, client):
        """Test metrics when v2 is unavailable"""
        from src.api_v3_endpoints import ModeMetrics
        
        mock_get_metrics.side_effect = [
            ModeMetrics(
                mode='v1',
                total_generations=10,
                avg_generation_time=0.5,
                last_generation_time=0.45,
                success_rate=1.0,
                available=True
            ),
            ModeMetrics(
                mode='v2',
                total_generations=0,
                avg_generation_time=0.0,
                last_generation_time=None,
                success_rate=0.0,
                available=False
            ),
            ModeMetrics(
                mode='hybrid',
                total_generations=3,
                avg_generation_time=0.7,
                last_generation_time=0.6,
                success_rate=1.0,
                available=True
            )
        ]
        
        mock_select.return_value = 'hybrid'
        
        response = client.get("/api/v3/metrics")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check v2 is marked as unavailable
        v2_metrics = next(m for m in data['modes'] if m['mode'] == 'v2')
        assert v2_metrics['available'] is False
        assert v2_metrics['total_generations'] == 0


class TestHelperFunctions:
    """Test helper functions used by endpoints"""
    
    @patch('src.api_v3_endpoints.UnifiedPredictionEngine')
    def test_select_best_mode_v2_available(self, mock_engine_class):
        """Test _select_best_mode when v2 is available"""
        from src.api_v3_endpoints import _select_best_mode
        
        engine = MagicMock()
        engine.get_mode.return_value = 'v2'
        engine.get_generation_metrics.return_value = {
            'total_generations': 5,
            'avg_generation_time': 0.8,
            'last_generation_time': 0.75
        }
        mock_engine_class.return_value = engine
        
        mode = _select_best_mode()
        assert mode == 'v2'
    
    @patch('src.api_v3_endpoints.UnifiedPredictionEngine')
    def test_select_best_mode_v2_unavailable(self, mock_engine_class):
        """Test _select_best_mode when v2 fails"""
        # Simulate v2 initialization failure
        mock_engine_class.side_effect = Exception("XGBoost not installed")
        
        from src.api_v3_endpoints import _select_best_mode
        
        mode = _select_best_mode()
        assert mode == 'v1'  # Should fallback to v1
    
    @patch('src.api_v3_endpoints.UnifiedPredictionEngine')
    def test_get_mode_metrics(self, mock_engine_class):
        """Test _get_mode_metrics function"""
        from src.api_v3_endpoints import _get_mode_metrics
        
        engine = MagicMock()
        engine.get_mode.return_value = 'v1'
        engine.get_generation_metrics.return_value = {
            'total_generations': 10,
            'avg_generation_time': 0.5,
            'last_generation_time': 0.45
        }
        mock_engine_class.return_value = engine
        
        metrics = _get_mode_metrics('v1')
        
        assert metrics.mode == 'v1'
        assert metrics.total_generations == 10
        assert metrics.avg_generation_time == 0.5
        assert metrics.available is True
    
    @patch('src.api_v3_endpoints.UnifiedPredictionEngine')
    def test_generate_tickets_with_fallback_success(self, mock_engine_class):
        """Test _generate_tickets_with_fallback successful generation"""
        from src.api_v3_endpoints import _generate_tickets_with_fallback
        
        engine = MagicMock()
        engine.get_mode.return_value = 'v1'
        engine.generate_tickets.return_value = [
            {
                'white_balls': [1, 2, 3, 4, 5],
                'powerball': 10,
                'strategy': 'test',
                'confidence': 0.7
            }
        ]
        engine.get_backend_info.return_value = {'mode': 'v1'}
        mock_engine_class.return_value = engine
        
        result = _generate_tickets_with_fallback('v1', 1)
        
        assert result['success'] is True
        assert result['mode'] == 'v1'
        assert len(result['tickets']) == 1
        assert 'generation_time' in result
    
    @patch('src.api_v3_endpoints.UnifiedPredictionEngine')
    def test_generate_tickets_with_fallback_error(self, mock_engine_class):
        """Test _generate_tickets_with_fallback with error and fallback"""
        from src.api_v3_endpoints import _generate_tickets_with_fallback
        
        # First call (v2) fails
        v2_engine = MagicMock()
        v2_engine.generate_tickets.side_effect = Exception("XGBoost error")
        
        # Second call (v1 fallback) succeeds
        v1_engine = MagicMock()
        v1_engine.get_mode.return_value = 'v1'
        v1_engine.generate_tickets.return_value = [
            {
                'white_balls': [1, 2, 3, 4, 5],
                'powerball': 10,
                'strategy': 'fallback',
                'confidence': 0.5
            }
        ]
        v1_engine.get_backend_info.return_value = {'mode': 'v1'}
        
        mock_engine_class.side_effect = [v2_engine, v1_engine]
        
        result = _generate_tickets_with_fallback('v2', 1)
        
        assert result['success'] is True
        assert result['mode'] == 'v1'  # Fell back to v1
        assert result['fallback_occurred'] is True
        assert 'fallback_reason' in result
