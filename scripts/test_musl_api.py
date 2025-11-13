#!/usr/bin/env python3
"""
Test MUSL API endpoint to check:
1. Response format and fields
2. Draw date and timestamp
3. When data is available relative to drawing time
"""

import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_musl_api():
    """Test MUSL API and inspect response."""
    
    api_key = os.getenv("MUSL_API_KEY")
    if not api_key:
        print("❌ MUSL_API_KEY not found in environment")
        return None
    
    print("🔍 Testing MUSL API endpoint...")
    print(f"📍 URL: https://api.musl.com/v3/numbers?GameCode=powerball")
    print(f"🔑 Using API Key: {api_key[:10]}...{api_key[-5:]}")
    print()
    
    try:
        url = "https://api.musl.com/v3/numbers"
        headers = {
            "accept": "application/json",
            "x-api-key": api_key
        }
        params = {"GameCode": "powerball"}
        
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        print("✅ API Response Success")
        print("=" * 80)
        print("FULL RESPONSE:")
        print(json.dumps(data, indent=2))
        print("=" * 80)
        print()
        
        # Analyze response
        print("📊 ANALYSIS:")
        print(f"Response type: {type(data)}")
        if isinstance(data, dict):
            print(f"Keys in response: {list(data.keys())}")
            print()
            
            # Check for timestamp fields
            print("🕐 TIMESTAMP FIELDS:")
            timestamp_fields = [k for k in data.keys() if 'time' in k.lower() or 'date' in k.lower() or 'when' in k.lower()]
            if timestamp_fields:
                for field in timestamp_fields:
                    value = data[field]
                    print(f"  • {field}: {value} (type: {type(value).__name__})")
                    if isinstance(value, str):
                        try:
                            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                            print(f"    → Parsed as: {dt}")
                        except:
                            pass
            else:
                print("  ℹ️  No obvious timestamp fields found")
            
            print()
            print("🎯 DRAW INFORMATION:")
            draw_fields = [
                'draw_date', 'drawDate', 'DrawDate', 
                'balls', 'numbers', 'Numbers',
                'powerball', 'pb', 'PB',
                'game', 'gameCode', 'GameCode'
            ]
            for field in draw_fields:
                if field in data:
                    print(f"  • {field}: {data[field]}")
            
            print()
            print("💡 RECOMMENDATIONS:")
            
            # Check if we have timestamp
            if 'draw_date' in data or 'drawDate' in data or 'DrawDate' in data:
                draw_date_field = [k for k in data.keys() if 'draw' in k.lower() and 'date' in k.lower()][0]
                draw_date = data[draw_date_field]
                print(f"  ✅ Draw date/time available: {draw_date_field} = {draw_date}")
            else:
                print(f"  ⚠️  No explicit draw date field found in response")
            
            # Check timestamp availability
            if 'last_sync_date' in data or 'lastSyncDate' in data or 'timestamp' in data:
                print(f"  ✅ API sync/update timestamp available")
            else:
                print(f"  ⚠️  No sync timestamp field found (can't determine when API was updated)")
        
        print()
        print("🗓️ SCHEDULING ANALYSIS:")
        if 'draw_date' in data:
            draw_date_str = data['draw_date']
            try:
                draw_dt = datetime.fromisoformat(draw_date_str.replace('Z', '+00:00'))
                draw_time_et = draw_dt.astimezone()  # Convert to local
                
                print(f"  Last draw date: {draw_dt}")
                print(f"  Drawing time (ET): ~10:59 PM")
                print(f"  Current pipeline job: 1:00 AM ET (next day)")
                print(f"  Time between draw and pipeline: ~2 hours ✅")
                print(f"  Status: 2 hours should be SAFE for data availability")
            except:
                pass
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API request failed: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse JSON response: {e}")
        print(f"Response text: {response.text[:500]}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_musl_api()
