import os
from typing import Optional, Dict, List

import pandas as pd
import requests
from loguru import logger

from src.database import (
    bulk_insert_draws,
    get_all_draws,
    get_latest_draw_date,
    initialize_database,
)
from src.database import get_db_connection


class DataLoader:
    """
    Loads historical Powerball data from the SQLite database.
    This class acts as an abstraction layer for data retrieval.
    """

    def __init__(self):
        """Initializes the DataLoader."""
        logger.info("DataLoader initialized to read from SQLite database.")

    def load_historical_data(self) -> pd.DataFrame:
        """
        Loads all historical Powerball data from the database.

        Returns:
            pd.DataFrame: A DataFrame with all historical data, sorted by date.
                         Returns an empty DataFrame if an error occurs.
        """
        try:
            df = get_all_draws()
            if df.empty:
                logger.warning(
                    "Historical data is empty. The database may need to be updated."
                )
            return df
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while loading data from the database: {e}"
            )
            return pd.DataFrame()


def get_data_loader() -> DataLoader:
    """
    Factory function to get an instance of DataLoader.
    """
    return DataLoader()


def _is_database_stale(latest_date_str: Optional[str], staleness_threshold_days: int = 2) -> bool:
    """
    Determines if the database is stale based on the latest draw date.
    
    Powerball draws occur on: Tue, Thu, Sun
    - Tue → Thu: 2 days
    - Thu → Sun: 3 days
    - Sun → Tue: 2 days
    - Average gap: ~2.33 days
    
    A threshold of 2 days means:
    - DB marked CURRENT while within normal 2-3 day drawing cycle
    - DB marked STALE only if >2 days (indicates missed updates)
    - Uses MUSL (incremental) for CURRENT, NC CSV (full) for STALE
    
    Args:
        latest_date_str: Latest draw date from DB (None if empty)
        staleness_threshold_days: Days to consider data stale (default: 2 for Powerball schedule)
        
    Returns:
        bool: True if stale (>threshold days old) or empty, False if current
    """
    if latest_date_str is None:
        logger.info("Database is empty (no draws found)")
        return True
    
    try:
        from src.date_utils import DateManager
        
        latest_date = pd.to_datetime(latest_date_str)
        current_et = DateManager.get_current_et_time()
        
        days_old = (current_et.date() - latest_date.date()).days
        
        is_stale = days_old > staleness_threshold_days
        
        if is_stale:
            logger.warning(f"Database is stale: latest draw is {days_old} days old ({latest_date_str})")
        else:
            logger.info(f"Database is current: latest draw is {days_old} days old ({latest_date_str})")
            
        return is_stale
        
    except Exception as e:
        logger.error(f"Error checking database staleness: {e}")
        return True  # Assume stale on error (safer to refresh)


# ============================================================================
# LEGACY FUNCTIONS REMOVED
# ============================================================================
# The following legacy functions have been removed and replaced with the new
# unified adaptive polling system:
#
# - update_database_from_source() → Replaced by realtime_draw_polling_unified() + daily_full_sync_job()
# - _transform_api_data() → No longer needed (direct parsing in new functions)
# - _parse_draw_record() → No longer needed (using _parse_musl_format directly)
# - _fetch_from_musl_api() → Replaced by fetch_single_draw_musl()
# - wait_for_draw_results() → Replaced by realtime_draw_polling_unified()
#
# New system benefits:
# - Simpler architecture (no complex state management)
# - 3-layer fallback per iteration (Web → MUSL → NC CSV)
# - Adaptive polling intervals (2min → 5min → 10min)
# - Comprehensive logging at each step
# - Daily safety net for completeness
# ============================================================================


# ============================================================================
# HELPER FUNCTIONS (Still needed by new system)
# ============================================================================

def _parse_musl_format(item: Dict) -> Optional[Dict]:
    """
    Parses MUSL API format.
    
    Expected format:
    {
        "numbers": [
            {"ruleCode": "white-balls", "value": "10", "orderDrawn": 1},
            ...
            {"ruleCode": "powerball", "value": "22", "orderDrawn": 1}
        ],
        "drawDate": "2024-10-05"
    }
    """
    try:
        numbers_list = item.get("numbers", [])
        draw_date = item.get("drawDate", "")

        white_balls = []
        powerball = None

        for num_obj in numbers_list:
            rule_code = num_obj.get("ruleCode", "")
            value = int(num_obj.get("value", 0))

            if rule_code == "white-balls":
                white_balls.append(value)
            elif rule_code == "powerball":
                powerball = value

        if len(white_balls) != 5 or powerball is None:
            return None

        white_balls.sort()

        return {
            "draw_date": draw_date,
            "n1": white_balls[0],
            "n2": white_balls[1],
            "n3": white_balls[2],
            "n4": white_balls[3],
            "n5": white_balls[4],
            "pb": powerball
        }
    except Exception as e:
        logger.warning(f"Error parsing MUSL format: {e}")
        return None


