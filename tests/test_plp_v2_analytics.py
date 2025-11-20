"""
Test for PLP V2 Analytics Endpoints (Task 4.5.2)

Tests the three new endpoints:
- GET /api/v2/analytics/context
- POST /api/v2/analytics/analyze-ticket
- POST /api/v2/generator/interactive
"""

import os
import importlib
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

# Ensure PLP v2 is enabled and API key is set BEFORE importing app
os.environ["PLP_API_ENABLED"] = "true"
os.environ["PREDICTLOTTOPRO_API_KEY"] = "test_key"

from src import plp_api_key as plp_keys
import src.api as api


@pytest.fixture()
def client(monkeypatch):
    """Setup test client with PLP v2 enabled"""
    # Reset in-memory rate limiter state between tests
    try:
        plp_keys._RATE_STATE.clear()  # type: ignore
    except Exception:
        pass
    # Ensure flags are set and reload app so /api/v2 is mounted
    monkeypatch.setenv("PLP_API_ENABLED", "true")
    monkeypatch.setenv("PREDICTLOTTOPRO_API_KEY", "test_key")
    importlib.reload(api)
    return TestClient(api.app)


def auth_headers(key: str = "test_key"):
    """Helper to create auth headers"""
    return {"Authorization": f"Bearer {key}"}


@pytest.fixture()
def mock_analytics_overview():
    """Mock analytics overview data"""
    return {
        'gap_analysis': {
            'white_balls': {
                '1': 5, '2': 10, '3': 15, '4': 20, '5': 25,
                '10': 1, '20': 2, '30': 3, '40': 4, '50': 6,
                '60': 50, '61': 51, '62': 52, '63': 53, '64': 54,
                '65': 55, '66': 56, '67': 57, '68': 58, '69': 59,
            },
            'powerball': {str(i): i * 2 for i in range(1, 27)},
        },
        'momentum_scores': {
            'white_balls': {
                '1': 0.5, '2': 0.6, '3': 0.7, '4': 0.8, '5': 0.9,
                '10': 0.95, '20': 0.85, '30': 0.75, '40': 0.65, '50': 0.55,
                '60': -0.5, '61': -0.6, '62': -0.7, '63': -0.8, '64': -0.9,
            },
            'powerball': {str(i): 0.1 * i for i in range(1, 27)},
        },
        'temporal_frequencies': {
            'white_balls': [0.01] * 69,
            'powerball': [0.04] * 26,
        },
        'data_summary': {
            'total_draws': 100,
            'most_recent_date': '2024-11-20',
            'current_era_draws': 90,
        },
    }


# ==== Test Analytics Context Endpoint ====

def test_analytics_context_success(client: TestClient, mock_analytics_overview):
    """Test successful analytics context retrieval"""
    with patch('src.api_plp_v2.get_analytics_overview', return_value=mock_analytics_overview):
        response = client.get("/api/v2/analytics/context", headers=auth_headers())
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert data['success'] is True
        assert 'data' in data
        assert 'timestamp' in data
        assert data['error'] is None
        
        # Validate data content
        result = data['data']
        assert 'hot_numbers' in result
        assert 'cold_numbers' in result
        assert 'momentum' in result
        assert 'gaps' in result
        assert 'data_summary' in result
        
        # Validate hot/cold numbers
        assert len(result['hot_numbers']) == 10
        assert len(result['cold_numbers']) == 10
        assert isinstance(result['hot_numbers'][0], int)
        
        # Validate momentum
        assert 'rising_numbers' in result['momentum']
        assert 'falling_numbers' in result['momentum']
        assert len(result['momentum']['rising_numbers']) == 10
        assert len(result['momentum']['falling_numbers']) == 10
        
        # Validate gaps structure
        assert 'white_balls' in result['gaps']
        assert 'powerball' in result['gaps']


def test_analytics_context_requires_auth(client: TestClient):
    """Test that analytics context requires authentication"""
    response = client.get("/api/v2/analytics/context")
    assert response.status_code == 401


def test_analytics_context_handles_errors(client: TestClient):
    """Test analytics context error handling"""
    with patch('src.api_plp_v2.get_analytics_overview', side_effect=Exception("Database error")):
        response = client.get("/api/v2/analytics/context", headers=auth_headers())
        assert response.status_code == 500


