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
            logger.warning("🌐 [web_scraping] Could not find drawdate span with ID")
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
            logger.warning("🌐 [web_scraping] Could not find powerball element")
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


def scrape_powerball_official(expected_draw_date: str) -> Optional[Dict]:
    """Scrape the official Powerball site for the winning numbers."""
    try:
        from bs4 import BeautifulSoup
        logger.info(f"🌐 [powerball_official] Scraping powerball.com for date {expected_draw_date}")

        url = "https://www.powerball.com/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        card = soup.find('div', class_='card h-100 number-card number-powerball complete')
        if not card:
            logger.info("🌐 [powerball_official] Draw card not yet marked complete")
            return None

        date_elem = card.find('h5', class_='title-date')
        if not date_elem:
            logger.warning("🌐 [powerball_official] Unable to locate draw date element")
            return None

        draw_date_text = date_elem.get_text(strip=True)
        try:
            parsed_date = pd.to_datetime(draw_date_text, format='%a, %b %d, %Y')
        except Exception:
            parsed_date = pd.to_datetime(draw_date_text, errors='coerce')
        if parsed_date is pd.NaT:
            logger.warning(f"🌐 [powerball_official] Cannot parse draw date '{draw_date_text}'")
            return None

        normalized_date = parsed_date.strftime('%Y-%m-%d')
        if normalized_date != expected_draw_date:
            logger.info(f"🌐 [powerball_official] Draw for {normalized_date} found, expected {expected_draw_date}")
            return None

        white_ball_elements = card.select('div.form-control.col.white-balls.item-powerball')
        if len(white_ball_elements) != 5:
            logger.warning(f"🌐 [powerball_official] Found {len(white_ball_elements)} white balls")
            return None

        white_balls = [int(el.get_text(strip=True)) for el in white_ball_elements]
        powerball_elem = card.select_one('div.form-control.col.powerball.item-powerball')
        if not powerball_elem:
            logger.warning("🌐 [powerball_official] Missing powerball value")
            return None
        powerball = int(powerball_elem.get_text(strip=True))

        multiplier_elem = card.select_one('span.multiplier')
        multiplier = int(multiplier_elem.get_text(strip=True).replace('x', '')) if multiplier_elem else 1

        result = {
            'draw_date': expected_draw_date,
            'n1': white_balls[0],
            'n2': white_balls[1],
            'n3': white_balls[2],
            'n4': white_balls[3],
            'n5': white_balls[4],
            'pb': powerball,
            'multiplier': multiplier,
            'source': 'powerball_official'
        }

        logger.info(f"🌐 [powerball_official] ✅ Found draw {normalized_date}: [{', '.join(map(str, white_balls))}] + PB {powerball} (x{multiplier})")
        return result
    except requests.exceptions.RequestException as e:
        logger.warning(f"🌐 [powerball_official] Network error: {e}")
        return None
    except Exception as e:
        logger.error(f"🌐 [powerball_official] Unexpected error: {e}", exc_info=True)
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
            logger.warning("🎯 [musl_api] Invalid response structure")
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
            logger.warning("🎯 [musl_api] No numbers array in response")
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
            'powerball_official': bool,
            'web_scraping': bool,
            'musl_api': bool
        }

    Example:
        >>> health = quick_health_check_sources()
        >>> print(health)
        {'powerball_official': True, 'web_scraping': True, 'musl_api': False}
    """
    import requests

    health_status = {
        'powerball_official': False,
        'web_scraping': False,
        'musl_api': False
    }

    logger.info("🏥 [health_check] Running quick health check on all sources (5s timeout)...")

    # Test 1: Powerball Official website
    try:
        url = "https://www.powerball.com/"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if response.status_code == 200 and 'number-powerball' in response.text:
            health_status['powerball_official'] = True
            logger.info(f"   ✅ Powerball Official: HEALTHY ({response.status_code})")
        else:
            logger.warning(f"   ⚠️  Powerball Official: DEGRADED (status {response.status_code})")
    except Exception as e:
        logger.warning(f"   ❌ Powerball Official: UNAVAILABLE ({str(e)[:50]})")

    # Test 2: NC Lottery Web Scraping
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

    # Test 3: MUSL API
    try:
        api_key = os.getenv("MUSL_API_KEY")
        if not api_key:
            logger.info("   ⚠️  MUSL API: SKIPPED (no API key configured)")
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

    healthy_count = sum(health_status.values())
    logger.info(f"🏥 [health_check] Complete: {healthy_count}/3 sources healthy")
    logger.info(f"🏥 [health_check] Active sources: {[k for k, v in health_status.items() if v]}")

    return health_status


def realtime_draw_polling_unified(expected_draw_date: str, execution_id: str = None, update_status_callback=None) -> Dict:
    """
    UNIFIED ADAPTIVE POLLING across all 3 data sources.

    Strategy:
    - Single loop tries ALL 3 sources each iteration (Powerball → NC Scraping → MUSL)
    - Adaptive intervals: 30s (first 30min) → 5min (next 90min) → 15min (after 2h)
    - Timeout at 6 hours (Daily Full Sync takes over at 6 AM)
    - First source that responds wins

    Args:
        expected_draw_date: Draw date to poll for (YYYY-MM-DD format)
        execution_id: Pipeline execution ID (optional, for status logging)
        update_status_callback: Callback function to update pipeline status (optional)
            Signature: update_status_callback(execution_id, current_step, metadata)

    Returns:
        Dict with polling results:
        {
            'success': bool,
            'draw_data': Dict or None,
            'source': str (powerball_official|web_scraping|musl_api),
            'attempts': int,
            'elapsed_seconds': float,
            'result': str (success|timeout|error)
        }

    Example Timeline (Monday 11:05 PM draw):
        23:05:00 → Attempt #1 (Powerball→NC→MUSL): None (interval: 30s)
        23:05:30 → Attempt #2 (Powerball→NC→MUSL): None (interval: 30s)
        23:06:00 → Attempt #3 (Powerball→NC→MUSL): ✅ Powerball Official SUCCESS!
        Result: {'success': True, 'source': 'powerball_official', 'attempts': 3, 'elapsed': 60s}
    """
    from datetime import datetime, timedelta
    from src.date_utils import DateManager
    import time

    start_time = datetime.now()

    # SIMPLE POLLING CONFIGURATION
    # Strategy: Short polling window + scheduler retries
    # - 4 attempts × 30s = 120s = 2 minutes maximum
    # - CRITICAL: Must be < systemd timeout (180s) to avoid SIGKILL
    # - If draw not available, exit gracefully → scheduler retries in 5 min
    # - Daily Full Sync at 6 AM as final safety net
    max_attempts = 4  # Maximum polling attempts (2 min total)
    interval_seconds = 30  # Fixed interval between attempts
    max_duration_minutes = (max_attempts * interval_seconds) / 60

    current_et = DateManager.get_current_et_time()

    logger.info("=" * 80)
    logger.info("🚀 [unified_polling] STARTING SIMPLE ROBUST POLLING")
    logger.info(f"🚀 [unified_polling] Target draw date: {expected_draw_date}")
    logger.info(f"🚀 [unified_polling] Started at: {current_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info(f"🚀 [unified_polling] Max attempts: {max_attempts} (~{max_duration_minutes:.0f} minutes max)")
    logger.info(f"🚀 [unified_polling] Interval: {interval_seconds}s between attempts")
    logger.info("🚀 [unified_polling] Strategy: Simple polling with scheduler retries until draw found")
    logger.info("=" * 80)

    # ========== PRE-CHECK: HEALTH CHECK ALL SOURCES ==========
    logger.info("🏥 [unified_polling] Running pre-check health test...")
    healthy_sources = quick_health_check_sources()

    # Abort if ALL sources are down
    if not any(healthy_sources.values()):
        logger.error("=" * 80)
        logger.error("🚨 [unified_polling] CRITICAL: ALL DATA SOURCES UNAVAILABLE!")
        logger.error("🚨 [unified_polling] Cannot proceed with polling - check connectivity")
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
    if healthy_sources['powerball_official']:
        active_sources.append(('Powerball Official', 'powerball_official', scrape_powerball_official))
    if healthy_sources['web_scraping']:
        active_sources.append(('NC Lottery Scraping', 'web_scraping', scrape_powerball_website))
    if healthy_sources['musl_api']:
        active_sources.append(('MUSL API', 'musl_api', fetch_single_draw_musl))

    logger.info(f"🚀 [unified_polling] Strategy: {' → '.join([s[0] for s in active_sources])} ({len(active_sources)}/{3} sources active)")
    logger.info("=" * 80)

    # SIMPLE POLLING LOOP: Try up to max_attempts
    for attempt in range(1, max_attempts + 1):
        elapsed_seconds = (datetime.now() - start_time).total_seconds()
        elapsed_minutes = elapsed_seconds / 60

        logger.info("-" * 80)
        logger.info(
            f"🔄 [unified_polling] Attempt {attempt}/{max_attempts} at {datetime.now().strftime('%H:%M:%S')} "
            f"({elapsed_minutes:.1f} min elapsed)"
        )
        logger.info("-" * 80)

        # Update pipeline status with current attempt
        if execution_id and update_status_callback:
            status_msg = f"STEP 1C/7: Polling draw (Attempt {attempt}/{max_attempts}, {elapsed_minutes:.1f}min)"
            try:
                update_status_callback(execution_id, status_msg)
            except Exception as e:
                logger.warning(f"Failed to update pipeline status: {e}")

        # TRY ONLY HEALTHY SOURCES (determined by pre-check)
        for idx, (source_name, source_key, source_func) in enumerate(active_sources, 1):
            try:
                logger.info(f"   Layer {idx}/{len(active_sources)}: Trying {source_name}...")
                result = source_func(expected_draw_date)
                if result:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    logger.info("=" * 80)
                    logger.info(f"✅ [unified_polling] SUCCESS via {source_name.upper()}!")
                    logger.info(f"✅ [unified_polling] Draw: [{result['n1']}, {result['n2']}, {result['n3']}, {result['n4']}, {result['n5']}] + PB {result['pb']}")
                    logger.info(f"✅ [unified_polling] Found after {attempt} attempts in {elapsed/60:.1f} minutes")
                    logger.info("=" * 80)
                    return {
                        'success': True,
                        'draw_data': result,
                        'source': source_key,
                        'attempts': attempt,
                        'elapsed_seconds': elapsed,
                        'result': 'success'
                    }
            except Exception as e:
                logger.warning(f"   {source_name} error: {str(e)[:80]}")

        # All sources failed this attempt - wait before next attempt
        if attempt < max_attempts:  # Don't sleep after last attempt
            logger.info(f"   ⏸ Draw not available yet. Waiting {interval_seconds}s before attempt {attempt + 1}...")
            time.sleep(interval_seconds)

    # Reached max_attempts without finding draw
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.warning("=" * 80)
    logger.warning(f"⏱ [unified_polling] MAX ATTEMPTS REACHED ({max_attempts})")
    logger.warning(f"⏱ [unified_polling] Elapsed time: {elapsed/60:.1f} minutes")
    logger.warning(f"⏱ [unified_polling] Draw {expected_draw_date} not available yet")
    logger.warning(f"⏱ [unified_polling] Scheduler will retry in 5 minutes")
    logger.warning(f"⏱ [unified_polling] Daily sync at 6 AM will ensure data completeness")
    logger.warning("=" * 80)

    return {
        'success': False,
        'draw_data': None,
        'source': None,
        'attempts': max_attempts,
        'elapsed_seconds': elapsed,
        'result': 'max_attempts_reached'
    }


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
    logger.info("🔄 [daily_sync] STARTING DAILY FULL SYNC")
    logger.info(f"🔄 [daily_sync] Execution time: {current_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info("🔄 [daily_sync] Source: NC Lottery CSV (complete historical data)")
    logger.info("=" * 80)

    try:
        # Step 1: Get latest draw date from database
        latest_db_date = get_latest_draw_date()
        logger.info(f"🔄 [daily_sync] Latest draw in database: {latest_db_date or 'EMPTY'}")

        # Step 2: Download and parse NC Lottery CSV
        logger.info("🔄 [daily_sync] Downloading NC Lottery CSV...")

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
            logger.info("✅ [daily_sync] SYNC COMPLETE!")
            logger.info(f"✅ [daily_sync] Total draws in CSV: {len(main_draws)}")
            logger.info(f"✅ [daily_sync] Draws processed: {len(parsed_draws)}")
            logger.info(f"✅ [daily_sync] Draws inserted: {inserted}")
            logger.info(f"✅ [daily_sync] Latest draw: {parsed_draws[0]['draw_date']}")
            logger.info(f"✅ [daily_sync] Execution time: {time.time() - start_time:.2f}s")
            logger.info("=" * 80)
        else:
            logger.info("=" * 80)
            logger.info("✅ [daily_sync] DATABASE IS COMPLETE - No missing draws found")
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
        logger.error("❌ [daily_sync] SYNC FAILED!")
        logger.error(f"❌ [daily_sync] Error: {e}")
        logger.error(f"❌ [daily_sync] Execution time: {elapsed:.2f}s")
        logger.error("=" * 80)
        logger.error("Full traceback:", exc_info=True)

        return {
            'success': False,
            'draws_fetched': 0,
            'draws_inserted': 0,
            'latest_date': latest_db_date if 'latest_db_date' in locals() else None,
            'execution_time': elapsed,
            'error': str(e)
        }


# ============================================================================
# PIPELINE v6.1 - 3 LAYER POLLING FUNCTIONS
# ============================================================================

def poll_draw_layer1(expected_draw_date: str, max_attempts: int = 10, interval_seconds: int = 60) -> Dict:
    """
    LAYER 1 POLLING: Primary post-draw polling using ONLY powerball.com.

    This is the fastest, most direct source. Runs immediately after draw time (11:15 PM ET).

    Strategy:
    - Single source: powerball.com only (fastest updates)
    - 10 attempts × 60s = 10 minutes maximum
    - If fails, draw is marked as pending for Layer 2

    Args:
        expected_draw_date: Draw date to poll for (YYYY-MM-DD format)
        max_attempts: Maximum polling attempts (default 10)
        interval_seconds: Seconds between attempts (default 60)

    Returns:
        Dict with polling results:
        {
            'success': bool,
            'draw_data': Dict or None,
            'source': 'powerball_official' or None,
            'attempts': int,
            'elapsed_seconds': float,
            'result': 'success' | 'max_attempts_reached'
        }
    """
    import time
    from datetime import datetime
    from src.date_utils import DateManager

    start_time = datetime.now()
    current_et = DateManager.get_current_et_time()

    logger.info("=" * 80)
    logger.info("🔵 [LAYER 1] STARTING PRIMARY POLLING - powerball.com ONLY")
    logger.info(f"🔵 [LAYER 1] Target draw date: {expected_draw_date}")
    logger.info(f"🔵 [LAYER 1] Started at: {current_et.strftime('%Y-%m-%d %H:%M:%S ET')}")
    logger.info(f"🔵 [LAYER 1] Max attempts: {max_attempts} ({max_attempts * interval_seconds / 60:.0f} min max)")
    logger.info("=" * 80)

    for attempt in range(1, max_attempts + 1):
        elapsed_seconds = (datetime.now() - start_time).total_seconds()

        logger.info(f"🔵 [LAYER 1] Attempt {attempt}/{max_attempts} ({elapsed_seconds/60:.1f} min elapsed)")

        try:
            result = scrape_powerball_official(expected_draw_date)
            if result:
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.info("=" * 80)
                logger.info(f"✅ [LAYER 1] SUCCESS! Draw found via powerball.com")
                logger.info(f"✅ [LAYER 1] Numbers: [{result['n1']}, {result['n2']}, {result['n3']}, {result['n4']}, {result['n5']}] + PB {result['pb']}")
                logger.info(f"✅ [LAYER 1] Found after {attempt} attempts in {elapsed/60:.1f} minutes")
                logger.info("=" * 80)

                return {
                    'success': True,
                    'draw_data': result,
                    'source': 'powerball_official',
                    'attempts': attempt,
                    'elapsed_seconds': elapsed,
                    'result': 'success'
                }
        except Exception as e:
            logger.warning(f"🔵 [LAYER 1] Error on attempt {attempt}: {str(e)[:80]}")

        # Wait before next attempt (except after last attempt)
        if attempt < max_attempts:
            logger.info(f"🔵 [LAYER 1] Waiting {interval_seconds}s before next attempt...")
            time.sleep(interval_seconds)

    # Max attempts reached
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.warning("=" * 80)
    logger.warning(f"⚠️ [LAYER 1] MAX ATTEMPTS REACHED ({max_attempts})")
    logger.warning(f"⚠️ [LAYER 1] Draw {expected_draw_date} not found on powerball.com")
    logger.warning(f"⚠️ [LAYER 1] Elapsed: {elapsed/60:.1f} minutes")
    logger.warning(f"⚠️ [LAYER 1] Draw will be marked as PENDING for Layer 2 retry")
    logger.warning("=" * 80)

    return {
        'success': False,
        'draw_data': None,
        'source': None,
        'attempts': max_attempts,
        'elapsed_seconds': elapsed,
        'result': 'max_attempts_reached'
    }


def poll_draw_layer2(expected_draw_date: str) -> Dict:
    """
    LAYER 2 POLLING: Multi-source retry for pending draws.

    Runs every 15 minutes after Layer 1 fails. Tries all sources in order.

    Strategy:
    - Try sources in order: powerball.com → MUSL API → NC Lottery CSV
    - Single attempt per source (fast check)
    - Called repeatedly by scheduler until success or Layer 3

    Args:
        expected_draw_date: Draw date to poll for (YYYY-MM-DD format)

    Returns:
        Dict with polling results:
        {
            'success': bool,
            'draw_data': Dict or None,
            'source': str or None,
            'result': 'success' | 'not_available'
        }
    """
    from datetime import datetime

    logger.info("-" * 60)
    logger.info(f"🟡 [LAYER 2] Retry polling for {expected_draw_date}")
    logger.info("-" * 60)

    # Define sources in priority order
    sources = [
        ('powerball_official', scrape_powerball_official),
        ('musl_api', fetch_single_draw_musl),
        ('nc_lottery_csv', fetch_single_draw_nclottery_csv),
    ]

    for source_name, source_func in sources:
        try:
            logger.info(f"🟡 [LAYER 2] Trying {source_name}...")
            result = source_func(expected_draw_date)

            if result:
                logger.info(f"✅ [LAYER 2] SUCCESS via {source_name}!")
                logger.info(f"✅ [LAYER 2] Numbers: [{result['n1']}, {result['n2']}, {result['n3']}, {result['n4']}, {result['n5']}] + PB {result['pb']}")

                return {
                    'success': True,
                    'draw_data': result,
                    'source': source_name,
                    'result': 'success'
                }
        except Exception as e:
            logger.warning(f"🟡 [LAYER 2] {source_name} error: {str(e)[:60]}")

    logger.info(f"🟡 [LAYER 2] Draw {expected_draw_date} not available yet on any source")

    return {
        'success': False,
        'draw_data': None,
        'source': None,
        'result': 'not_available'
    }


def poll_draw_layer3(expected_draw_date: str, max_retries_per_source: int = 3) -> Dict:
    """
    LAYER 3 POLLING: Emergency recovery with maximum effort.

    Runs at 6:00 AM ET for any draws still pending. Uses all sources with retries.

    Strategy:
    - Try ALL sources with multiple retries each
    - Last chance before marking as failed_permanent
    - Maximum effort to recover the draw

    Args:
        expected_draw_date: Draw date to poll for (YYYY-MM-DD format)
        max_retries_per_source: Retries per source (default 3)

    Returns:
        Dict with polling results:
        {
            'success': bool,
            'draw_data': Dict or None,
            'source': str or None,
            'total_attempts': int,
            'result': 'success' | 'all_sources_failed'
        }
    """
    import time
    from datetime import datetime

    logger.info("=" * 80)
    logger.info(f"🔴 [LAYER 3] EMERGENCY RECOVERY for {expected_draw_date}")
    logger.info(f"🔴 [LAYER 3] Maximum effort: {max_retries_per_source} retries per source")
    logger.info("=" * 80)

    sources = [
        ('powerball_official', scrape_powerball_official),
        ('musl_api', fetch_single_draw_musl),
        ('nc_lottery_csv', fetch_single_draw_nclottery_csv),
    ]

    total_attempts = 0

    for source_name, source_func in sources:
        logger.info(f"🔴 [LAYER 3] Trying {source_name} ({max_retries_per_source} attempts)...")

        for retry in range(1, max_retries_per_source + 1):
            total_attempts += 1

            try:
                result = source_func(expected_draw_date)

                if result:
                    logger.info("=" * 80)
                    logger.info(f"✅ [LAYER 3] RECOVERED via {source_name}!")
                    logger.info(f"✅ [LAYER 3] Numbers: [{result['n1']}, {result['n2']}, {result['n3']}, {result['n4']}, {result['n5']}] + PB {result['pb']}")
                    logger.info(f"✅ [LAYER 3] Total attempts: {total_attempts}")
                    logger.info("=" * 80)

                    return {
                        'success': True,
                        'draw_data': result,
                        'source': source_name,
                        'total_attempts': total_attempts,
                        'result': 'success'
                    }

            except Exception as e:
                logger.warning(f"🔴 [LAYER 3] {source_name} attempt {retry} error: {str(e)[:60]}")

            # Small delay between retries
            if retry < max_retries_per_source:
                time.sleep(5)

    # All sources failed
    logger.error("=" * 80)
    logger.error(f"❌ [LAYER 3] ALL SOURCES FAILED for {expected_draw_date}")
    logger.error(f"❌ [LAYER 3] Total attempts: {total_attempts}")
    logger.error(f"❌ [LAYER 3] Draw will be marked as FAILED_PERMANENT")
    logger.error("=" * 80)

    return {
        'success': False,
        'draw_data': None,
        'source': None,
        'total_attempts': total_attempts,
        'result': 'all_sources_failed'
    }
