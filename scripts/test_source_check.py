#!/usr/bin/env python3
"""
Test Smart Polling Check - View diagnostics from each source.

Usage:
    python scripts/test_source_check.py [draw_date]

Examples:
    python scripts/test_source_check.py           # Uses next expected draw date
    python scripts/test_source_check.py 2024-12-02  # Specific date
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.loader import smart_polling_check
from src.date_utils import DateManager


def main():
    # Get draw date from argument or calculate next expected
    if len(sys.argv) > 1:
        draw_date = sys.argv[1]
    else:
        draw_date = DateManager.calculate_next_drawing_date()

    current_et = DateManager.get_current_et_time()

    print("=" * 70)
    print("SMART POLLING CHECK - Source Diagnostics")
    print("=" * 70)
    print(f"Current Time (ET): {current_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Checking Draw:     {draw_date}")
    print("=" * 70)
    print()

    # Run the check
    result = smart_polling_check(draw_date)

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Success:     {result['success']}")
    print(f"Source:      {result['source'] or 'None (all failed)'}")
    print(f"Elapsed:     {result['elapsed_seconds']:.2f}s")
    print()

    # Show diagnostics table
    print("DETAILED DIAGNOSTICS:")
    print("-" * 70)
    print(f"{'Source':<20} {'Status':<20} {'HTTP':<6} {'Time':<8}")
    print("-" * 70)

    for d in result['diagnostics']:
        status = d.status.value if hasattr(d.status, 'value') else str(d.status)
        http = str(d.http_status) if d.http_status else "-"
        time_ms = f"{d.response_time_ms}ms" if d.response_time_ms else "-"

        print(f"{d.source:<20} {status:<20} {http:<6} {time_ms:<8}")

        if d.diagnostic_message:
            print(f"  └─ {d.diagnostic_message}")

        if d.found_date and d.found_date != d.expected_date:
            print(f"  └─ Found date: {d.found_date} (expected: {d.expected_date})")

    print("-" * 70)

    # Show draw data if found
    if result['success'] and result['draw_data']:
        print()
        print("DRAW DATA FOUND:")
        data = result['draw_data']
        print(f"  Date:       {data.get('draw_date')}")
        print(f"  Numbers:    {data.get('n1')}-{data.get('n2')}-{data.get('n3')}-{data.get('n4')}-{data.get('n5')}")
        print(f"  Powerball:  {data.get('pb')}")
        print(f"  Multiplier: {data.get('multiplier', 'N/A')}")
        print(f"  Source:     {data.get('source')}")

    print()
    return 0 if result['success'] else 1


if __name__ == "__main__":
    sys.exit(main())