def fetch_musl_jackpot() -> Optional[Dict]:
    """
    Fetches current Powerball jackpot information from MUSL Grand Prize API.
    
    Returns:
        Dict containing:
        - annuity: Current jackpot (annuitized)
        - cash: Current cash value
        - nextAnnuity: Next jackpot estimate
        - nextCash: Next cash value estimate
        - prizeCombined: Formatted string with both values
        - nextPrizeCombined: Formatted string for next jackpot
        - drawDate: Current draw date
        - nextDrawDate: Next drawing date
        Or None if request fails.
    """
    try:
        api_key = os.getenv("MUSL_API_KEY")
        if not api_key:
            logger.warning("MUSL_API_KEY not found in environment variables")
            return None

        url = "https://api.musl.com/v3/grandprize"
        headers = {
            "accept": "application/json",
            "x-api-key": api_key
        }
        params = {"GameCode": "powerball"}

        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()

        data = response.json()

        if not data or "grandPrize" not in data:
            return None

        grand_prize = data["grandPrize"]
        next_drawing = data.get("nextDrawing", {})

        return {
            "annuity": grand_prize.get("annuity", 0),
            "cash": grand_prize.get("cash", 0),
            "nextAnnuity": grand_prize.get("nextAnnuity", 0),
            "nextCash": grand_prize.get("nextCash", 0),
            "prizeText": grand_prize.get("prizeText", ""),
            "cashPrizeText": grand_prize.get("cashPrizeText", ""),
            "prizeCombined": grand_prize.get("prizeCombined", ""),
            "nextPrizeText": grand_prize.get("nextPrizeText", ""),
            "nextCashPrizeText": grand_prize.get("nextCashPrizeText", ""),
            "nextPrizeCombined": grand_prize.get("nextPrizeCombined", ""),
            "drawDate": data.get("drawDate", ""),
            "nextDrawDate": next_drawing.get("drawDate", "")
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"MUSL Grand Prize API request failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching jackpot from MUSL: {e}")
        return None



# ============================================================================
# NEW UNIFIED ADAPTIVE POLLING SYSTEM  
# ============================================================================

