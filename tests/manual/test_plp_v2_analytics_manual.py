#!/usr/bin/env python
"""
Manual test script for PLP V2 Analytics Endpoints (Task 4.5.2)
===============================================================

This script provides a quick manual test of the new analytics endpoints.
Run this to verify endpoints work with real analytics engines.

Usage:
    python tests/manual/test_plp_v2_analytics_manual.py
"""

import os
import sys
import json

# Set environment variables before imports
os.environ["PLP_API_ENABLED"] = "true"
os.environ["PREDICTLOTTOPRO_API_KEY"] = "test_key_manual"

from fastapi.testclient import TestClient

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.api import app

def test_analytics_context():
    """Test GET /api/v2/analytics/context"""
    print("\n" + "="*80)
    print("TEST 1: Analytics Context Endpoint")
    print("="*80)
    
    client = TestClient(app)
    headers = {"Authorization": "Bearer test_key_manual"}
    
    response = client.get("/api/v2/analytics/context", headers=headers)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2))
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data['success'] is True, "Expected success=True"
    assert 'hot_numbers' in data['data'], "Expected hot_numbers in response"
    assert 'cold_numbers' in data['data'], "Expected cold_numbers in response"
    
    print("✅ Analytics Context endpoint works!")


def test_analyze_ticket():
    """Test POST /api/v2/analytics/analyze-ticket"""
    print("\n" + "="*80)
    print("TEST 2: Ticket Analyzer Endpoint")
    print("="*80)
    
    client = TestClient(app)
    headers = {"Authorization": "Bearer test_key_manual"}
    
    # Test with a sample ticket
    payload = {
        "white_balls": [7, 23, 34, 47, 62],
        "powerball": 15
    }
    
    print(f"Request Payload:")
    print(json.dumps(payload, indent=2))
    
    response = client.post(
        "/api/v2/analytics/analyze-ticket",
        json=payload,
        headers=headers
    )
    
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2))
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data['success'] is True, "Expected success=True"
    assert 'total_score' in data['data'], "Expected total_score in response"
    assert 'recommendation' in data['data'], "Expected recommendation in response"
    
    print("✅ Ticket Analyzer endpoint works!")


def test_interactive_generator():
    """Test POST /api/v2/generator/interactive"""
    print("\n" + "="*80)
    print("TEST 3: Interactive Generator Endpoint")
    print("="*80)
    
    client = TestClient(app)
    headers = {"Authorization": "Bearer test_key_manual"}
    
    # Test with custom parameters
    payload = {
        "risk": "high",
        "temperature": "hot",
        "exclude": [13, 7],
        "count": 3
    }
    
    print(f"Request Payload:")
    print(json.dumps(payload, indent=2))
    
    response = client.post(
        "/api/v2/generator/interactive",
        json=payload,
        headers=headers
    )
    
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2))
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data['success'] is True, "Expected success=True"
    assert 'tickets' in data['data'], "Expected tickets in response"
    assert len(data['data']['tickets']) == 3, "Expected 3 tickets"
    
    # Verify exclusions were respected
    for ticket in data['data']['tickets']:
        assert 13 not in ticket['white_balls'], "Number 13 should be excluded"
        assert 7 not in ticket['white_balls'], "Number 7 should be excluded"
    
    print("✅ Interactive Generator endpoint works!")


def test_validation_errors():
    """Test validation error handling"""
    print("\n" + "="*80)
    print("TEST 4: Validation Error Handling")
    print("="*80)
    
    client = TestClient(app)
    headers = {"Authorization": "Bearer test_key_manual"}
    
    # Test invalid ticket (duplicate numbers)
    payload = {
        "white_balls": [7, 7, 34, 47, 62],
        "powerball": 15
    }
    
    print(f"Testing invalid ticket (duplicate numbers):")
    response = client.post(
        "/api/v2/analytics/analyze-ticket",
        json=payload,
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    
    # Test invalid risk level
    payload = {
        "risk": "ultra_high",
        "temperature": "hot"
    }
    
    print(f"\nTesting invalid risk level:")
    response = client.post(
        "/api/v2/generator/interactive",
        json=payload,
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    
    print("✅ Validation error handling works!")


def main():
    """Run all manual tests"""
    print("\n" + "="*80)
    print("PLP V2 ANALYTICS ENDPOINTS - MANUAL TEST SUITE")
    print("="*80)
    
    try:
        test_analytics_context()
        test_analyze_ticket()
        test_interactive_generator()
        test_validation_errors()
        
        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED!")
        print("="*80)
        print("\nThe PLP V2 Analytics endpoints are working correctly.")
        print("You can now use these endpoints in the PredictLottoPro application.")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
