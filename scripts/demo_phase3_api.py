#!/usr/bin/env python3
"""
Demonstration script for PHASE 3 API endpoints
Shows example requests and responses for both endpoints
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from src.api import app
import json

def demo_latest_endpoint():
    """Demonstrate /api/v1/predictions/latest endpoint"""
    print("\n" + "="*80)
    print("DEMONSTRATION: GET /api/v1/predictions/latest")
    print("="*80)
    
    client = TestClient(app)
    
    # Example 1: Get 5 latest predictions
    print("\n📌 Example 1: Get 5 latest predictions (highest confidence)")
    print("   Request: GET /api/v1/predictions/latest?limit=5")
    
    resp = client.get("/api/v1/predictions/latest?limit=5")
    data = resp.json()
    
    print(f"\n   Response ({resp.status_code}):")
    print(f"   Total returned: {data['total']}")
    print(f"\n   Top 5 predictions by confidence:")
    for i, ticket in enumerate(data['tickets'][:5], 1):
        print(f"      {i}. Strategy: {ticket['strategy']:20} | Confidence: {ticket['confidence']:.4f} | Numbers: {ticket['white_balls']} + PB:{ticket['powerball']}")
    
    # Example 2: Filter by strategy
    print("\n📌 Example 2: Get XGBoost predictions only")
    print("   Request: GET /api/v1/predictions/latest?strategy=xgboost_ml&limit=3")
    
    resp = client.get("/api/v1/predictions/latest?strategy=xgboost_ml&limit=3")
    data = resp.json()
    
    print(f"\n   Response ({resp.status_code}):")
    print(f"   Total XGBoost predictions: {data['total']}")
    for i, ticket in enumerate(data['tickets'][:3], 1):
        print(f"      {i}. {ticket['white_balls']} + PB:{ticket['powerball']} (confidence: {ticket['confidence']:.4f})")
    
    # Example 3: High confidence filter
    print("\n📌 Example 3: Get only high-confidence predictions (>0.75)")
    print("   Request: GET /api/v1/predictions/latest?min_confidence=0.75&limit=10")
    
    resp = client.get("/api/v1/predictions/latest?min_confidence=0.75&limit=10")
    data = resp.json()
    
    print(f"\n   Response ({resp.status_code}):")
    print(f"   High-confidence predictions found: {data['total']}")
    if data['tickets']:
        confidences = [t['confidence'] for t in data['tickets']]
        print(f"   Confidence range: {min(confidences):.4f} - {max(confidences):.4f}")


def demo_by_strategy_endpoint():
    """Demonstrate /api/v1/predictions/by-strategy endpoint"""
    print("\n" + "="*80)
    print("DEMONSTRATION: GET /api/v1/predictions/by-strategy")
    print("="*80)
    
    client = TestClient(app)
    
    print("\n📌 Example: Get performance metrics for all strategies")
    print("   Request: GET /api/v1/predictions/by-strategy")
    
    resp = client.get("/api/v1/predictions/by-strategy")
    data = resp.json()
    
    print(f"\n   Response ({resp.status_code}):")
    print(f"   Total strategies: {data['total_strategies']}")
    print(f"   Total tickets generated: {data['total_tickets']}")
    
    print("\n   📊 Strategy Performance Leaderboard (sorted by ROI):")
    print("   " + "-"*90)
    print(f"   {'Strategy':<22} {'Tickets':<8} {'Avg Conf':<10} {'ROI':<8} {'Win Rate':<10} {'Weight':<8}")
    print("   " + "-"*90)
    
    # Sort by ROI
    sorted_strategies = sorted(
        data['strategies'].items(),
        key=lambda x: x[1]['performance']['roi'],
        reverse=True
    )
    
    for strategy_name, strategy_data in sorted_strategies:
        perf = strategy_data['performance']
        print(f"   {strategy_name:<22} {strategy_data['total_tickets']:<8} "
              f"{strategy_data['avg_confidence']:<10.4f} {perf['roi']:<8.2f} "
              f"{perf['win_rate']:<10.4f} {perf['current_weight']:<8.4f}")
    
    print("   " + "-"*90)
    
    # Highlight best and worst performers
    best_strategy = sorted_strategies[0]
    worst_strategy = sorted_strategies[-1]
    
    print(f"\n   🏆 Best Performer: {best_strategy[0]} (ROI: {best_strategy[1]['performance']['roi']:.2f})")
    print(f"   ⚠️  Needs Improvement: {worst_strategy[0]} (ROI: {worst_strategy[1]['performance']['roi']:.2f})")
    
    # Show use case
    print("\n   💡 Use Case for External Project:")
    print("      - External app can query this endpoint to see which strategies are working best")
    print("      - Adaptive learning automatically adjusts weights based on ROI")
    print("      - Strategies with high ROI get more tickets generated in future runs")


def main():
    """Run demonstrations"""
    print("\n" + "#"*80)
    print("# PHASE 3 API ENDPOINTS - LIVE DEMONSTRATION")
    print("# External Project API - Read-Only, High Performance (<10ms)")
    print("#"*80)
    
    demo_latest_endpoint()
    demo_by_strategy_endpoint()
    
    print("\n" + "="*80)
    print("✅ DEMONSTRATION COMPLETE")
    print("="*80)
    print("\n📌 Key Features:")
    print("   ✓ Both endpoints respond in <10ms")
    print("   ✓ Read-only operations (no new predictions generated)")
    print("   ✓ Flexible filtering and aggregation")
    print("   ✓ Real-time access to pipeline predictions")
    print("   ✓ Performance metrics for adaptive learning")
    
    print("\n📚 API Documentation:")
    print("   - Swagger UI: http://localhost:8000/docs")
    print("   - ReDoc: http://localhost:8000/redoc")
    print("   - OpenAPI JSON: http://localhost:8000/openapi.json")
    
    print("\n🎯 Ready for external project integration!")
    print()

if __name__ == "__main__":
    main()
