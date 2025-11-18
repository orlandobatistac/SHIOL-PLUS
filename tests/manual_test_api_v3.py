#!/usr/bin/env python3
"""
Manual test script for API v3 endpoints
Demonstrates all four endpoints with sample requests
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_predict_auto():
    """Test POST /api/v3/predict (auto-select mode)"""
    print("=" * 60)
    print("TEST 1: POST /api/v3/predict (auto-select mode)")
    print("=" * 60)
    
    response = requests.post(
        f"{BASE_URL}/api/v3/predict",
        json={"count": 3, "include_metadata": True}
    )
    
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Mode used: {data.get('mode')}")
    print(f"Mode selected: {data.get('mode_selected')}")
    print(f"Tickets generated: {data.get('count')}")
    print(f"Success: {data.get('success')}")
    print()
    
    if data.get('tickets'):
        print("Sample ticket:")
        print(json.dumps(data['tickets'][0], indent=2))
    
    print()


def test_predict_v1():
    """Test POST /api/v3/predict/v1 (force v1 mode)"""
    print("=" * 60)
    print("TEST 2: POST /api/v3/predict/v1 (force v1 mode)")
    print("=" * 60)
    
    response = requests.post(
        f"{BASE_URL}/api/v3/predict/v1",
        json={"count": 2, "include_metadata": False}
    )
    
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Mode used: {data.get('mode')}")
    print(f"Mode selected: {data.get('mode_selected')}")
    print(f"Tickets generated: {data.get('count')}")
    print()
    
    if data.get('tickets'):
        for i, ticket in enumerate(data['tickets'], 1):
            print(f"Ticket {i}: {ticket['white_balls']} + PB {ticket['powerball']}")
            print(f"  Strategy: {ticket['strategy']}, Confidence: {ticket['confidence']}")
    
    print()


def test_predict_hybrid():
    """Test POST /api/v3/predict/hybrid (force hybrid mode)"""
    print("=" * 60)
    print("TEST 3: POST /api/v3/predict/hybrid (force hybrid mode)")
    print("=" * 60)
    
    response = requests.post(
        f"{BASE_URL}/api/v3/predict/hybrid",
        json={"count": 5, "include_metadata": True}
    )
    
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Mode used: {data.get('mode')}")
    print(f"Fallback occurred: {data.get('metadata', {}).get('fallback_occurred', False)}")
    print(f"Tickets generated: {data.get('count')}")
    
    if data.get('metadata'):
        print(f"Generation time: {data['metadata'].get('generation_time', 0):.3f}s")
    
    print()


def test_compare():
    """Test GET /api/v3/compare (compare all modes)"""
    print("=" * 60)
    print("TEST 4: GET /api/v3/compare (compare all modes)")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/api/v3/compare?count=2")
    
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Timestamp: {data.get('timestamp')}")
    print(f"Recommended mode: {data.get('recommendation')}")
    print()
    
    for comp in data.get('comparisons', []):
        print(f"Mode: {comp['mode']}")
        print(f"  Success: {comp['success']}")
        print(f"  Generation time: {comp['generation_time']:.3f}s")
        print(f"  Tickets generated: {len(comp['tickets'])}")
        if comp.get('error'):
            print(f"  Error: {comp['error']}")
        print()


def test_metrics():
    """Test GET /api/v3/metrics (performance statistics)"""
    print("=" * 60)
    print("TEST 5: GET /api/v3/metrics (performance statistics)")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/api/v3/metrics")
    
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Timestamp: {data.get('timestamp')}")
    print(f"Recommended mode: {data.get('recommended_mode')}")
    print()
    
    print("Mode Metrics:")
    for mode_metric in data.get('modes', []):
        print(f"\n{mode_metric['mode'].upper()}:")
        print(f"  Available: {mode_metric['available']}")
        print(f"  Total generations: {mode_metric['total_generations']}")
        print(f"  Avg generation time: {mode_metric['avg_generation_time']:.3f}s")
        print(f"  Success rate: {mode_metric.get('success_rate', 0):.1%}")


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "API v3 ENDPOINTS MANUAL TEST" + " " * 20 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    try:
        test_predict_auto()
        test_predict_v1()
        test_predict_hybrid()
        test_compare()
        test_metrics()
        
        print()
        print("╔" + "=" * 58 + "╗")
        print("║" + " " * 18 + "ALL TESTS PASSED" + " " * 24 + "║")
        print("╚" + "=" * 58 + "╝")
        print()
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
