#!/usr/bin/env python3
"""
Comprehensive Data Sources Health Check

Tests all available data sources for SHIOL+ Powerball predictions:
1. NC Lottery Web Scraping (Primary - real-time HTML parsing)
2. MUSL API (Secondary - official API with key required)
3. NC Lottery CSV (Tertiary - historical bulk data)

Reports:
- Connectivity status
- Response format validation
- Latest available draw date
- Performance metrics
- Overall health status

Usage:
    python scripts/test_all_data_sources.py
    
    Or from production:
    /root/.venv_shiolplus/bin/python scripts/test_all_data_sources.py

Exit codes:
    0 = All sources healthy (EXCELLENT/GOOD)
    1 = Degraded (at least 1 source down)
    2 = Critical (all sources down)
"""

import os
import sys
import time
import requests
from datetime import datetime
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class DataSourceTester:
    """Test suite for all Powerball data sources.
    
    Tests sources in priority order:
    1. NC Lottery Scraping (Primary)
    2. MUSL API (Secondary)
    3. NC CSV Download (Tertiary)
    """
    
    def __init__(self):
        self.results = {
            'web_scraping': {'status': 'NOT_TESTED', 'details': {}},
            'musl_api': {'status': 'NOT_TESTED', 'details': {}},
            'nc_csv': {'status': 'NOT_TESTED', 'details': {}},
        }
        self.overall_health = 'UNKNOWN'
    
    def test_web_scraping(self) -> Dict[str, Any]:
        """Test NC Lottery web scraping (PRIMARY - Real-time source)."""
        print("\n" + "="*80)
        print("🟢 TESTING: NC Lottery Web Scraping (PRIMARY SOURCE)")
        print("="*80)
        
        try:
            from bs4 import BeautifulSoup
            
            url = "https://nclottery.com/powerball"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            
            start_time = time.time()
            response = requests.get(url, headers=headers, timeout=15)
            response_time = time.time() - start_time
            
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract draw date
            drawdate_elem = soup.find('span', id='ctl00_MainContent_lblDrawdate')
            if not drawdate_elem:
                raise ValueError("Could not find draw date element")
            
            drawdate_text = drawdate_elem.get_text(strip=True)
            
            # Extract white balls
            white_balls = []
            for i in range(1, 6):
                ball_elem = soup.find('span', id=f'ctl00_MainContent_lblBall{i}')
                if ball_elem:
                    white_balls.append(ball_elem.get_text(strip=True))
            
            # Extract powerball
            pb_elem = soup.find('span', id='ctl00_MainContent_lblPowerball')
            powerball = pb_elem.get_text(strip=True) if pb_elem else 'Not found'
            
            # Extract multiplier
            powerplay_elem = soup.find('span', id='ctl00_MainContent_lblPowerplay')
            multiplier = powerplay_elem.get_text(strip=True) if powerplay_elem else 'Not found'
            
            numbers = f"{', '.join(white_balls)} + PB {powerball}"
            
            print(f"✅ Connection: SUCCESS")
            print(f"✓ Response time: {response_time:.2f}s")
            print(f"✓ Latest draw date: {drawdate_text}")
            print(f"✓ Winning numbers: {numbers}")
            print(f"✓ PowerPlay: {multiplier}")
            print(f"✓ HTML parsing: SUCCESS")
            
            return {
                'status': 'HEALTHY',
                'error': None,
                'draw_date': drawdate_text,
                'response_time': response_time,
                'records_count': 1,
                'numbers': numbers
            }
        except ImportError:
            print("❌ BeautifulSoup not installed")
            return {
                'status': 'ERROR',
                'error': 'BeautifulSoup4 not installed - run: pip install beautifulsoup4',
                'draw_date': None,
                'response_time': None
            }
            
        except requests.exceptions.Timeout:
            print("❌ Connection: TIMEOUT (>15s)")
            return {
                'status': 'TIMEOUT',
                'error': 'Request timed out after 15 seconds',
                'draw_date': None,
                'response_time': None
            }
        except requests.exceptions.HTTPError as e:
            print(f"❌ Connection: HTTP ERROR {e.response.status_code}")
            return {
                'status': 'ERROR',
                'error': f'HTTP {e.response.status_code}: {str(e)}',
                'draw_date': None,
                'response_time': None
            }
        except Exception as e:
            print(f"❌ Connection: FAILED - {str(e)}")
            return {
                'status': 'ERROR',
                'error': str(e),
                'draw_date': None,
                'response_time': None
            }
    
    def test_musl_api(self) -> Dict[str, Any]:
        """Test MUSL API (SECONDARY - Official API with key required)."""
        print("\n" + "="*80)
        print("🔵 TESTING: MUSL API (SECONDARY SOURCE)")
        print("="*80)
        
        api_key = os.getenv("MUSL_API_KEY")
        
        if not api_key:
            print("❌ MUSL_API_KEY not found in environment")
            return {
                'status': 'UNAVAILABLE',
                'error': 'API key not configured',
                'draw_date': None,
                'response_time': None
            }
        
        print(f"✓ API Key configured: {api_key[:10]}...{api_key[-5:]}")
        
        try:
            url = "https://api.musl.com/v3/numbers"
            headers = {
                "accept": "application/json",
                "x-api-key": api_key
            }
            params = {"GameCode": "powerball"}
            
            start_time = time.time()
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response_time = time.time() - start_time
            
            response.raise_for_status()
            data = response.json()
            
            # Validate response structure
            if not isinstance(data, dict):
                raise ValueError(f"Expected dict, got {type(data)}")
            
            # Extract draw information
            draw_date = None
            for date_field in ['draw_date', 'drawDate', 'DrawDate', 'gameDrawDate']:
                if date_field in data:
                    draw_date = data[date_field]
                    break
            
            # Extract numbers for validation
            numbers_found = any(k in data for k in ['numbers', 'Numbers', 'balls', 'winningNumbers'])
            
            print(f"✅ Connection: SUCCESS")
            print(f"✓ Response time: {response_time:.2f}s")
            print(f"✓ Latest draw date: {draw_date or 'Not found'}")
            print(f"✓ Numbers present: {numbers_found}")
            print(f"✓ Response fields: {', '.join(list(data.keys())[:5])}...")
            
            return {
                'status': 'HEALTHY',
                'error': None,
                'draw_date': draw_date,
                'response_time': response_time,
                'numbers_available': numbers_found,
                'fields_count': len(data.keys())
            }
            
        except requests.exceptions.Timeout:
            print("❌ Connection: TIMEOUT (>15s)")
            return {
                'status': 'TIMEOUT',
                'error': 'Request timed out after 15 seconds',
                'draw_date': None,
                'response_time': None
            }
        except requests.exceptions.HTTPError as e:
            print(f"❌ Connection: HTTP ERROR {e.response.status_code}")
            return {
                'status': 'ERROR',
                'error': f'HTTP {e.response.status_code}: {str(e)}',
                'draw_date': None,
                'response_time': None
            }
        except Exception as e:
            print(f"❌ Connection: FAILED - {str(e)}")
            return {
                'status': 'ERROR',
                'error': str(e),
                'draw_date': None,
                'response_time': None
            }

    
    def test_nc_csv(self) -> Dict[str, Any]:
        """Test NC Lottery CSV endpoint (TERTIARY - Historical bulk data)."""
        print("\n" + "="*80)
        print("🟡 TESTING: NC Lottery CSV (TERTIARY SOURCE)")
        print("="*80)
        
        try:
            url = "https://nclottery.com/powerball-download"
            headers = {"User-Agent": "SHIOL+ Powerball Analytics"}
            
            start_time = time.time()
            response = requests.get(url, headers=headers, timeout=30)
            response_time = time.time() - start_time
            
            response.raise_for_status()
            content = response.text
            
            # Check if response is HTML instead of CSV
            if content.strip().startswith('<'):
                print(f"⚠️  Response is HTML, not CSV (endpoint may have changed)")
                print(f"✓ Response time: {response_time:.2f}s")
                print(f"✓ Status code: {response.status_code}")
                print(f"⚠️  CSV format validation: FAILED")
                
                return {
                    'status': 'DEGRADED',
                    'error': 'Endpoint returning HTML instead of CSV - may need URL update',
                    'draw_date': None,
                    'response_time': response_time,
                    'total_records': 0,
                    'csv_size': len(content)
                }
            
            # Basic CSV validation
            lines = content.strip().split('\n')
            if len(lines) < 2:
                raise ValueError("CSV has insufficient data")
            
            # Try to parse latest draw
            latest_line = lines[1] if len(lines) > 1 else ""
            fields = latest_line.split(',')
            draw_date = fields[0] if fields else 'Not found'
            numbers = ', '.join(fields[1:6]) if len(fields) >= 6 else 'Not found'
            powerball = fields[6] if len(fields) > 6 else 'Not found'
            
            print(f"✅ Connection: SUCCESS")
            print(f"✓ Response time: {response_time:.2f}s")
            print(f"✓ CSV size: {len(content)} bytes")
            print(f"✓ Total records: {len(lines) - 1}")
            print(f"✓ Latest draw date: {draw_date}")
            print(f"✓ Latest numbers: {numbers} PB:{powerball}")
            
            return {
                'status': 'HEALTHY',
                'error': None,
                'draw_date': draw_date,
                'response_time': response_time,
                'total_records': len(lines) - 1,
                'csv_size': len(content)
            }
            
        except requests.exceptions.Timeout:
            print("❌ Connection: TIMEOUT (>30s)")
            return {
                'status': 'TIMEOUT',
                'error': 'Request timed out after 30 seconds',
                'draw_date': None,
                'response_time': None
            }
        except requests.exceptions.HTTPError as e:
            print(f"❌ Connection: HTTP ERROR {e.response.status_code}")
            return {
                'status': 'ERROR',
                'error': f'HTTP {e.response.status_code}: {str(e)}',
                'draw_date': None,
                'response_time': None
            }
        except Exception as e:
            print(f"❌ Connection: FAILED - {str(e)}")
            return {
                'status': 'ERROR',
                'error': str(e),
                'draw_date': None,
                'response_time': None
            }
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all data source tests and generate summary.
        
        Tests are run in priority order:
        1. Web Scraping (Primary)
        2. MUSL API (Secondary)
        3. NC CSV (Tertiary)
        """
        print("\n" + "🚀 "+"="*76)
        print("🚀  SHIOL+ DATA SOURCES HEALTH CHECK")
        print("🚀 " + "="*76)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Priority Order: NC Lottery Scraping → MUSL API → NC CSV")
        
        # Test each source in priority order
        self.results['web_scraping'] = self.test_web_scraping()
        self.results['musl_api'] = self.test_musl_api()
        self.results['nc_csv'] = self.test_nc_csv()
        
        # Calculate overall health
        healthy_count = sum(1 for r in self.results.values() if r['status'] == 'HEALTHY')
        degraded_count = sum(1 for r in self.results.values() if r['status'] == 'DEGRADED')
        total_count = len(self.results)
        
        # Primary source (web scraping) is critical
        primary_healthy = self.results['web_scraping']['status'] == 'HEALTHY'
        
        if healthy_count == total_count:
            self.overall_health = 'EXCELLENT'
            health_emoji = '🟢'
        elif primary_healthy and healthy_count >= 2:
            self.overall_health = 'GOOD'
            health_emoji = '🟡'
        elif primary_healthy or healthy_count >= 1:
            self.overall_health = 'DEGRADED'
            health_emoji = '🟠'
        else:
            self.overall_health = 'CRITICAL'
            health_emoji = '🔴'
        
        # Print summary
        print("\n" + "="*80)
        print("📊 SUMMARY REPORT")
        print("="*80)
        
        # Define source priority labels
        source_labels = {
            'web_scraping': 'NC LOTTERY SCRAPING (PRIMARY)',
            'musl_api': 'MUSL API (SECONDARY)',
            'nc_csv': 'NC CSV DOWNLOAD (TERTIARY)'
        }
        
        for source_name, result in self.results.items():
            status = result['status']
            status_emoji = {
                'HEALTHY': '✅',
                'DEGRADED': '⚠️',
                'UNAVAILABLE': '⚠️',
                'TIMEOUT': '⏱️',
                'ERROR': '❌',
                'NOT_TESTED': '❓'
            }.get(status, '❓')
            
            label = source_labels.get(source_name, source_name.upper().replace('_', ' '))
            print(f"\n{status_emoji} {label}")
            print(f"   Status: {status}")
            if result.get('draw_date'):
                print(f"   Latest Draw: {result['draw_date']}")
            if result.get('response_time'):
                print(f"   Response Time: {result['response_time']:.2f}s")
            if result.get('numbers'):
                print(f"   Numbers: {result['numbers']}")
            if result.get('error'):
                print(f"   ⚠️  Issue: {result['error']}")
        
        print("\n" + "="*80)
        print(f"{health_emoji} OVERALL HEALTH: {self.overall_health}")
        print("="*80)
        print(f"✅ Healthy: {healthy_count}/{total_count}")
        if degraded_count > 0:
            print(f"⚠️  Degraded: {degraded_count}/{total_count}")
        
        # Recommendations
        print("\n📋 RECOMMENDATIONS:")
        
        # Check primary source
        if self.results['web_scraping']['status'] != 'HEALTHY':
            print("   🚨 PRIMARY source (NC Lottery Scraping) is down - this is critical!")
        
        # Check secondary source
        if self.results['musl_api']['status'] == 'UNAVAILABLE':
            print("   💡 Configure MUSL_API_KEY for secondary source access")
        elif self.results['musl_api']['status'] != 'HEALTHY':
            print("   ⚠️  SECONDARY source (MUSL API) has issues")
        
        # Check tertiary source
        if self.results['nc_csv']['status'] == 'DEGRADED':
            print("   ℹ️  TERTIARY source (NC CSV Download) returning HTML - endpoint may need update")
        elif self.results['nc_csv']['status'] != 'HEALTHY':
            print("   ⚠️  TERTIARY source (NC CSV Download) unavailable")
        
        # Overall recommendations
        if healthy_count == total_count:
            print("   🎉 All sources operational - maximum reliability!")
        elif primary_healthy and healthy_count >= 2:
            print("   ✓ Primary + backup sources available - system stable")
        elif primary_healthy:
            print("   ✓ Primary source available - system can operate normally")
        elif healthy_count >= 1:
            print("   ⚠️  Operating on backup sources only - reduced reliability")
        else:
            print("   🚨 CRITICAL: No data sources available - system cannot fetch draws!")
        
        print("\n" + "="*80 + "\n")
        
        return {
            'overall_health': self.overall_health,
            'healthy_count': healthy_count,
            'total_count': total_count,
            'sources': self.results,
            'timestamp': datetime.now().isoformat()
        }


def main():
    """Main entry point."""
    tester = DataSourceTester()
    results = tester.run_all_tests()
    
    # Exit with appropriate code
    if results['overall_health'] in ['EXCELLENT', 'GOOD']:
        sys.exit(0)  # Success
    elif results['overall_health'] == 'DEGRADED':
        sys.exit(1)  # Warning
    else:
        sys.exit(2)  # Critical


if __name__ == "__main__":
    main()
