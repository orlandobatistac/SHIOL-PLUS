#!/usr/bin/env python3
"""
Test script for consolidated /api/v2/plp-dashboard endpoint.
Compares performance: single endpoint vs multiple endpoints.
"""

import time
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_single_vs_multiple():
    """Compare single consolidated endpoint vs multiple calls."""
    print("=" * 70)
    print("PLP DASHBOARD - SINGLE ENDPOINT vs MULTIPLE ENDPOINTS")
    print("=" * 70)

    from src.api_plp_v2 import (
        get_plp_dashboard,
        get_draw_stats,
        plp_hot_cold_numbers,
        plp_overview_enhanced,
        invalidate_all_plp_caches,
    )

    # Reset all caches
    print("\n[SETUP] Invalidating all caches...")
    invalidate_all_plp_caches()

    # ===== TEST 1: Multiple Endpoints (OLD WAY) =====
    print("\n[TEST 1] MULTIPLE ENDPOINTS (3 separate calls)...")
    print("-" * 50)

    start = time.perf_counter()

    # Call 1: Draw stats
    t1_start = time.perf_counter()
    result1 = asyncio.run(get_draw_stats())
    t1 = (time.perf_counter() - t1_start) * 1000
    print(f"  /draw-stats:        {t1:.2f}ms")

    # Call 2: Hot/Cold numbers
    t2_start = time.perf_counter()
    result2 = asyncio.run(plp_hot_cold_numbers())
    t2 = (time.perf_counter() - t2_start) * 1000
    print(f"  /hot-cold-numbers:  {t2:.2f}ms")

    # Call 3: Overview enhanced
    t3_start = time.perf_counter()
    result3 = asyncio.run(plp_overview_enhanced())
    t3 = (time.perf_counter() - t3_start) * 1000
    print(f"  /overview-enhanced: {t3:.2f}ms")

    total_multiple = (time.perf_counter() - start) * 1000
    print(f"\n  TOTAL (3 calls):    {total_multiple:.2f}ms")

    # Reset caches again for fair comparison
    invalidate_all_plp_caches()

    # ===== TEST 2: Single Consolidated Endpoint (NEW WAY) =====
    print("\n[TEST 2] SINGLE ENDPOINT (1 call with all data)...")
    print("-" * 50)

    start = time.perf_counter()
    result_single = asyncio.run(get_plp_dashboard())
    total_single = (time.perf_counter() - start) * 1000

    print(f"  /plp-dashboard:     {total_single:.2f}ms")
    print(f"  from_cache:         {result_single.get('from_cache', False)}")

    # Show data received
    data = result_single.get('data', {})
    print(f"\n  Data received:")
    print(f"    - draw_stats:     total={data.get('draw_stats', {}).get('total_draws')}")
    print(f"    - hot_cold:       {len(data.get('hot_cold', {}).get('hot_numbers', {}).get('white_balls', []))} hot white balls")
    print(f"    - top_strategies: {len(data.get('top_strategies', []))} strategies")

    # ===== TEST 3: Cached Single Endpoint =====
    print("\n[TEST 3] SINGLE ENDPOINT (cached)...")
    print("-" * 50)

    start = time.perf_counter()
    result_cached = asyncio.run(get_plp_dashboard())
    total_cached = (time.perf_counter() - start) * 1000

    print(f"  /plp-dashboard:     {total_cached:.3f}ms")
    print(f"  from_cache:         {result_cached.get('from_cache', False)}")
    print(f"  cache_age_seconds:  {result_cached.get('cache_age_seconds', 0)}")

    # ===== SUMMARY =====
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\n  Multiple endpoints (3 calls): {total_multiple:.2f}ms")
    print(f"  Single endpoint (cold):       {total_single:.2f}ms")
    print(f"  Single endpoint (cached):     {total_cached:.3f}ms")

    print(f"\n  🚀 Savings vs multiple calls:")
    if total_single > 0:
        print(f"     Cold:   {total_multiple - total_single:.2f}ms saved ({total_multiple/total_single:.1f}x faster)")
    if total_cached > 0:
        print(f"     Cached: {total_multiple - total_cached:.2f}ms saved ({total_multiple/total_cached:.0f}x faster)")

    # Network latency simulation
    print("\n  📡 With real network latency (~50ms per call):")
    network_multiple = total_multiple + (3 * 50)  # 3 round-trips
    network_single = total_single + 50             # 1 round-trip
    network_cached = total_cached + 50             # 1 round-trip

    print(f"     Multiple (3 calls): {network_multiple:.0f}ms")
    print(f"     Single (cold):      {network_single:.0f}ms")
    print(f"     Single (cached):    {network_cached:.0f}ms")
    print(f"\n     Real-world savings: {network_multiple - network_cached:.0f}ms! 🎉")

    # Response structure
    print("\n" + "=" * 70)
    print("RESPONSE STRUCTURE for /plp-dashboard")
    print("=" * 70)
    print("""
{
  "success": true,
  "data": {
    "draw_stats": {
      "total_draws": 2260,
      "most_recent": "2025-12-01",
      "current_era": 1980
    },
    "hot_cold": {
      "hot_numbers": {
        "white_balls": [28, 43, 7, 29, 3, 62, 52, 32, 8, 15],
        "powerballs": [25, 1, 2, 19, 20]
      },
      "cold_numbers": {
        "white_balls": [11, 63, 36, 20, 46, 21, 41, 38, 55, 56],
        "powerballs": [8, 13, 26, 16, 6]
      },
      "draws_analyzed": 100
    },
    "top_strategies": [
      {"name": "frequency_weighted", "weight": 0.1751, ...},
      ...
    ]
  },
  "from_cache": true,
  "cache_age_seconds": 45.2
}
""")

    return total_cached < 5


if __name__ == "__main__":
    success = test_single_vs_multiple()
    sys.exit(0 if success else 1)
