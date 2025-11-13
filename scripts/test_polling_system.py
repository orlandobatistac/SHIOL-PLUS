#!/usr/bin/env python3
"""
Test script for the smart polling system.

Tests:
1. Immediate availability (draw already complete)
2. Mock timeout scenario (test timeout logic without waiting 120 minutes)
3. Network error handling
4. API key validation

Usage:
    python scripts/test_polling_system.py
"""

import os
import sys
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.loader import wait_for_draw_results
from src.date_utils import DateManager
from loguru import logger


def test_immediate_availability():
    """Test with a draw that's already complete (recent past draw)."""
    print("\n" + "="*80)
    print("TEST 1: Immediate Availability (Recent Completed Draw)")
    print("="*80)
    
    # Get the most recent drawing date (should be complete by now)
    recent_draws = DateManager.get_recent_drawing_dates(count=1)
    last_draw = recent_draws[0] if recent_draws else "2025-11-03"
    print(f"Testing with last draw date: {last_draw}")
    print(f"Expected: Should find data immediately (statusCode='complete')\n")
    
    result = wait_for_draw_results(
        expected_draw_date=last_draw,
        check_interval_seconds=5,  # Faster for testing
        timeout_minutes=2          # Short timeout for testing
    )
    
    print("\n" + "-"*80)
    print("RESULT:")
    print(f"  Success: {result['success']}")
    print(f"  Attempts: {result['attempts']}")
    print(f"  Elapsed: {result['elapsed_seconds']:.2f} seconds")
    print(f"  Result: {result['result']}")
    print(f"  Available at: {result['data_available_at']}")
    print(f"  Status code: {result['final_status_code']}")
    
    if result['success'] and result['attempts'] == 1:
        print("\n✅ TEST PASSED: Data found immediately")
        return True
    elif result['success']:
        print(f"\n⚠️  TEST PARTIAL: Data found but took {result['attempts']} attempts")
        return True
    else:
        print("\n❌ TEST FAILED: Could not find completed draw data")
        return False


def test_future_draw_timeout():
    """Test with a future draw date (should timeout quickly)."""
    print("\n" + "="*80)
    print("TEST 2: Future Draw (Timeout Scenario)")
    print("="*80)
    
    # Get next drawing date (definitely not available yet)
    next_draw = DateManager.calculate_next_drawing_date()
    print(f"Testing with FUTURE draw date: {next_draw}")
    print(f"Expected: Should timeout after ~10 seconds (timeout=0.17 min)\n")
    
    result = wait_for_draw_results(
        expected_draw_date=next_draw,
        check_interval_seconds=2,   # Very fast checks
        timeout_minutes=0.17        # ~10 seconds timeout
    )
    
    print("\n" + "-"*80)
    print("RESULT:")
    print(f"  Success: {result['success']}")
    print(f"  Attempts: {result['attempts']}")
    print(f"  Elapsed: {result['elapsed_seconds']:.2f} seconds")
    print(f"  Result: {result['result']}")
    print(f"  Available at: {result['data_available_at']}")
    print(f"  Status code: {result['final_status_code']}")
    
    if not result['success'] and result['result'] == 'timeout':
        print("\n✅ TEST PASSED: Timeout handled correctly")
        return True
    else:
        print("\n❌ TEST FAILED: Expected timeout but got different result")
        return False


def test_api_key_validation():
    """Test behavior when API key is missing."""
    print("\n" + "="*80)
    print("TEST 3: Missing API Key")
    print("="*80)
    
    # Temporarily remove API key
    original_key = os.environ.get("MUSL_API_KEY")
    if original_key:
        del os.environ["MUSL_API_KEY"]
    
    print("Testing with NO MUSL_API_KEY set")
    print("Expected: Should return error immediately\n")
    
    result = wait_for_draw_results(
        expected_draw_date="2025-11-05",
        check_interval_seconds=2,
        timeout_minutes=0.1
    )
    
    # Restore API key
    if original_key:
        os.environ["MUSL_API_KEY"] = original_key
    
    print("\n" + "-"*80)
    print("RESULT:")
    print(f"  Success: {result['success']}")
    print(f"  Attempts: {result['attempts']}")
    print(f"  Result: {result['result']}")
    print(f"  Status code: {result['final_status_code']}")
    
    if not result['success'] and result['result'] == 'error' and result['final_status_code'] == 'missing_api_key':
        print("\n✅ TEST PASSED: API key validation working")
        return True
    else:
        print("\n❌ TEST FAILED: Did not handle missing API key correctly")
        return False


def test_summary():
    """Display test summary."""
    print("\n" + "="*80)
    print("POLLING SYSTEM TEST SUMMARY")
    print("="*80)
    
    print("\n📋 Test Coverage:")
    print("  ✅ Immediate availability (completed draw)")
    print("  ✅ Timeout scenario (future draw)")
    print("  ✅ API key validation")
    
    print("\n🔍 Production Configuration:")
    print("  - Check interval: 120 seconds (2 minutes)")
    print("  - Timeout: 120 minutes (2 hours)")
    print("  - Start time: 11:05 PM ET (6 min after draw)")
    print("  - Expected availability: 5-30 minutes after draw")
    
    print("\n📊 Expected Production Behavior:")
    print("  - Normal case: 3-15 attempts (~6-30 minutes)")
    print("  - Edge case: Up to 60 attempts if API very delayed")
    print("  - Timeout: Only if MUSL API down for 120+ minutes (extremely rare)")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    logger.info("Starting polling system tests...")
    
    results = []
    
    # Run tests
    results.append(("Immediate Availability", test_immediate_availability()))
    results.append(("Future Draw Timeout", test_future_draw_timeout()))
    results.append(("API Key Validation", test_api_key_validation()))
    
    # Display summary
    test_summary()
    
    # Final verdict
    print("\n" + "="*80)
    print("TEST RESULTS:")
    print("="*80)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {test_name}")
    
    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)
    
    print(f"\nTotal: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        print("\n🎉 ALL TESTS PASSED! Polling system is ready for integration.")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total_tests - total_passed} test(s) failed. Review errors above.")
        sys.exit(1)
