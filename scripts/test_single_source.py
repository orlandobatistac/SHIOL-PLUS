#!/usr/bin/env python3
"""Test individual sources for a specific date."""

import sys
sys.path.insert(0, '.')

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from src.loader import (
    check_powerball_official,
    check_nclottery_website,
    check_musl_api,
    check_nclottery_csv
)

def test_source(name, func, date):
    print()
    print("=" * 60)
    print(f"SOURCE: {name}")
    print("=" * 60)

    result = func(date)

    print(f"Status:  {result.status.value}")
    print(f"Success: {result.success}")
    print(f"HTTP:    {result.http_status or '-'}")
    print(f"Time:    {result.response_time_ms or '-'}ms")
    print(f"Message: {result.diagnostic_message}")

    if result.found_date:
        print(f"Found:   {result.found_date}")

    if result.draw_data:
        d = result.draw_data
        nums = f"{d['n1']}-{d['n2']}-{d['n3']}-{d['n4']}-{d['n5']}"
        print(f"Numbers: {nums} PB:{d['pb']} x{d.get('multiplier', 1)}")

    return result

if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else "2025-12-01"
    source = sys.argv[2] if len(sys.argv) > 2 else "all"

    print(f"Testing date: {date}")

    sources = {
        "1": ("powerball_official", check_powerball_official),
        "2": ("nclottery_web", check_nclottery_website),
        "3": ("musl_api", check_musl_api),
        "4": ("nclottery_csv", check_nclottery_csv),
    }

    if source == "all":
        for key, (name, func) in sources.items():
            test_source(name, func, date)
    elif source in sources:
        name, func = sources[source]
        test_source(name, func, date)
    else:
        print(f"Usage: python {sys.argv[0]} <date> [1|2|3|4|all]")
        print("  1 = powerball_official")
        print("  2 = nclottery_web")
        print("  3 = musl_api")
        print("  4 = nclottery_csv")