def scrape_powerball_website(expected_draw_date: str) -> Optional[Dict]:
    """
    Scrapes NC Lottery website for official draw results (Layer 1 - HTML Parsing).
    
    This is the PRIMARY data source as it scrapes directly from NC Lottery's
    Powerball results page. Results typically available 5-15 minutes after draw.
    
    Args:
        expected_draw_date: Date in YYYY-MM-DD format (e.g., "2025-11-10")
        
    Returns:
        Dict with parsed draw data, or None if not found/error
        {
            'draw_date': '2025-11-10',
            'n1': 12, 'n2': 24, 'n3': 35, 'n4': 47, 'n5': 58,
            'pb': 9,
            'multiplier': 2,
            'source': 'web_scraping'
        }
    
    Example:
        >>> result = scrape_powerball_website('2025-11-10')
        >>> if result:
        >>>     print(f"Found draw: [{result['n1']}, ...] + PB {result['pb']}")
    """
    try:
        from bs4 import BeautifulSoup
        
        logger.info(f"🌐 [web_scraping] Attempting to scrape nclottery.com for date {expected_draw_date}")
        
        # NC Lottery Powerball results page
        url = "https://nclottery.com/powerball"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://nclottery.com/"
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract draw date directly (it's in a unique ID)
        drawdate_elem = soup.find('span', id='ctl00_MainContent_lblDrawdate')
        if not drawdate_elem:
            logger.warning(f"🌐 [web_scraping] Could not find drawdate span with ID")
            return None
        
        # Parse date (format: "Saturday, Nov 8, 2025" or "Sat, Nov 8")
        drawdate_text = drawdate_elem.get_text(strip=True)
        try:
            # Try full format first: "Saturday, Nov 8, 2025"
            if ', 20' in drawdate_text:  # Has year
                parsed_date = pd.to_datetime(drawdate_text, format='%A, %b %d, %Y')
            else:
                # Short format without year: "Sat, Nov 8" - add current year
                import datetime
                current_year = datetime.datetime.now().year
                drawdate_with_year = f"{drawdate_text}, {current_year}"
                parsed_date = pd.to_datetime(drawdate_with_year, format='%a, %b %d, %Y')
            
            normalized_date = parsed_date.strftime('%Y-%m-%d')
        except Exception as e:
            logger.warning(f"🌐 [web_scraping] Could not parse date '{drawdate_text}': {e}")
            return None
        
        # Check if this is the expected date
        if normalized_date != expected_draw_date:
            logger.warning(
                f"🌐 [web_scraping] Found draw for {normalized_date}, "
                f"but expected {expected_draw_date}"
            )
            return None
        
        # Extract white balls (5 balls)
        white_balls = []
        for i in range(1, 6):
            ball_elem = soup.find('span', id=f'ctl00_MainContent_lblBall{i}')
            if ball_elem:
                white_balls.append(int(ball_elem.get_text(strip=True)))
        
        # Extract powerball
        pb_elem = soup.find('span', id='ctl00_MainContent_lblPowerball')
        if not pb_elem:
            logger.warning(f"🌐 [web_scraping] Could not find powerball element")
            return None
        powerball = int(pb_elem.get_text(strip=True))
        
        # Extract multiplier (format: "POWER PLAY 2x")
        multiplier = 1
        powerplay_elem = soup.find('span', id='ctl00_MainContent_lblPowerplay')
        if powerplay_elem:
            powerplay_text = powerplay_elem.get_text(strip=True)
            # Extract number before 'x' (e.g., "POWER PLAY 2x" -> 2)
            import re
            match = re.search(r'(\d+)x', powerplay_text)
            if match:
                multiplier = int(match.group(1))
        
        if len(white_balls) == 5 and powerball:
            result = {
                'draw_date': expected_draw_date,
                'n1': white_balls[0],
                'n2': white_balls[1],
                'n3': white_balls[2],
                'n4': white_balls[3],
                'n5': white_balls[4],
                'pb': powerball,
                'multiplier': multiplier,
                'source': 'web_scraping'
            }
            
            logger.info(
                f"🌐 [web_scraping] ✅ SUCCESS! Found draw {expected_draw_date}: "
                f"[{result['n1']}, {result['n2']}, {result['n3']}, {result['n4']}, {result['n5']}] + PB {result['pb']} (x{result['multiplier']})"
            )
            return result
        
        logger.warning(f"🌐 [web_scraping] Incomplete data: white_balls={white_balls}, pb={powerball}")
        return None
        
    except requests.exceptions.RequestException as e:
        logger.warning(f"🌐 [web_scraping] Network error: {e}")
        return None
    except Exception as e:
        logger.error(f"🌐 [web_scraping] Unexpected error: {e}", exc_info=True)
        return None


def fetch_single_draw_musl(expected_draw_date: str) -> Optional[Dict]:
    """
    Fetches single draw from MUSL API v3 (Layer 2 - Fast, Official).
    
    Uses the official MUSL API /v3/numbers endpoint to fetch specific draw
    by date. This is more reliable than web scraping and faster than NC CSV.
    
    Args:
        expected_draw_date: Date in YYYY-MM-DD format (e.g., "2025-11-10")
        
    Returns:
        Dict with draw data if found and complete, None otherwise
        {
            'draw_date': '2025-11-10',
            'n1': 3, 'n2': 53, 'n3': 60, 'n4': 62, 'n5': 68,
            'pb': 11,
            'multiplier': 2,
            'source': 'musl_api'
        }
    """
    try:
        logger.info(f"🎯 [musl_api] Fetching draw from MUSL API v3 for date {expected_draw_date}")
        
        api_key = os.getenv("MUSL_API_KEY")
        if not api_key:
            logger.warning("🎯 [musl_api] MUSL_API_KEY not found in environment")
            return None
        
        # MUSL API v3 endpoint (discovered via Swagger documentation)
        url = "https://api.musl.com/v3/numbers"
        headers = {
            "x-api-key": api_key,
            "Accept": "application/json"
        }
        params = {
            "DrawDate": expected_draw_date,  # YYYY-MM-DD format
            "GameCode": "powerball"
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        # Validate response structure
        if not data or 'drawDate' not in data:
            logger.warning(f"🎯 [musl_api] Invalid response structure")
            return None
        
        draw_date = data.get('drawDate', '')
        status_code = data.get('statusCode', '')
        
        # Verify this is the expected draw
        if draw_date != expected_draw_date:
            logger.info(
                f"🎯 [musl_api] API returned draw {draw_date}, expecting {expected_draw_date}"
            )
            return None
        
        # Check if draw is complete
        if status_code != 'complete':
            logger.info(
                f"🎯 [musl_api] Draw {draw_date} has statusCode='{status_code}' (waiting for 'complete')"
            )
            return None
        
        # Parse numbers array
        # Structure: [
        #   {"itemCode":"powerball","ruleCode":"white-balls","value":"03",...},
        #   {"itemCode":"powerball","ruleCode":"powerball","value":"11",...},
        #   {"itemCode":"power-play","ruleCode":"power-play","value":"02",...}
        # ]
        numbers_data = data.get('numbers', [])
        if not numbers_data:
            logger.warning(f"🎯 [musl_api] No numbers array in response")
            return None
        
        # Extract white balls (ruleCode='white-balls')
        white_balls = []
        for num_obj in numbers_data:
            if num_obj.get('ruleCode') == 'white-balls':
                white_balls.append(int(num_obj.get('value', 0)))
        
        white_balls.sort()  # MUSL returns in draw order, we need sorted
        
        # Extract powerball (ruleCode='powerball')
        powerball = None
        for num_obj in numbers_data:
            if num_obj.get('ruleCode') == 'powerball':
                powerball = int(num_obj.get('value', 0))
                break
        
        # Extract multiplier (itemCode='power-play')
        multiplier = 1
        for num_obj in numbers_data:
            if num_obj.get('itemCode') == 'power-play':
                multiplier = int(num_obj.get('value', 1))
                break
        
        # Validate we got all required data
        if len(white_balls) != 5 or powerball is None:
            logger.warning(
                f"🎯 [musl_api] Incomplete data: white_balls={white_balls}, pb={powerball}"
            )
            return None
        
        result = {
            'draw_date': expected_draw_date,
            'n1': white_balls[0],
            'n2': white_balls[1],
            'n3': white_balls[2],
            'n4': white_balls[3],
            'n5': white_balls[4],
            'pb': powerball,
            'multiplier': multiplier,
            'source': 'musl_api'
        }
        
        logger.info(
            f"🎯 [musl_api] ✅ SUCCESS! Found complete draw {draw_date}: "
            f"[{result['n1']}, {result['n2']}, {result['n3']}, {result['n4']}, {result['n5']}] + PB {result['pb']} (x{result['multiplier']})"
        )
        
        return result
        
    except requests.exceptions.RequestException as e:
        logger.warning(f"🎯 [musl_api] Network error: {e}")
        return None
    except Exception as e:
        logger.error(f"🎯 [musl_api] Unexpected error: {e}", exc_info=True)
        return None


def fetch_single_draw_nclottery_csv(expected_draw_date: str) -> Optional[Dict]:
    """
    Fetches single draw from NC Lottery CSV download (Layer 3 - CSV Fallback).
    
    Downloads and parses the complete historical CSV from NC Lottery.
    Most comprehensive source with 2,250+ draws from 2006 to present.
    No API key required, no rate limits.
    
    Args:
        expected_draw_date: Date in YYYY-MM-DD format (e.g., "2025-11-08")
        
    Returns:
        Dict with draw data if found, None otherwise
        {
            'draw_date': '2025-11-08',
            'n1': 3, 'n2': 53, 'n3': 60, 'n4': 62, 'n5': 68,
            'pb': 11,
            'multiplier': 2,
            'source': 'nclottery_csv'
        }
    
    Note:
        - CSV contains both main draws and "DoubleDraw" entries
        - Only main draws (SubName is NaN) are returned
        - Numbers are automatically sorted from Ball 1-5
        - Power Play defaults to 1 if missing (pre-2012 draws)
    """
    try:
        logger.info(f"📂 [nclottery_csv] Fetching draw from NC Lottery CSV for date {expected_draw_date}")
        
        # Download CSV
        csv_url = "https://nclottery.com/powerball-download"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        response = requests.get(csv_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Parse CSV with pandas
        from io import StringIO
        csv_content = StringIO(response.text)
        df = pd.read_csv(csv_content)
        
        # Filter to main draws only (exclude DoubleDraw)
        main_draws = df[df['SubName'].isna()].copy()
        
        # Remove disclaimer row (has NaN in Ball columns)
        main_draws = main_draws[main_draws['Ball 1'].notna()].copy()
        
        # Parse dates to YYYY-MM-DD format
        main_draws['parsed_date'] = pd.to_datetime(main_draws['Date'], format='%m/%d/%Y')
        main_draws['date_str'] = main_draws['parsed_date'].dt.strftime('%Y-%m-%d')
        
        # Find the specific draw
        target_draw = main_draws[main_draws['date_str'] == expected_draw_date]
        
        if target_draw.empty:
            logger.info(f"📂 [nclottery_csv] Draw {expected_draw_date} not found in NC Lottery CSV")
            return None
        
        # Extract and parse the draw
        row = target_draw.iloc[0]
        
        # Sort white balls (CSV has them in draw order, not sorted)
        white_balls = sorted([
            int(row['Ball 1']),
            int(row['Ball 2']),
            int(row['Ball 3']),
            int(row['Ball 4']),
            int(row['Ball 5'])
        ])
        
        powerball = int(row['Powerball'])
        
        # Power Play might be NaN for older draws (pre-2012)
        multiplier = int(row['Power Play']) if pd.notna(row['Power Play']) else 1
        
        result = {
            'draw_date': expected_draw_date,
            'n1': white_balls[0],
            'n2': white_balls[1],
            'n3': white_balls[2],
            'n4': white_balls[3],
            'n5': white_balls[4],
            'pb': powerball,
            'multiplier': multiplier,
            'source': 'nclottery_csv'
        }
        
        logger.info(
            f"📂 [nclottery_csv] ✅ SUCCESS! Found draw {expected_draw_date}: "
            f"[{result['n1']}, {result['n2']}, {result['n3']}, {result['n4']}, {result['n5']}] + PB {result['pb']} (x{result['multiplier']})"
        )
        
        return result
        
    except requests.exceptions.RequestException as e:
        logger.warning(f"📂 [nclottery_csv] Network error downloading CSV: {e}")
        return None
    except Exception as e:
        logger.error(f"📂 [nclottery_csv] Unexpected error: {e}", exc_info=True)
        return None


def quick_health_check_sources() -> Dict[str, bool]:
    """
    Quick health check for all data sources (5s timeout each).
    
    Performs lightweight connectivity tests WITHOUT fetching draw data.
    Used before polling to detect problematic sources and avoid hanging.
    
    Returns:
        Dict with source availability:
        {
            'web_scraping': bool,
            'musl_api': bool,
            'nclottery_csv': bool
        }
    
    Example:
        >>> health = quick_health_check_sources()
        >>> print(health)
        {'web_scraping': True, 'musl_api': True, 'nclottery_csv': False}
    """
    import requests
    
    health_status = {
        'web_scraping': False,
        'musl_api': False,
        'nclottery_csv': False
    }
    
    logger.info("🏥 [health_check] Running quick health check on all sources (5s timeout)...")
    
    # Test 1: NC Lottery Web Scraping
    try:
        url = "https://nclottery.com/powerball"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200 and len(response.text) > 1000:
            health_status['web_scraping'] = True
            logger.info(f"   ✅ NC Lottery Scraping: HEALTHY ({response.status_code}, {len(response.text)} bytes)")
        else:
            logger.warning(f"   ⚠️  NC Lottery Scraping: DEGRADED (status {response.status_code})")
    except Exception as e:
        logger.warning(f"   ❌ NC Lottery Scraping: UNAVAILABLE ({str(e)[:50]})")
    
    # Test 2: MUSL API
    try:
        api_key = os.getenv("MUSL_API_KEY")
        if not api_key:
            logger.info(f"   ⚠️  MUSL API: SKIPPED (no API key configured)")
        else:
            url = "https://api.musl.com/v3/numbers"
            headers = {
                "accept": "application/json",
                "x-api-key": api_key
            }
            params = {"GameCode": "powerball"}
            response = requests.get(url, headers=headers, params=params, timeout=5)
            if response.status_code == 200:
                health_status['musl_api'] = True
                logger.info(f"   ✅ MUSL API: HEALTHY ({response.status_code})")
            else:
                logger.warning(f"   ⚠️  MUSL API: DEGRADED (status {response.status_code})")
    except Exception as e:
        logger.warning(f"   ❌ MUSL API: UNAVAILABLE ({str(e)[:50]})")
    
    # Test 3: NC Lottery CSV
    try:
        url = "https://nclottery.com/powerball-download"
        headers = {"User-Agent": "SHIOL+ Powerball Analytics"}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200 and response.text.startswith('"Date"'):
            health_status['nclottery_csv'] = True
            logger.info(f"   ✅ NC CSV Download: HEALTHY ({response.status_code}, CSV format OK)")
        else:
            logger.warning(f"   ⚠️  NC CSV Download: DEGRADED (invalid format or status {response.status_code})")
    except Exception as e:
        logger.warning(f"   ❌ NC CSV Download: UNAVAILABLE ({str(e)[:50]})")
    
    healthy_count = sum(health_status.values())
    logger.info(f"🏥 [health_check] Complete: {healthy_count}/3 sources healthy")
    logger.info(f"🏥 [health_check] Active sources: {[k for k, v in health_status.items() if v]}")
    
    return health_status


def realtime_draw_polling_unified(expected_draw_date: str) -> Dict:
    """
    UNIFIED ADAPTIVE POLLING across all 3 data sources.
    
    Strategy:
    - Single loop tries ALL 3 sources each iteration (NC Scraping → MUSL → NC CSV)
    - Adaptive intervals: 2min (first 30min) → 5min (next 30min) → 10min (after 60min)
    - Timeout at 6:00 AM next day (Daily Full Sync takes over)
    - First source that responds wins
    
    This replaces the old smart polling system with a simpler, more reliable approach
    similar to the original Excel-based hourly polling.
    
    Args:
        expected_draw_date: Draw date to poll for (YYYY-MM-DD format)
        
    Returns:
        Dict with polling results:
        {
            'success': bool,
            'draw_data': Dict or None,
            'source': str (web_scraping|musl_api|nclottery_csv),
            'attempts': int,
            'elapsed_seconds': float,
            'result': str (success|timeout|error)
        }
    
    Example Timeline (Monday 11:05 PM draw):
        23:05:00 → Attempt #1 (Web→MUSL→NY): None (interval: 2min)
        23:07:00 → Attempt #2 (Web→MUSL→NY): None (interval: 2min)
        23:09:00 → Attempt #3 (Web→MUSL→NY): ✅ Web scraping SUCCESS!
        Result: {'success': True, 'source': 'web_scraping', 'attempts': 3, 'elapsed': 240s}
    """
    from datetime import datetime, timedelta
    from src.date_utils import DateManager
    import time
    
    start_time = datetime.now()
    attempts = 0
    
    # Calculate timeout: 6 hours for adaptive polling
    # Rationale: Draw numbers may take hours to publish (multiple sources, variable delays)
    # Polling adapts intervals: 30s (0-30min), 5min (30min-2h), 15min (2h+)
    # Daily Full Sync at 6 AM ET is absolute safety net
    current_et = DateManager.get_current_et_time()
    timeout_seconds = 6 * 3600  # 6 hours = 21600 seconds
    timeout_timestamp = start_time.timestamp() + timeout_seconds
    timeout_et = current_et.replace(hour=(current_et.hour + 6) % 24)
    
    logger.info("=" * 80)
    logger.info(f"🚀 [unified_polling] STARTING UNIFIED ADAPTIVE POLLING")
    logger.info(f"🚀 [unified_polling] Target draw date: {expected_draw_date}")
    logger.info(f"🚀 [unified_polling] Started at: {current_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info(f"🚀 [unified_polling] Timeout at: {timeout_et.strftime('%Y-%m-%d %H:%M:%S %Z')} (6 hours)")
    logger.info(f"🚀 [unified_polling] Adaptive intervals: 30s (0-30min) → 5min (30min-2h) → 15min (2h+)")
    logger.info("=" * 80)
    
    # ========== PRE-CHECK: HEALTH CHECK ALL SOURCES ==========
    logger.info(f"🏥 [unified_polling] Running pre-check health test...")
    healthy_sources = quick_health_check_sources()
    
    # Abort if ALL sources are down
    if not any(healthy_sources.values()):
        logger.error("=" * 80)
        logger.error(f"🚨 [unified_polling] CRITICAL: ALL DATA SOURCES UNAVAILABLE!")
        logger.error(f"🚨 [unified_polling] Cannot proceed with polling - check connectivity")
        logger.error("=" * 80)
        return {
            'success': False,
            'draw_data': None,
            'source': None,
            'attempts': 0,
            'elapsed_seconds': 0,
            'result': 'all_sources_down'
        }
    
    # Build active sources list based on health check
    active_sources = []
    if healthy_sources['web_scraping']:
        active_sources.append(('NC Lottery Scraping', 'web_scraping', scrape_powerball_website))
    if healthy_sources['musl_api']:
        active_sources.append(('MUSL API', 'musl_api', fetch_single_draw_musl))
    if healthy_sources['nclottery_csv']:
        active_sources.append(('NC CSV', 'nclottery_csv', fetch_single_draw_nclottery_csv))
    
    logger.info(f"🚀 [unified_polling] Strategy: {' → '.join([s[0] for s in active_sources])} ({len(active_sources)}/{3} sources active)")
    logger.info(f"🚀 [unified_polling] Intervals: 30s (0-30min) → 5min (30min-2h) → 15min (2h+)")
    logger.info("=" * 80)
    
    while True:
        attempts += 1
        elapsed_seconds = (datetime.now() - start_time).total_seconds()
        elapsed_minutes = elapsed_seconds / 60
        
        # Check timeout BEFORE attempting
        if datetime.now().timestamp() >= timeout_timestamp:
            logger.warning("=" * 80)
            logger.warning(f"⏱ [unified_polling] TIMEOUT REACHED after 6 hours")
            logger.warning(f"⏱ [unified_polling] Total attempts: {attempts}")
            logger.warning(f"⏱ [unified_polling] Elapsed time: {elapsed_minutes:.1f} minutes")
            logger.warning(f"⏱ [unified_polling] Draw still not available from any source - daily sync will catch it at 6 AM")
            logger.warning("=" * 80)
            return {
                'success': False,
                'draw_data': None,
                'source': None,
                'attempts': attempts,
                'elapsed_seconds': elapsed_seconds,
                'result': 'timeout'
            }
        
        # Determine interval based on elapsed time (adaptive)
        # Phase 1 (0-30 min): Check every 30 seconds (frequent during ceremony)
        # Phase 2 (30 min-2 hours): Check every 5 minutes (less frequent)
        # Phase 3 (2+ hours): Check every 15 minutes (very spacious)
        if elapsed_minutes < 30:
            interval_seconds = 30   # 30 seconds
            phase = "Phase 1 (0-30min): frequent polling"
        elif elapsed_minutes < 120:
            interval_seconds = 300  # 5 minutes
            phase = "Phase 2 (30min-2h): normal polling"
        else:
            interval_seconds = 900  # 15 minutes
            phase = "Phase 3 (2h+): sparse polling"
        
        logger.info("-" * 80)
        logger.info(
            f"🔄 [unified_polling] Attempt #{attempts} at {datetime.now().strftime('%H:%M:%S')} "
            f"({elapsed_minutes:.1f}min elapsed, {phase})"
        )
        logger.info("-" * 80)
        
        # TRY ONLY HEALTHY SOURCES (determined by pre-check)
        for idx, (source_name, source_key, source_func) in enumerate(active_sources, 1):
            try:
                logger.info(f"   Layer {idx}/{len(active_sources)}: Trying {source_name}...")
                result = source_func(expected_draw_date)
                if result:
                    logger.info("=" * 80)
                    logger.info(f"✅ [unified_polling] SUCCESS via {source_name.upper()}!")
                    logger.info(f"✅ [unified_polling] Draw: [{result['n1']}, {result['n2']}, {result['n3']}, {result['n4']}, {result['n5']}] + PB {result['pb']}")
                    logger.info(f"✅ [unified_polling] Attempts: {attempts}, Elapsed: {elapsed_minutes:.1f} minutes")
                    logger.info("=" * 80)
                    return {
                        'success': True,
                        'draw_data': result,
                        'source': source_key,
                        'attempts': attempts,
                        'elapsed_seconds': elapsed_seconds,
                        'result': 'success'
                    }
            except Exception as e:
                logger.error(f"   Layer {idx}/{len(active_sources)}: {source_name} failed with exception: {e}")
        
        # All active sources failed - wait and retry
        next_attempt_time = datetime.now().timestamp() + interval_seconds
        if next_attempt_time > timeout_timestamp:
            remaining_sleep = timeout_timestamp - datetime.now().timestamp()
            if remaining_sleep > 0:
                logger.info(f"   ⏸ No data from any source. Sleeping {remaining_sleep:.0f}s (until timeout)...")
                time.sleep(remaining_sleep)
            else:
                logger.info(f"   ⏸ Timeout reached, exiting polling loop")
                break
        else:
            logger.info(f"   ⏸ No data from any source. Sleeping {interval_seconds}s before retry (Attempt #{attempts+1})...")
            time.sleep(interval_seconds)


def daily_full_sync_job() -> Dict:
    """
    DAILY FULL SYNC JOB - Runs at 6:00 AM ET every day.
    
    Safety net that ensures database completeness by:
    1. Downloading complete historical CSV from NC Lottery (2,250+ draws)
    2. Comparing with database to find gaps
    3. Inserting all missing draws
    4. Logging results
    
    This catches any draws missed by real-time polling due to:
    - Network outages
    - API failures
    - Service downtime
    - Timeout scenarios
    
    Advantages of NC Lottery CSV:
    - Comprehensive historical data (2006-present, 2,250+ draws)
    - Complete history: 2006-present (2,250+ draws)
    - No 1-2 day delay
    - No rate limits
    - Single HTTP request (faster)
    - No API key required
    
    Returns:
        Dict with sync results:
        {
            'success': bool,
            'draws_fetched': int,
            'draws_inserted': int,
            'latest_date': str,
            'execution_time': float
        }
    
    Example:
        >>> result = daily_full_sync_job()
        >>> print(f"Synced {result['draws_inserted']} missing draws")
    """
    from datetime import datetime
    from src.date_utils import DateManager
    import time
    
    start_time = time.time()
    current_et = DateManager.get_current_et_time()
    
    logger.info("=" * 80)
    logger.info(f"🔄 [daily_sync] STARTING DAILY FULL SYNC")
    logger.info(f"🔄 [daily_sync] Execution time: {current_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info(f"🔄 [daily_sync] Source: NC Lottery CSV (complete historical data)")
    logger.info("=" * 80)
    
    try:
        # Step 1: Get latest draw date from database
        latest_db_date = get_latest_draw_date()
        logger.info(f"🔄 [daily_sync] Latest draw in database: {latest_db_date or 'EMPTY'}")
        
        # Step 2: Download and parse NC Lottery CSV
        logger.info(f"🔄 [daily_sync] Downloading NC Lottery CSV...")
        
        csv_url = "https://nclottery.com/powerball-download"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(csv_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Parse CSV
        from io import StringIO
        csv_content = StringIO(response.text)
        df = pd.read_csv(csv_content)
        
        # Filter to main draws only (exclude DoubleDraw and disclaimer row)
        main_draws = df[df['SubName'].isna()].copy()
        main_draws = main_draws[main_draws['Ball 1'].notna()].copy()
        
        # Parse dates
        main_draws['parsed_date'] = pd.to_datetime(main_draws['Date'], format='%m/%d/%Y')
        main_draws['date_str'] = main_draws['parsed_date'].dt.strftime('%Y-%m-%d')
        
        logger.info(f"🔄 [daily_sync] ✅ Downloaded CSV with {len(main_draws)} total draws")
        logger.info(f"🔄 [daily_sync]    Date range: {main_draws['date_str'].min()} to {main_draws['date_str'].max()}")
        
        # Step 3: Get last 30 draws for comparison (or all if database is empty)
        if latest_db_date:
            # Only process draws from last 60 days (safety margin)
            from datetime import timedelta
            cutoff_date = pd.to_datetime(latest_db_date) - timedelta(days=60)
            recent_draws = main_draws[main_draws['parsed_date'] >= cutoff_date].copy()
            logger.info(f"🔄 [daily_sync] Processing {len(recent_draws)} recent draws (last 60 days)")
        else:
            # Database empty - process all historical draws
            recent_draws = main_draws.copy()
            logger.info(f"🔄 [daily_sync] Database empty - processing ALL {len(recent_draws)} historical draws")
        
        # Step 4: Parse draws into database format
        parsed_draws = []
        for _, row in recent_draws.iterrows():
            try:
                # Sort white balls
                white_balls = sorted([
                    int(row['Ball 1']),
                    int(row['Ball 2']),
                    int(row['Ball 3']),
                    int(row['Ball 4']),
                    int(row['Ball 5'])
                ])
                
                parsed_draws.append({
                    'draw_date': row['date_str'],
                    'n1': white_balls[0],
                    'n2': white_balls[1],
                    'n3': white_balls[2],
                    'n4': white_balls[3],
                    'n5': white_balls[4],
                    'pb': int(row['Powerball'])
                })
            except Exception as e:
                logger.warning(f"🔄 [daily_sync] Failed to parse draw {row.get('Date', 'unknown')}: {e}")
                continue
        
        logger.info(f"🔄 [daily_sync] Successfully parsed {len(parsed_draws)} draws")
        
        # Step 5: Get existing draw dates from database to detect gaps
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT draw_date FROM powerball_draws")
            existing_dates = {row[0] for row in cursor.fetchall()}
        
        # Step 6: Find missing draws (in CSV but not in DB)
        missing_draws = []
        for draw in parsed_draws:
            if draw['draw_date'] not in existing_dates:
                missing_draws.append(draw)
        
        if missing_draws:
            logger.info(f"🔄 [daily_sync] Found {len(missing_draws)} missing draws:")
            for draw in missing_draws[:10]:  # Show first 10
                logger.info(
                    f"   📅 {draw['draw_date']}: "
                    f"[{draw['n1']}, {draw['n2']}, {draw['n3']}, {draw['n4']}, {draw['n5']}] + PB {draw['pb']}"
                )
            if len(missing_draws) > 10:
                logger.info(f"   ... and {len(missing_draws) - 10} more")
            
            # Step 7: Insert missing draws (convert to DataFrame first)
            missing_df = pd.DataFrame(missing_draws)
            inserted = bulk_insert_draws(missing_df)
            
            logger.info("=" * 80)
            logger.info(f"✅ [daily_sync] SYNC COMPLETE!")
            logger.info(f"✅ [daily_sync] Total draws in CSV: {len(main_draws)}")
            logger.info(f"✅ [daily_sync] Draws processed: {len(parsed_draws)}")
            logger.info(f"✅ [daily_sync] Draws inserted: {inserted}")
            logger.info(f"✅ [daily_sync] Latest draw: {parsed_draws[0]['draw_date']}")
            logger.info(f"✅ [daily_sync] Execution time: {time.time() - start_time:.2f}s")
            logger.info("=" * 80)
        else:
            logger.info("=" * 80)
            logger.info(f"✅ [daily_sync] DATABASE IS COMPLETE - No missing draws found")
            logger.info(f"✅ [daily_sync] Latest draw: {parsed_draws[0]['draw_date']}")
            logger.info(f"✅ [daily_sync] Execution time: {time.time() - start_time:.2f}s")
            logger.info("=" * 80)
        
        return {
            'success': True,
            'draws_fetched': len(parsed_draws),
            'draws_inserted': len(missing_draws) if missing_draws else 0,
            'latest_date': parsed_draws[0]['draw_date'] if parsed_draws else None,
            'execution_time': time.time() - start_time
        }
        
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error("=" * 80)
        logger.error(f"❌ [daily_sync] SYNC FAILED!")
        logger.error(f"❌ [daily_sync] Error: {e}")
        logger.error(f"❌ [daily_sync] Execution time: {elapsed:.2f}s")
        logger.error("=" * 80)
        logger.error(f"Full traceback:", exc_info=True)
        
        return {
            'success': False,
            'draws_fetched': 0,
            'draws_inserted': 0,
            'latest_date': latest_db_date if 'latest_db_date' in locals() else None,
            'execution_time': elapsed,
            'error': str(e)
        }
