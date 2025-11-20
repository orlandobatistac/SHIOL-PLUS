#!/usr/bin/env python3
"""
Test script to verify data leakage fix.

This script validates that StrategyManager correctly filters historical data
when max_date is provided, preventing data leakage in historical predictions.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.database import get_all_draws
from src.strategy_generators import StrategyManager
from loguru import logger

def test_get_all_draws_filtering():
    """Test that get_all_draws correctly filters by max_date"""
    logger.info("=" * 70)
    logger.info("TEST 1: get_all_draws() filtering")
    logger.info("=" * 70)
    
    # Test without filter (should get all draws)
    all_draws = get_all_draws()
    logger.info(f"✅ Without filter: {len(all_draws)} draws loaded")
    logger.info(f"   Date range: {all_draws['draw_date'].min()} to {all_draws['draw_date'].max()}")
    
    # Test with filter (should exclude draws >= max_date)
    test_date = "2025-11-17"
    filtered_draws = get_all_draws(max_date=test_date)
    logger.info(f"\n✅ With max_date={test_date}: {len(filtered_draws)} draws loaded")
    logger.info(f"   Date range: {filtered_draws['draw_date'].min()} to {filtered_draws['draw_date'].max()}")
    
    # Verify no draws >= test_date
    invalid_draws = filtered_draws[filtered_draws['draw_date'] >= test_date]
    if len(invalid_draws) > 0:
        logger.error(f"❌ FAIL: Found {len(invalid_draws)} draws >= {test_date}")
        logger.error(f"   Invalid draws: {invalid_draws['draw_date'].tolist()}")
        return False
    else:
        logger.success(f"✅ PASS: No draws >= {test_date} in filtered data")
    
    # Verify we filtered out some draws
    expected_filtered = len(all_draws) - len(filtered_draws)
    if expected_filtered > 0:
        logger.success(f"✅ PASS: Correctly filtered out {expected_filtered} draws")
    else:
        logger.warning(f"⚠️  WARNING: No draws were filtered (test_date may be after all draws)")
    
    return True


def test_strategy_manager_filtering():
    """Test that StrategyManager correctly uses max_date"""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 2: StrategyManager max_date parameter")
    logger.info("=" * 70)
    
    test_date = "2025-11-17"
    
    # Create manager with max_date
    logger.info(f"\n📊 Creating StrategyManager with max_date={test_date}")
    manager = StrategyManager(max_date=test_date)
    
    # Check that strategies loaded correct data
    # Pick a strategy and verify its draws_df
    freq_strategy = manager.strategies['frequency_weighted']
    
    if freq_strategy.draws_df.empty:
        logger.error("❌ FAIL: Strategy has empty draws_df")
        return False
    
    logger.info(f"✅ frequency_weighted strategy loaded {len(freq_strategy.draws_df)} draws")
    logger.info(f"   Date range: {freq_strategy.draws_df['draw_date'].min()} to {freq_strategy.draws_df['draw_date'].max()}")
    
    # Verify no draws >= test_date
    invalid_draws = freq_strategy.draws_df[freq_strategy.draws_df['draw_date'] >= test_date]
    if len(invalid_draws) > 0:
        logger.error(f"❌ FAIL: Strategy has {len(invalid_draws)} draws >= {test_date}")
        logger.error(f"   Invalid draws: {invalid_draws['draw_date'].tolist()}")
        return False
    else:
        logger.success(f"✅ PASS: Strategy correctly filtered to draws < {test_date}")
    
    return True


def test_ticket_generation():
    """Test that ticket generation works with filtered data"""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 3: Ticket generation with filtered data")
    logger.info("=" * 70)
    
    test_date = "2025-11-17"
    
    # Generate 10 test tickets
    logger.info(f"\n🎲 Generating 10 tickets with max_date={test_date}")
    manager = StrategyManager(max_date=test_date)
    
    try:
        tickets = manager.generate_balanced_tickets(total=10)
        
        if len(tickets) != 10:
            logger.error(f"❌ FAIL: Expected 10 tickets, got {len(tickets)}")
            return False
        
        logger.success(f"✅ PASS: Generated {len(tickets)} tickets successfully")
        
        # Verify ticket format
        for i, ticket in enumerate(tickets[:3], 1):  # Check first 3
            wb = ticket['white_balls']
            pb = ticket['powerball']
            strategy = ticket['strategy']
            
            # Validate
            if len(wb) != 5:
                logger.error(f"❌ FAIL: Ticket {i} has {len(wb)} white balls (expected 5)")
                return False
            
            if not all(1 <= n <= 69 for n in wb):
                logger.error(f"❌ FAIL: Ticket {i} has out-of-range white balls: {wb}")
                return False
            
            if not 1 <= pb <= 26:
                logger.error(f"❌ FAIL: Ticket {i} has out-of-range powerball: {pb}")
                return False
            
            if wb != sorted(wb):
                logger.error(f"❌ FAIL: Ticket {i} has unsorted white balls: {wb}")
                return False
            
            logger.info(f"   Ticket {i}: {wb} + PB {pb} (strategy: {strategy})")
        
        logger.success(f"✅ PASS: All tickets are valid")
        return True
        
    except Exception as e:
        logger.error(f"❌ FAIL: Ticket generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    logger.info("\n")
    logger.info("╔" + "=" * 68 + "╗")
    logger.info("║" + " " * 15 + "DATA LEAKAGE FIX VALIDATION" + " " * 26 + "║")
    logger.info("╚" + "=" * 68 + "╝")
    
    tests = [
        ("get_all_draws() filtering", test_get_all_draws_filtering),
        ("StrategyManager max_date", test_strategy_manager_filtering),
        ("Ticket generation", test_ticket_generation)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ Test '{test_name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info("=" * 70)
    logger.info(f"Results: {passed}/{total} tests passed")
    logger.info("=" * 70)
    
    if passed == total:
        logger.success("\n🎉 ALL TESTS PASSED! Data leakage fix is working correctly.")
        return 0
    else:
        logger.error(f"\n❌ {total - passed} test(s) failed. Fix required.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
