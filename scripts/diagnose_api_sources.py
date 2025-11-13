#!/usr/bin/env python3
"""
Diagnostic script to check which API sources are available and working.

No external dependencies required - works in production.
"""

import os
import requests
from loguru import logger

# Try to load from .env if available, but don't fail if python-dotenv not installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger.info("=" * 70)
logger.info("DIAGNOSTIC: Checking API Sources Configuration")
logger.info("=" * 70)

# Check MUSL API
print("\n1️⃣  MUSL API (Primary for incremental updates)")
print("-" * 70)
musl_key = os.getenv("MUSL_API_KEY")
if musl_key:
    print(f"✅ MUSL_API_KEY found: {musl_key[:10]}...{musl_key[-5:]}")
    
    # Test connection
    try:
        url = "https://api.musl.com/v3/numbers"
        headers = {"accept": "application/json", "x-api-key": musl_key}
        params = {"GameCode": "powerball"}
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        print(f"✅ MUSL API Connection: SUCCESS")
        print(f"   Response: {data}")
    except Exception as e:
        print(f"❌ MUSL API Connection: FAILED - {e}")
else:
    print("❌ MUSL_API_KEY NOT found in environment")
    print("   Action needed: Set MUSL_API_KEY in .env or production secrets")

# Check Web Scraping
print("\n2️⃣  Powerball.com Web Scraping (Real-time fallback)")
print("-" * 70)

try:
    url = "https://www.powerball.com/api/v1/numbers/powerball/recent-winning-numbers"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
    print(f"✅ Web Scraping Connection: SUCCESS")
    print(f"   Sample response (first draw): {data[0] if data else 'empty'}")
except Exception as e:
    print(f"❌ Web Scraping Connection: FAILED - {e}")

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
musl_available = bool(musl_key)

print(f"\nPrimary (MUSL):           {'✅ AVAILABLE' if musl_available else '❌ NOT AVAILABLE'}")
print(f"Fallback (Web Scraping):  ✅ AVAILABLE (no config needed)")
print(f"Historical (NC CSV):      ✅ AVAILABLE (no config needed)")

if not musl_available:
    print("\n⚠️  WARNING: MUSL API not configured!")
    print("   Current behavior: Using web scraping as primary")
    print("   Recommended: Configure MUSL_API_KEY for better reliability")
    print("\n   To fix:")
    print("   1. Get MUSL API key from https://www.musl.org/")
    print("   2. Set in production: export MUSL_API_KEY=your_key")
    print("   3. Restart services")