# ==== Test Ticket Analyzer Endpoint ====

def test_analyze_ticket_success(client: TestClient, mock_analytics_overview):
    """Test successful ticket analysis"""
    mock_score_result = {
        'total_score': 75,
        'details': {
            'diversity': {'score': 0.8, 'quality': 'Good'},
            'balance': {'score': 0.7, 'quality': 'Fair'},
            'potential': {'score': 0.75, 'quality': 'Good'},
        },
        'recommendation': 'Good ticket with balanced numbers',
    }
    
    with patch('src.api_plp_v2.get_analytics_overview', return_value=mock_analytics_overview):
        with patch('src.api_plp_v2.TicketScorer.score_ticket', return_value=mock_score_result):
            payload = {
                'white_balls': [1, 15, 23, 42, 67],
                'powerball': 15,
            }
            
            response = client.post(
                "/api/v2/analytics/analyze-ticket",
                json=payload,
                headers=auth_headers()
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Validate response structure
            assert data['success'] is True
            assert 'data' in data
            assert 'timestamp' in data
            assert data['error'] is None
            
            # Validate score result
            result = data['data']
            assert result['total_score'] == 75
            assert 'details' in result
            assert 'recommendation' in result


def test_analyze_ticket_validation_errors(client: TestClient):
    """Test ticket analyzer validation"""
    # Test: Not enough numbers
    response = client.post(
        "/api/v2/analytics/analyze-ticket",
        json={'white_balls': [1, 2, 3], 'powerball': 15},
        headers=auth_headers()
    )
    assert response.status_code == 422  # Pydantic validation error
    
    # Test: Duplicate numbers
    response = client.post(
        "/api/v2/analytics/analyze-ticket",
        json={'white_balls': [1, 1, 2, 3, 4], 'powerball': 15},
        headers=auth_headers()
    )
    assert response.status_code == 400
    
    # Test: Numbers out of range
    response = client.post(
        "/api/v2/analytics/analyze-ticket",
        json={'white_balls': [1, 2, 3, 4, 70], 'powerball': 15},
        headers=auth_headers()
    )
    assert response.status_code == 400
    
    # Test: Powerball out of range
    response = client.post(
        "/api/v2/analytics/analyze-ticket",
        json={'white_balls': [1, 2, 3, 4, 5], 'powerball': 27},
        headers=auth_headers()
    )
    assert response.status_code == 422  # Pydantic validation error


def test_analyze_ticket_requires_auth(client: TestClient):
    """Test that ticket analyzer requires authentication"""
    payload = {'white_balls': [1, 2, 3, 4, 5], 'powerball': 15}
    response = client.post("/api/v2/analytics/analyze-ticket", json=payload)
    assert response.status_code == 401


# ==== Test Interactive Generator Endpoint ====

def test_interactive_generator_success(client: TestClient, mock_analytics_overview):
    """Test successful interactive ticket generation"""
    mock_tickets = [
        {'white_balls': [1, 15, 23, 42, 67], 'powerball': 10, 'confidence': 0.75},
        {'white_balls': [5, 18, 27, 45, 62], 'powerball': 15, 'confidence': 0.70},
        {'white_balls': [8, 20, 31, 48, 65], 'powerball': 20, 'confidence': 0.65},
    ]
    
    with patch('src.api_plp_v2.get_analytics_overview', return_value=mock_analytics_overview):
        with patch('src.api_plp_v2.CustomInteractiveGenerator.generate_custom', return_value=mock_tickets):
            payload = {
                'risk': 'high',
                'temperature': 'hot',
                'exclude': [13, 7],
                'count': 3,
            }
            
            response = client.post(
                "/api/v2/generator/interactive",
                json=payload,
                headers=auth_headers()
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Validate response structure
            assert data['success'] is True
            assert 'data' in data
            assert 'timestamp' in data
            assert data['error'] is None
            
            # Validate generated tickets
            result = data['data']
            assert 'tickets' in result
            assert 'parameters' in result
            assert len(result['tickets']) == 3
            
            # Validate ticket structure
            ticket = result['tickets'][0]
            assert 'rank' in ticket
            assert 'white_balls' in ticket
            assert 'powerball' in ticket
            assert 'confidence' in ticket
            assert len(ticket['white_balls']) == 5
            
            # Validate parameters echo
            params = result['parameters']
            assert params['risk'] == 'high'
            assert params['temperature'] == 'hot'
            assert params['excluded_count'] == 2
            assert params['requested_count'] == 3


def test_interactive_generator_default_params(client: TestClient, mock_analytics_overview):
    """Test interactive generator with default parameters"""
    mock_tickets = [
        {'white_balls': [1, 15, 23, 42, 67], 'powerball': 10, 'confidence': 0.75},
    ]
    
    with patch('src.api_plp_v2.get_analytics_overview', return_value=mock_analytics_overview):
        with patch('src.api_plp_v2.CustomInteractiveGenerator.generate_custom', return_value=mock_tickets):
            # Send request with minimal payload
            payload = {}
            
            response = client.post(
                "/api/v2/generator/interactive",
                json=payload,
                headers=auth_headers()
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Validate defaults were used
            params = data['data']['parameters']
            assert params['risk'] == 'med'
            assert params['temperature'] == 'neutral'
            assert params['excluded_count'] == 0
            assert params['requested_count'] == 5  # Default count


def test_interactive_generator_validation_errors(client: TestClient):
    """Test interactive generator validation"""
    # Test: Invalid risk level
    response = client.post(
        "/api/v2/generator/interactive",
        json={'risk': 'ultra', 'temperature': 'hot'},
        headers=auth_headers()
    )
    assert response.status_code == 400
    # PLP v2 error format uses 'error' field instead of 'detail'
    error_msg = response.json().get('error', '')
    assert 'risk level' in error_msg.lower()
    
    # Test: Invalid temperature
    response = client.post(
        "/api/v2/generator/interactive",
        json={'risk': 'med', 'temperature': 'warm'},
        headers=auth_headers()
    )
    assert response.status_code == 400
    error_msg = response.json().get('error', '')
    assert 'temperature' in error_msg.lower()
    
    # Test: Invalid exclusion numbers
    response = client.post(
        "/api/v2/generator/interactive",
        json={'risk': 'med', 'temperature': 'hot', 'exclude': [70, 80]},
        headers=auth_headers()
    )
    assert response.status_code == 400


def test_interactive_generator_requires_auth(client: TestClient):
    """Test that interactive generator requires authentication"""
    payload = {'risk': 'med', 'temperature': 'hot'}
    response = client.post("/api/v2/generator/interactive", json=payload)
    assert response.status_code == 401


# ==== Test Error Handling ====

def test_endpoints_handle_server_errors_gracefully(client: TestClient):
    """Test that all endpoints handle internal errors gracefully"""
    # Test analytics context error
    with patch('src.api_plp_v2.get_analytics_overview', side_effect=RuntimeError("DB connection lost")):
        response = client.get("/api/v2/analytics/context", headers=auth_headers())
        assert response.status_code == 500
        # PLP v2 error format uses 'error' field instead of 'detail'
        error_msg = response.json().get('error', '')
        assert 'Failed to retrieve analytics context' in error_msg or 'error' in error_msg.lower()
    
    # Test ticket analyzer error
    with patch('src.api_plp_v2.get_analytics_overview', side_effect=RuntimeError("DB connection lost")):
        payload = {'white_balls': [1, 2, 3, 4, 5], 'powerball': 15}
        response = client.post("/api/v2/analytics/analyze-ticket", json=payload, headers=auth_headers())
        assert response.status_code == 500
    
    # Test interactive generator error
    with patch('src.api_plp_v2.get_analytics_overview', side_effect=RuntimeError("DB connection lost")):
        payload = {'risk': 'med', 'temperature': 'hot'}
        response = client.post("/api/v2/generator/interactive", json=payload, headers=auth_headers())
        assert response.status_code == 500


# ==== Test Response Format Consistency ====

def test_response_format_consistency(client: TestClient, mock_analytics_overview):
    """Test that all endpoints return consistent response format"""
    with patch('src.api_plp_v2.get_analytics_overview', return_value=mock_analytics_overview):
        with patch('src.api_plp_v2.TicketScorer.score_ticket', return_value={'total_score': 75}):
            with patch('src.api_plp_v2.CustomInteractiveGenerator.generate_custom', return_value=[]):
                # Test analytics context
                response = client.get("/api/v2/analytics/context", headers=auth_headers())
                data = response.json()
                assert 'success' in data
                assert 'data' in data
                assert 'timestamp' in data
                assert 'error' in data
                
                # Test ticket analyzer
                payload = {'white_balls': [1, 2, 3, 4, 5], 'powerball': 15}
                response = client.post("/api/v2/analytics/analyze-ticket", json=payload, headers=auth_headers())
                data = response.json()
                assert 'success' in data
                assert 'data' in data
                assert 'timestamp' in data
                assert 'error' in data
                
                # Test interactive generator
                payload = {'risk': 'med', 'temperature': 'hot'}
                response = client.post("/api/v2/generator/interactive", json=payload, headers=auth_headers())
                data = response.json()
                assert 'success' in data
                assert 'data' in data
                assert 'timestamp' in data
                assert 'error' in data
Tests for new PLP V2 analytics functions
Tests for compute_gap_analysis, compute_temporal_frequencies,
compute_momentum_scores, and get_analytics_overview
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.analytics_engine import (
    compute_gap_analysis,
    compute_temporal_frequencies,
    compute_momentum_scores,
    get_analytics_overview
)


class TestComputeGapAnalysis:
    """Test gap analysis function"""
    
    def test_gap_analysis_with_valid_data(self):
        """Test gap analysis with normal data"""
        # Create sample data with known gaps
        today = datetime.now()
        df = pd.DataFrame({
            'draw_date': [
                today - timedelta(days=30),
                today - timedelta(days=20),
                today - timedelta(days=10)
            ],
            'n1': [1, 2, 3],
            'n2': [5, 6, 7],
            'n3': [10, 11, 12],
            'n4': [20, 21, 22],
            'n5': [30, 31, 32],
            'pb': [5, 10, 15]
        })
        
        result = compute_gap_analysis(df)
        
        # Verify structure
        assert 'white_balls' in result
        assert 'powerball' in result
        assert len(result['white_balls']) == 69
        assert len(result['powerball']) == 26
        
        # Verify gaps for numbers we know appeared
        # Most recent draw was 10 days ago
        # Number 3 appeared in that most recent draw (10 days ago)
        # So gap from most recent draw to when it last appeared = 0
        assert result['white_balls'][3] == 0
        
        # Number 32 also appeared in the most recent draw
        assert result['white_balls'][32] == 0
        
        # Number 1 appeared 30 days ago
        # Gap from most recent draw (10 days ago) to when it appeared (30 days ago) = 20 days
        assert result['white_balls'][1] == 20
        
        # Number 2 appeared 20 days ago
        # Gap from most recent draw to when it appeared = 10 days
        assert result['white_balls'][2] == 10
        
        # Powerball 15 appeared in most recent draw (10 days ago)
        assert result['powerball'][15] == 0
        
        # Number that never appeared should have gap of 999
        assert result['white_balls'][69] == 999
    
    def test_gap_analysis_empty_dataframe(self):
        """Test gap analysis handles empty dataframe gracefully"""
        df = pd.DataFrame()
        
        result = compute_gap_analysis(df)
        
        # Should return default gaps (all 0)
        assert 'white_balls' in result
        assert 'powerball' in result
        assert len(result['white_balls']) == 69
        assert len(result['powerball']) == 26
        assert result['white_balls'][1] == 0
    
    def test_gap_analysis_single_draw(self):
        """Test gap analysis with single draw"""
        today = datetime.now()
        df = pd.DataFrame({
            'draw_date': [today],
            'n1': [5], 'n2': [15], 'n3': [25], 'n4': [35], 'n5': [45],
            'pb': [10]
        })
        
        result = compute_gap_analysis(df)
        
        # Numbers that appeared should have gap of 0
        assert result['white_balls'][5] == 0
        assert result['white_balls'][15] == 0
        assert result['powerball'][10] == 0
        
        # Numbers that didn't appear should have gap of 999
        assert result['white_balls'][1] == 999


class TestComputeTemporalFrequencies:
    """Test temporal frequency calculation with exponential decay"""
    
    def test_temporal_frequencies_with_valid_data(self):
        """Test temporal frequencies with normal data"""
        today = datetime.now()
        df = pd.DataFrame({
            'draw_date': [
                today - timedelta(days=30),
                today - timedelta(days=20),
                today - timedelta(days=10)
            ],
            'n1': [1, 1, 1],  # Number 1 appears in all draws
            'n2': [5, 6, 7],
            'n3': [10, 11, 12],
            'n4': [20, 21, 22],
            'n5': [30, 31, 32],
            'pb': [5, 5, 5]  # Powerball 5 appears in all draws
        })
        
        result = compute_temporal_frequencies(df, decay_rate=0.05)
        
        # Verify structure
        assert 'white_balls' in result
        assert 'powerball' in result
        assert len(result['white_balls']) == 69
        assert len(result['powerball']) == 26
        
        # Verify probabilities sum to 1
        assert np.isclose(result['white_balls'].sum(), 1.0, atol=1e-6)
        assert np.isclose(result['powerball'].sum(), 1.0, atol=1e-6)
        
        # Number 1 appeared in all draws, so it should have higher frequency
        # than numbers that appeared once
        assert result['white_balls'][0] > result['white_balls'][4]  # n1 > n2
    
    def test_temporal_frequencies_empty_dataframe(self):
        """Test temporal frequencies handles empty dataframe"""
        df = pd.DataFrame()
        
        result = compute_temporal_frequencies(df)
        
        # Should return uniform distribution
        assert 'white_balls' in result
        assert 'powerball' in result
        assert np.isclose(result['white_balls'].sum(), 1.0)
        assert np.isclose(result['powerball'].sum(), 1.0)
        # All frequencies should be equal (uniform)
        assert np.allclose(result['white_balls'], 1/69, atol=1e-6)
    
    def test_temporal_frequencies_decay_rate(self):
        """Test that higher decay rate reduces influence of old draws"""
        today = datetime.now()
        df = pd.DataFrame({
            'draw_date': [
                today - timedelta(days=100),  # Old draw
                today - timedelta(days=1)     # Recent draw
            ],
            'n1': [1, 2],
            'n2': [5, 6],
            'n3': [10, 11],
            'n4': [20, 21],
            'n5': [30, 31],
            'pb': [5, 10]
        })
        
        # Low decay (old draws still matter)
        result_low = compute_temporal_frequencies(df, decay_rate=0.01)
        
        # High decay (old draws matter less)
        result_high = compute_temporal_frequencies(df, decay_rate=0.1)
        
        # With high decay, number 2 (recent) should have higher frequency
        # relative to number 1 (old) compared to low decay
        ratio_low = result_low['white_balls'][1] / result_low['white_balls'][0]
        ratio_high = result_high['white_balls'][1] / result_high['white_balls'][0]
        
        assert ratio_high > ratio_low


class TestComputeMomentumScores:
    """Test momentum score calculation"""
    
    def test_momentum_scores_with_valid_data(self):
        """Test momentum scores with normal data"""
        # Create data where number 1 appears more in recent draws (rising)
        # and number 69 appears less in recent draws (falling)
        dates = [datetime.now() - timedelta(days=i) for i in range(20, 0, -1)]
        
        # Create n1 column: 69 in first 10 rows (older), 1 in last 10 rows (recent)
        n1_values = [69] * 10 + [1] * 10
        
        df = pd.DataFrame({
            'draw_date': dates,
            'n1': n1_values,
            'n2': [5, 6, 7, 8, 9] * 4,
            'n3': [10, 11, 12, 13, 14] * 4,
            'n4': [20, 21, 22, 23, 24] * 4,
            'n5': [30, 31, 32, 33, 34] * 4,
            'pb': [5] * 20
        })
        
        result = compute_momentum_scores(df, window=20)
        
        # Verify structure
        assert 'white_balls' in result
        assert 'powerball' in result
        assert len(result['white_balls']) == 69
        assert len(result['powerball']) == 26
        
        # Number 1 appears in last 10 draws (recent half), so should have positive momentum
        assert result['white_balls'][1] > 0
        
        # Number 69 appears in first 10 draws (older half), so should have negative momentum
        assert result['white_balls'][69] < 0
        
        # Momentum scores should be between -1 and 1
        for score in result['white_balls'].values():
            assert -1.0 <= score <= 1.0
    
    def test_momentum_scores_insufficient_data(self):
        """Test momentum scores handles insufficient data"""
        df = pd.DataFrame({
            'draw_date': [datetime.now()],
            'n1': [1], 'n2': [5], 'n3': [10], 'n4': [20], 'n5': [30],
            'pb': [5]
        })
        
        result = compute_momentum_scores(df, window=20)
        
        # Should return neutral momentum (0.0) for all numbers
        assert all(score == 0.0 for score in result['white_balls'].values())
        assert all(score == 0.0 for score in result['powerball'].values())
    
    def test_momentum_scores_stable_numbers(self):
        """Test momentum scores for numbers appearing consistently"""
        # Create data where number 5 appears in both halves equally
        dates = [datetime.now() - timedelta(days=i) for i in range(20, 0, -1)]
        
        df = pd.DataFrame({
            'draw_date': dates,
            'n1': [5] * 20,  # Appears consistently
            'n2': [10] * 20,
            'n3': [15] * 20,
            'n4': [20] * 20,
            'n5': [25] * 20,
            'pb': [5] * 20
        })
        
        result = compute_momentum_scores(df, window=20)
        
        # Number 5 appears equally in both halves, momentum should be near 0
        assert abs(result['white_balls'][5]) < 0.2


class TestGetAnalyticsOverview:
    """Test the facade function that returns all analytics"""
    
    def test_analytics_overview_structure(self):
        """Test that analytics overview returns expected structure"""
        result = get_analytics_overview()
        
        # Verify all expected keys are present
        assert 'gap_analysis' in result
        assert 'temporal_frequencies' in result
        assert 'momentum_scores' in result
        assert 'pattern_statistics' in result
        assert 'data_summary' in result
        
        # Verify nested structure
        assert 'white_balls' in result['gap_analysis']
        assert 'powerball' in result['gap_analysis']
        assert 'white_balls' in result['temporal_frequencies']
        assert 'powerball' in result['temporal_frequencies']
        assert 'white_balls' in result['momentum_scores']
        assert 'powerball' in result['momentum_scores']
        
        # Verify data summary fields
        assert 'total_draws' in result['data_summary']
        assert 'most_recent_date' in result['data_summary']
        assert 'current_era_draws' in result['data_summary']
    
    def test_analytics_overview_with_no_data(self, monkeypatch):
        """Test analytics overview handles no data gracefully"""
        # Mock get_all_draws to return empty dataframe
        def mock_get_all_draws():
            return pd.DataFrame()
        
        monkeypatch.setattr('src.analytics_engine.get_all_draws', mock_get_all_draws)
        
        result = get_analytics_overview()
        
        # Should return default values without errors
        assert result['data_summary']['total_draws'] == 0
        assert result['data_summary']['most_recent_date'] is None


class TestIntegration:
    """Integration tests combining multiple analytics functions"""
    
    def test_analytics_consistency(self):
        """Test that all analytics functions work together consistently"""
        # Create sample data
        today = datetime.now()
        dates = [today - timedelta(days=i) for i in range(30, 0, -1)]
        
        df = pd.DataFrame({
            'draw_date': dates,
            'n1': list(range(1, 31)),
            'n2': list(range(10, 40)),
            'n3': list(range(20, 50)),
            'n4': list(range(30, 60)),
            'n5': list(range(40, 70)),
            'pb': [i % 26 + 1 for i in range(30)]
        })
        
        # Compute all analytics
        gap = compute_gap_analysis(df)
        temporal = compute_temporal_frequencies(df)
        momentum = compute_momentum_scores(df, window=20)
        
        # Verify they all return data for same number ranges
        assert set(gap['white_balls'].keys()) == set(range(1, 70))
        assert len(temporal['white_balls']) == 69
        assert set(momentum['white_balls'].keys()) == set(range(1, 70))
        
        # Verify probabilities are valid
        assert np.isclose(temporal['white_balls'].sum(), 1.0)
        assert np.isclose(temporal['powerball'].sum(), 1.0)
