#!/usr/bin/env python3
"""
Detailed diagnostic of what DATA SOURCES are being used in the actual pipeline.
Shows the decision logic and which source is selected.

No external dependencies required - works in production.
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to load from .env if available, but don't fail if python-dotenv not installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.database import get_latest_draw_date, get_all_draws
from src.loader import _is_database_stale
from loguru import logger

logger.info("=" * 80)
logger.info("DIAGNOSTIC: Data Source Selection in Pipeline (STEP 1)")
logger.info("=" * 80)

# Check environment
musl_key = os.getenv("MUSL_API_KEY")

print("\n1️⃣  ENVIRONMENT CONFIGURATION")
print("-" * 80)
print(f"MUSL_API_KEY:                {'✅ SET' if musl_key else '❌ NOT SET'}")

# Check DB state
latest_date = get_latest_draw_date()
all_draws = get_all_draws()
total_draws = len(all_draws) if all_draws is not None else 0

print("\n2️⃣  DATABASE STATE")
print("-" * 80)
print(f"Total draws in DB:           {total_draws}")
print(f"Latest draw date:            {latest_date if latest_date else 'EMPTY'}")

if latest_date:
    is_stale = _is_database_stale(latest_date, staleness_threshold_days=1)
    latest_dt = datetime.strptime(latest_date, "%Y-%m-%d")
    days_old = (datetime.now() - latest_dt).days
    print(f"Latest draw age:             {days_old} day(s) ago")
    print(f"Is stale (>1 day)?           {'❌ YES' if is_stale else '✅ NO'}")
else:
    print(f"Is stale?                    ✅ YES (DB is EMPTY)")

# Determine DB state
if latest_date is None:
    db_state = "EMPTY"
elif _is_database_stale(latest_date, staleness_threshold_days=1):
    db_state = "STALE"
else:
    db_state = "CURRENT"

print(f"DB State Classification:     {db_state}")

print("\n3️⃣  DATA SOURCE SELECTION LOGIC")
print("-" * 80)
print("\nDecision tree from update_database_from_source():")

if db_state in ["EMPTY", "STALE"]:
    print(f"\n→ DB State is {db_state}")
    print("  PRIMARY STRATEGY:  NY State API (bulk historical data)")
    print("  REASON:            Database needs full refresh")
    print("  FALLBACK:          MUSL API (if NY State fails)")
    print("\n  ⚠️  NOTE: This uses NY State, not MUSL!")
    print("  This is INTENTIONAL for bulk/historical recovery.")
    print("  To use MUSL instead, wait until DB is CURRENT (1+ day old data refresh)")
else:
    print(f"\n→ DB State is {db_state}")
    print("  PRIMARY STRATEGY:  MUSL API (incremental, single latest draw)")
    print("  REASON:            Database is up-to-date, just checking for new draws")
    print("  FALLBACK:          NY State API (if MUSL fails)")
    print("\n  ✅ This uses MUSL, which is faster and more efficient!")

print("\n" + "=" * 80)
print("ACTIONABLE INSIGHTS")
print("=" * 80)

if db_state in ["EMPTY", "STALE"]:
    print(f"\n📌 Your DB is {db_state} - this is why NY State is being used")
    print("   Current behavior is CORRECT (bulk historical data needed)")
    print("\n   Once DB becomes CURRENT:")
    print("   • MUSL will be used for incremental updates (faster)")
    print("   • NY State will only be fallback (if MUSL fails)")
    
    if not musl_key:
        print("\n⚠️  IMPORTANT: MUSL_API_KEY is not configured")
        print("   Without it, ALL incremental updates will fall back to NY State")
        print("   Recommendation: Configure MUSL_API_KEY in production")
else:
    print("\n✅ Your DB is CURRENT - using MUSL API (optimal)")
    print("\n   If you see NY State being used instead:")
    print("   • Check if MUSL_API_KEY is configured")
    print("   • Check if MUSL API is accessible from your server")
    print("   • Run diagnose_api_sources.py to verify connectivity")

print("\n" + "=" * 80)
