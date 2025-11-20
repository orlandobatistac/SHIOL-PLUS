"""
Test for PLP V2 Analytics Endpoints (Task 4.5.2)
=================================================

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
