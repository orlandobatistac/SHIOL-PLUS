#!/usr/bin/env python3
"""
Test script for /api/v2/analytics/context endpoint cache performance.
"""

import time
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_analytics_context_cache():
    """Test analytics context cache performance."""
    print("=" * 60)
    print("PLP V2 /analytics/context - CACHE PERFORMANCE TEST")
    print("=" * 60)

    from src.api_plp_v2 import (
        plp_analytics_context,
        invalidate_analytics_context_cache
    )

    # Reset cache
    print("\n[SETUP] Invalidating analytics context cache...")
    invalidate_analytics_context_cache()

    # First call (cold - no cache)
    print("\n[TEST 1] First call (cold cache - full calculation)...")
    start = time.perf_counter()
    result1 = asyncio.run(plp_analytics_context())
    time1 = (time.perf_counter() - start) * 1000

    print(f"  Time: {time1:.0f}ms")
    print(f"  from_cache: {result1.get('from_cache', False)}")
    print(f"  calculation_time_ms: {result1.get('calculation_time_ms', 'N/A')}")

    # Show some data
    data = result1.get('data', {})
    hot_white = data.get('hot_numbers', {}).get('white_balls', [])
    cold_white = data.get('cold_numbers', {}).get('white_balls', [])
    print(f"  Hot white balls: {hot_white[:5]}")
    print(f"  Cold white balls: {cold_white[:5]}")

    data_summary = data.get('data_summary', {})
    print(f"  Total draws: {data_summary.get('total_draws', 'N/A')}")
    print(f"  Most recent: {data_summary.get('most_recent_date', 'N/A')}")

    # Second call (warm - from cache)
    print("\n[TEST 2] Second call (cache hit)...")
    start = time.perf_counter()
    result2 = asyncio.run(plp_analytics_context())
    time2 = (time.perf_counter() - start) * 1000

    print(f"  Time: {time2:.3f}ms")
    print(f"  from_cache: {result2.get('from_cache', False)}")
    print(f"  cache_age_seconds: {result2.get('cache_age_seconds', 'N/A')}")

    # Third call
    print("\n[TEST 3] Third call (cache hit)...")
    start = time.perf_counter()
    result3 = asyncio.run(plp_analytics_context())
    time3 = (time.perf_counter() - start) * 1000

    print(f"  Time: {time3:.3f}ms")
    print(f"  from_cache: {result3.get('from_cache', False)}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  First call (cold cache):  {time1:,.0f}ms")
    print(f"  Second call (cached):     {time2:,.2f}ms")
    print(f"  Third call (cached):      {time3:,.2f}ms")

    if time2 > 0:
        speedup = time1 / time2
        print(f"\n  🚀 SPEEDUP: {speedup:,.0f}x faster with cache")

    if time2 < 5:
        print("  ✅ CACHE WORKING - responses under 5ms")
    else:
        print("  ❌ CACHE NOT WORKING - responses still slow")

    # Compare with what PLP was experiencing
    print("\n" + "-" * 60)
    print("COMPARISON WITH ORIGINAL PROBLEM:")
    print("-" * 60)
    print(f"  Before (no cache): ~20,000ms (20 seconds)")
    print(f"  After (cached):    {time2:.2f}ms")
    print(f"  Improvement:       ~{20000/max(time2, 0.01):,.0f}x faster! 🎉")

    return time2 < 10


if __name__ == "__main__":
    success = test_analytics_context_cache()
    sys.exit(0 if success else 1)
