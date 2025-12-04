#!/usr/bin/env python3
"""
Test script for PLP v2 hot/cold numbers endpoint performance.
"""

import time
import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_hot_cold_performance():
    """Test hot/cold calculation and cache performance."""
    print("=" * 60)
    print("PLP V2 HOT/COLD NUMBERS - PERFORMANCE TEST")
    print("=" * 60)

    from src.api_plp_v2 import (
        get_cached_hot_cold_numbers,
        invalidate_hot_cold_cache
    )

    # Reset cache
    print("\n[SETUP] Invalidating cache...")
    invalidate_hot_cold_cache()

    # First call (cold - no cache)
    print("\n[TEST 1] First call (cold cache)...")
    start = time.perf_counter()
    result1 = get_cached_hot_cold_numbers()
    time1 = (time.perf_counter() - start) * 1000

    print(f"  Time: {time1:.2f}ms")
    print(f"  From cache: {result1.get('from_cache', False)}")
    print(f"  Draws analyzed: {result1.get('draws_analyzed', 0)}")
    print(f"  Hot white balls: {result1['hot_numbers']['white_balls']}")
    print(f"  Cold white balls: {result1['cold_numbers']['white_balls']}")
    print(f"  Hot powerballs: {result1['hot_numbers']['powerballs']}")
    print(f"  Cold powerballs: {result1['cold_numbers']['powerballs']}")

    # Second call (warm - from cache)
    print("\n[TEST 2] Second call (cache hit)...")
    start = time.perf_counter()
    result2 = get_cached_hot_cold_numbers()
    time2 = (time.perf_counter() - start) * 1000

    print(f"  Time: {time2:.3f}ms")
    print(f"  From cache: {result2.get('from_cache', False)}")
    print(f"  Cache age: {result2.get('cache_age_seconds', 0)}s")

    # Multiple cached calls
    print("\n[TEST 3] 10 cached calls...")
    times = []
    for i in range(10):
        start = time.perf_counter()
        _ = get_cached_hot_cold_numbers()
        times.append((time.perf_counter() - start) * 1000)

    avg_time = sum(times) / len(times)
    print(f"  Average time: {avg_time:.3f}ms")
    print(f"  Min time: {min(times):.3f}ms")
    print(f"  Max time: {max(times):.3f}ms")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Cold cache (first call): {time1:.2f}ms")
    print(f"  Warm cache (second call): {time2:.3f}ms")

    if time2 > 0:
        speedup = time1 / time2
        print(f"  Speedup: {speedup:,.0f}x faster with cache")

    if time2 < 1:
        print("  ✅ PASSED - Cache working correctly (<1ms)")
    elif time2 < 5:
        print("  ✅ PASSED - Cache working correctly (<5ms)")
    else:
        print("  ❌ FAILED - Cache too slow")

    return time2 < 5


def test_enhanced_overview():
    """Test enhanced overview endpoint."""
    print("\n" + "=" * 60)
    print("PLP V2 ENHANCED OVERVIEW - PERFORMANCE TEST")
    print("=" * 60)

    import asyncio
    from src.api_plp_v2 import plp_overview_enhanced

    # First call
    print("\n[TEST] Enhanced overview endpoint...")
    start = time.perf_counter()
    result = asyncio.run(plp_overview_enhanced())
    time1 = (time.perf_counter() - start) * 1000

    print(f"  Total time: {time1:.2f}ms")
    print(f"  Response time (reported): {result.get('response_time_ms', 0)}ms")
    print(f"  Hot/cold from cache: {result['hot_cold_analysis'].get('from_cache', False)}")
    print(f"  Top strategies: {len(result.get('top_strategies', []))}")
    print(f"  Latest draw: {result['draw_stats'].get('latest_draw_date', 'N/A')}")
    print(f"  Total draws (current era): {result['draw_stats'].get('total_draws_current_era', 0)}")

    # Show top strategies
    print("\n  Top Strategies:")
    for s in result.get('top_strategies', [])[:3]:
        print(f"    - {s['name']}: weight={s['weight']}, predictions={s['predictions']}")

    if time1 < 100:
        print("\n  ✅ PASSED - Response time acceptable (<100ms)")
    else:
        print("\n  ⚠️  WARNING - Response time slow (>100ms)")

    return time1 < 100


if __name__ == "__main__":
    test1 = test_hot_cold_performance()
    test2 = test_enhanced_overview()

    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    print(f"  Hot/Cold Cache Test: {'✅ PASSED' if test1 else '❌ FAILED'}")
    print(f"  Enhanced Overview Test: {'✅ PASSED' if test2 else '❌ FAILED'}")

    sys.exit(0 if (test1 and test2) else 1)
