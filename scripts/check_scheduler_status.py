#!/usr/bin/env python3
"""
Quick script to check scheduler status via API endpoint.
Useful for verifying deployment and scheduler health.

Usage:
    python scripts/check_scheduler_status.py [base_url]
    
Example:
    python scripts/check_scheduler_status.py http://localhost:8000
    python scripts/check_scheduler_status.py https://your-vps-domain.com
"""

import sys
import requests
import json
from datetime import datetime

def check_scheduler(base_url="http://localhost:8000"):
    """Check scheduler health and print formatted status"""
    
    url = f"{base_url}/api/v1/scheduler/health"
    
    print("=" * 80)
    print("🔍 SCHEDULER STATUS CHECK")
    print("=" * 80)
    print(f"\n📡 Endpoint: {url}")
    print(f"⏰ Check Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        response = requests.get(url, timeout=10)
        
        print(f"📊 HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Check for error status in JSON
            if data.get("status") == "error":
                print(f"\n❌ SCHEDULER ERROR")
                print(f"   Message: {data.get('message', 'Unknown error')}")
                print(f"\n   This is expected if:")
                print(f"   - Server just started and scheduler is initializing")
                print(f"   - Deployment in progress")
                print(f"   - Configuration issue")
                return False
            
            # Normal response
            running = data.get("scheduler_running", False)
            ready = data.get("scheduler_ready", False)
            total_jobs = data.get("total_jobs", 0)
            
            if running and ready:
                print(f"\n✅ SCHEDULER HEALTHY")
            elif running:
                print(f"\n⚠️ SCHEDULER RUNNING BUT NOT READY")
            else:
                print(f"\n❌ SCHEDULER NOT RUNNING")
            
            print(f"\n   Running: {running}")
            print(f"   Ready: {ready}")
            print(f"   Total Jobs: {total_jobs}")
            
            # Show job details
            if total_jobs > 0:
                print(f"\n📋 Scheduled Jobs:")
                jobs = data.get("jobs", [])
                for job in jobs:
                    print(f"\n   • {job.get('name', job.get('id', 'Unknown'))}")
                    print(f"     ID: {job.get('id')}")
                    next_run = job.get('next_run_time')
                    if next_run:
                        print(f"     Next Run: {next_run}")
                    else:
                        print(f"     Next Run: Not scheduled")
            
            # Show v4.0 specific jobs
            daily_sync = data.get("daily_sync_summary")
            post_drawing = data.get("post_drawing_summary")
            
            if daily_sync or post_drawing:
                print(f"\n🔄 v4.0 Jobs Status:")
                
                if daily_sync:
                    print(f"\n   Daily Full Sync (6:00 AM ET):")
                    print(f"   - Next Run: {daily_sync.get('next_run_time_et', 'Unknown')}")
                    mins = daily_sync.get('minutes_until_next_run')
                    if mins is not None:
                        hrs = int(mins // 60)
                        mins_remainder = int(mins % 60)
                        print(f"   - Time Until: {hrs}h {mins_remainder}m")
                
                if post_drawing:
                    print(f"\n   Real-time Polling (11:05 PM ET mon/wed/sat):")
                    print(f"   - Next Run: {post_drawing.get('next_run_time_et', 'Unknown')}")
                    mins = post_drawing.get('minutes_until_next_run')
                    if mins is not None:
                        hrs = int(mins // 60)
                        mins_remainder = int(mins % 60)
                        print(f"   - Time Until: {hrs}h {mins_remainder}m")
            
            # Latest pipeline execution
            latest = data.get("latest_pipeline")
            if latest:
                print(f"\n🚀 Latest Pipeline Execution:")
                print(f"   Status: {latest.get('status', 'Unknown')}")
                print(f"   Steps Completed: {latest.get('steps_completed', 0)}")
                print(f"   Tickets Generated: {latest.get('total_tickets_generated', 0)}")
                print(f"   Data Source: {latest.get('data_source', 'Unknown')}")
                age = latest.get('age_minutes')
                if age is not None:
                    if age < 60:
                        print(f"   Age: {int(age)} minutes ago")
                    else:
                        hrs = int(age // 60)
                        mins = int(age % 60)
                        print(f"   Age: {hrs}h {mins}m ago")
            
            # Uptime
            uptime_sec = data.get("scheduler_uptime_seconds")
            if uptime_sec is not None:
                hrs = int(uptime_sec // 3600)
                mins = int((uptime_sec % 3600) // 60)
                print(f"\n⏱️ Scheduler Uptime: {hrs}h {mins}m")
            
            # Notes
            notes = data.get("notes", {})
            if notes.get("version"):
                print(f"\n📌 Version: {notes.get('version')}")
                print(f"   Architecture: {notes.get('architecture', 'N/A')}")
            
            print("\n" + "=" * 80)
            return True
            
        else:
            print(f"\n❌ HTTP ERROR {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"\n❌ CONNECTION ERROR")
        print(f"   Cannot connect to {base_url}")
        print(f"   Is the server running?")
        return False
    except requests.exceptions.Timeout:
        print(f"\n❌ TIMEOUT ERROR")
        print(f"   Server took too long to respond")
        return False
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR")
        print(f"   {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    
    success = check_scheduler(base_url)
    sys.exit(0 if success else 1)
