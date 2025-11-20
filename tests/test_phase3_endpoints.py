"""
Tests for PHASE 3 External Project API Endpoints
Tests /api/v1/predictions/latest and /api/v1/predictions/by-strategy
"""
from fastapi.testclient import TestClient
import pytest


def test_latest_predictions_default(fastapi_app):
    """Test /latest endpoint with default parameters (limit=50)"""
    client = TestClient(fastapi_app)
    resp = client.get("/api/v1/predictions/latest")
    
    assert resp.status_code == 200
    data = resp.json()
    
    # Check response structure
    assert "tickets" in data
    assert "total" in data
    assert "timestamp" in data
    assert "filters_applied" in data
    
    # Check default filters
    assert data["filters_applied"]["limit"] == 50
    assert data["filters_applied"]["strategy"] is None
    assert data["filters_applied"]["min_confidence"] is None
    
    # Tickets should be a list
    assert isinstance(data["tickets"], list)
    
    # If tickets exist, check their structure
    if len(data["tickets"]) > 0:
        ticket = data["tickets"][0]
        assert "id" in ticket
        assert "draw_date" in ticket
        assert "strategy" in ticket
        assert "white_balls" in ticket
        assert "powerball" in ticket
        assert "confidence" in ticket
        assert "created_at" in ticket
        
        # Validate white_balls is list of 5 numbers
        assert isinstance(ticket["white_balls"], list)
        assert len(ticket["white_balls"]) == 5
        
        # Validate powerball is integer
        assert isinstance(ticket["powerball"], int)
        assert 1 <= ticket["powerball"] <= 26
        
        # Validate confidence is float
        assert isinstance(ticket["confidence"], (int, float))
        assert 0.0 <= ticket["confidence"] <= 1.0


def test_latest_predictions_with_limit(fastapi_app):
    """Test /latest endpoint with custom limit"""
    client = TestClient(fastapi_app)
    resp = client.get("/api/v1/predictions/latest", params={"limit": 10})
    
    assert resp.status_code == 200
    data = resp.json()
    
    # Should return at most 10 tickets
    assert len(data["tickets"]) <= 10
    assert data["filters_applied"]["limit"] == 10


def test_latest_predictions_with_strategy_filter(fastapi_app):
    """Test /latest endpoint with strategy filter"""
    client = TestClient(fastapi_app)
    
    # First, get all predictions to find an existing strategy
    all_resp = client.get("/api/v1/predictions/latest", params={"limit": 100})
    all_data = all_resp.json()
    
    if len(all_data["tickets"]) > 0:
        # Get first strategy name
        strategy_name = all_data["tickets"][0]["strategy"]
        
        # Now filter by that strategy
        resp = client.get("/api/v1/predictions/latest", params={"strategy": strategy_name})
        assert resp.status_code == 200
        data = resp.json()
        
        # All returned tickets should have the filtered strategy
        for ticket in data["tickets"]:
            assert ticket["strategy"] == strategy_name


def test_latest_predictions_with_min_confidence(fastapi_app):
    """Test /latest endpoint with min_confidence filter"""
    client = TestClient(fastapi_app)
    resp = client.get("/api/v1/predictions/latest", params={"min_confidence": 0.7})
    
    assert resp.status_code == 200
    data = resp.json()
    
    # All returned tickets should have confidence >= 0.7
    for ticket in data["tickets"]:
        assert ticket["confidence"] >= 0.7


def test_latest_predictions_combined_filters(fastapi_app):
    """Test /latest endpoint with multiple filters"""
    client = TestClient(fastapi_app)
    
    # Get a strategy first
    all_resp = client.get("/api/v1/predictions/latest", params={"limit": 100})
    all_data = all_resp.json()
    
    if len(all_data["tickets"]) > 0:
        strategy_name = all_data["tickets"][0]["strategy"]
        
        resp = client.get("/api/v1/predictions/latest", params={
            "limit": 5,
            "strategy": strategy_name,
            "min_confidence": 0.5
        })
        
        assert resp.status_code == 200
        data = resp.json()
        
        # Should return at most 5 tickets
        assert len(data["tickets"]) <= 5
        
        # All should match filters
        for ticket in data["tickets"]:
            assert ticket["strategy"] == strategy_name
            assert ticket["confidence"] >= 0.5


def test_by_strategy_endpoint(fastapi_app):
    """Test /by-strategy endpoint"""
    client = TestClient(fastapi_app)
    resp = client.get("/api/v1/predictions/by-strategy")
    
    assert resp.status_code == 200
    data = resp.json()
    
    # Check response structure
    assert "strategies" in data
    assert "total_strategies" in data
    assert "total_tickets" in data
    assert "timestamp" in data
    
    # Strategies should be a dict
    assert isinstance(data["strategies"], dict)
    assert isinstance(data["total_strategies"], int)
    assert isinstance(data["total_tickets"], int)
    
    # If strategies exist, check their structure
    if len(data["strategies"]) > 0:
        strategy_name = list(data["strategies"].keys())[0]
        strategy_data = data["strategies"][strategy_name]
        
        # Check strategy data structure
        assert "total_tickets" in strategy_data
        assert "avg_confidence" in strategy_data
        assert "last_generated" in strategy_data
        assert "performance" in strategy_data
        
        # Check performance metrics
        perf = strategy_data["performance"]
        assert "total_plays" in perf
        assert "total_wins" in perf
        assert "win_rate" in perf
        assert "roi" in perf
        assert "avg_prize" in perf
        assert "current_weight" in perf
        assert "confidence" in perf
        
        # Validate metric types
        assert isinstance(strategy_data["total_tickets"], int)
        assert isinstance(strategy_data["avg_confidence"], (int, float))
        assert isinstance(perf["win_rate"], (int, float))
        assert isinstance(perf["roi"], (int, float))
        assert isinstance(perf["current_weight"], (int, float))


def test_latest_predictions_ordering(fastapi_app):
    """Test that /latest endpoint returns predictions ordered by confidence DESC"""
    client = TestClient(fastapi_app)
    resp = client.get("/api/v1/predictions/latest", params={"limit": 20})
    
    assert resp.status_code == 200
    data = resp.json()
    
    # If we have multiple tickets, check ordering
    if len(data["tickets"]) >= 2:
        confidences = [ticket["confidence"] for ticket in data["tickets"]]
        
        # Check that confidences are in descending order
        for i in range(len(confidences) - 1):
            assert confidences[i] >= confidences[i + 1], \
                f"Confidences not in descending order: {confidences}"


def test_latest_predictions_invalid_limit(fastapi_app):
    """Test /latest endpoint with invalid limit (should be clamped or rejected)"""
    client = TestClient(fastapi_app)
    
    # Test limit > 500 (max allowed)
    resp = client.get("/api/v1/predictions/latest", params={"limit": 1000})
    # FastAPI should validate and reject
    assert resp.status_code == 422  # Validation error


def test_latest_predictions_invalid_confidence(fastapi_app):
    """Test /latest endpoint with invalid confidence value"""
    client = TestClient(fastapi_app)
    
    # Test confidence > 1.0
    resp = client.get("/api/v1/predictions/latest", params={"min_confidence": 1.5})
    # FastAPI should validate and reject
    assert resp.status_code == 422  # Validation error
    
    # Test confidence < 0.0
    resp = client.get("/api/v1/predictions/latest", params={"min_confidence": -0.5})
    assert resp.status_code == 422  # Validation error
