#!/usr/bin/env python3
"""Test script to verify AI Winnings calculation consistency."""

import asyncio
import sys
sys.path.insert(0, '.')

from src.api_public_endpoints import get_public_recent_draws
from src.database import get_draw_analytics


async def main():
    print("=" * 60)
    print("Testing AI Winnings Consistency (Grid vs Modal)")
    print("=" * 60)

    # Get recent draws from the grid endpoint
    result = await get_public_recent_draws(limit=10)

    print(f"\nGrid endpoint status: {result['status']}")
    print(f"Query time: {result['query_time']}")
    print(f"Total draws: {result['count']}")

    print("\n" + "-" * 60)
    print(f"{'Draw Date':<15} {'Grid Prize':<12} {'Modal Prize':<12} {'Match?':<8}")
    print("-" * 60)

    all_match = True
    for draw in result['draws'][:10]:
        draw_date = draw['draw_date']
        grid_prize = draw['total_prize']

        if draw['has_predictions']:
            # Get modal analytics for comparison
            analytics = get_draw_analytics(draw_date, limit=500)
            modal_prize = analytics.get('total_prize', 0.0)

            matches = abs(grid_prize - modal_prize) < 0.01
            match_str = "✅" if matches else "❌"
            if not matches:
                all_match = False

            print(f"{draw_date:<15} ${grid_prize:<11.2f} ${modal_prize:<11.2f} {match_str}")
        else:
            print(f"{draw_date:<15} ${grid_prize:<11.2f} {'N/A':<12} (no predictions)")

    print("-" * 60)

    if all_match:
        print("\n✅ SUCCESS: Grid and Modal values are consistent!")
    else:
        print("\n❌ MISMATCH DETECTED: Some values don't match!")

    return 0 if all_match else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
