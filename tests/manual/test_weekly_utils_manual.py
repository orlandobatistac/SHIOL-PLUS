"""
Manual test for week calculations including DST transitions.
Extracted from src/weekly_utils.py to keep production code clean.

Run with: python tests/manual/test_weekly_utils_manual.py
"""

from datetime import datetime, date
import pytz
from loguru import logger

import sys
sys.path.insert(0, '/workspaces/SHIOL-PLUS/src')
from weekly_utils import get_week_start_sunday_et


def test_week_calculations():
    """
    Test cases for edge conditions and DST transitions.
    Run this function to validate week calculation logic.
    """
    et_tz = pytz.timezone('US/Eastern')
    test_results = []

    test_cases = [
        # Saturday night before Sunday
        (datetime(2024, 1, 6, 23, 59), date(2024, 1, 7), "Saturday 23:59 -> Sunday Jan 7"),
        # Sunday midnight exactly
        (datetime(2024, 1, 7, 0, 0), date(2024, 1, 7), "Sunday 00:00 -> Sunday Jan 7"),
        # Sunday morning
        (datetime(2024, 1, 7, 10, 30), date(2024, 1, 7), "Sunday 10:30 -> Sunday Jan 7"),
        # Mid-week Wednesday
        (datetime(2024, 1, 10, 15, 45), date(2024, 1, 7), "Wednesday 15:45 -> Sunday Jan 7"),
        # Friday night
        (datetime(2024, 1, 12, 23, 30), date(2024, 1, 7), "Friday 23:30 -> Sunday Jan 7"),
        # Next Saturday
        (datetime(2024, 1, 13, 12, 0), date(2024, 1, 7), "Saturday 12:00 -> Sunday Jan 7"),
        # DST transition test (Spring forward - March 10, 2024)
        (datetime(2024, 3, 10, 3, 0), date(2024, 3, 10), "DST Spring forward"),
        # DST transition test (Fall back - November 3, 2024)
        (datetime(2024, 11, 3, 1, 0), date(2024, 11, 3), "DST Fall back"),
    ]

    for test_dt, expected_sunday, description in test_cases:
        try:
            test_dt_et = et_tz.localize(test_dt)
            result = get_week_start_sunday_et(test_dt_et)

            success = result == expected_sunday
            test_results.append({
                'test': description,
                'input': test_dt.strftime('%Y-%m-%d %H:%M'),
                'expected': expected_sunday.strftime('%Y-%m-%d'),
                'actual': result.strftime('%Y-%m-%d'),
                'success': success
            })

            if not success:
                logger.error(f"Test failed: {description}")
                logger.error(f"  Input: {test_dt}")
                logger.error(f"  Expected: {expected_sunday}")
                logger.error(f"  Actual: {result}")
            else:
                logger.debug(f"Test passed: {description}")

        except Exception as e:
            logger.error(f"Test error for {description}: {e}")
            test_results.append({
                'test': description,
                'input': test_dt.strftime('%Y-%m-%d %H:%M'),
                'expected': expected_sunday.strftime('%Y-%m-%d'),
                'actual': f"ERROR: {e}",
                'success': False
            })

    # Summary
    passed = sum(1 for result in test_results if result['success'])
    total = len(test_results)

    if passed == total:
        logger.info(f"All {total} week calculation tests passed!")
        return True
    else:
        logger.warning(f"Week calculation tests: {passed}/{total} passed")
        for result in test_results:
            if not result['success']:
                logger.warning(f"  FAILED: {result['test']}")
        return False


if __name__ == "__main__":
    """Run tests when executed directly."""
    print("Testing week calculations...")
    test_week_calculations()
    print("Tests completed!")
