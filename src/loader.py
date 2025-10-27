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


def _is_database_stale(latest_date_str: Optional[str], staleness_threshold_days: int = 1) -> bool:
    """
    Determines if the database is stale based on the latest draw date.
    
    Args:
        latest_date_str: Latest draw date from DB (None if empty)
        staleness_threshold_days: Days to consider data stale (default: 1)
        
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


def update_database_from_source() -> int:
    """
    Fetches the latest Powerball data from official APIs with smart source selection,
    compares with existing database, and inserts only new draws.
    Initializes the database if empty.

    Data Source Strategy:
    - EMPTY DB: NY State API (bulk historical) → fallback MUSL
    - STALE DB (>1 day): NY State API (full refresh) → fallback MUSL
    - CURRENT DB: MUSL (incremental) → fallback NY State

    Both sources available for recovery if primary fails.

    Returns:
        int: Total number of draws in database after update.
    """
    logger.info("=" * 60)
    logger.info("Starting intelligent data update process...")
    logger.info("=" * 60)

    initialize_database()

    # Phase 1: Analyze database state
    latest_date_in_db = get_latest_draw_date()
    is_stale = _is_database_stale(latest_date_in_db, staleness_threshold_days=1)

    db_state = "EMPTY" if latest_date_in_db is None else ("STALE" if is_stale else "CURRENT")
    logger.info(f"📊 Database State: {db_state}")

    if latest_date_in_db:
        logger.info(f"   Latest draw date: {latest_date_in_db}")

    # Phase 2: Smart source selection
    fetched_data = None

    if db_state in ["EMPTY", "STALE"]:
        # Use NY State for bulk operations (full history)
        logger.info("🔄 Strategy: NY State API (bulk historical data)")
        logger.info("   Reason: Database is empty or stale - need full refresh")

        fetched_data = _fetch_from_nystate_api()

        if fetched_data:
            logger.info(f"✅ NY State API success: {len(fetched_data)} draws fetched")
        else:
            logger.warning("⚠️  NY State API failed, falling back to MUSL...")
            fetched_data = _fetch_from_musl_api()

            if fetched_data:
                logger.info(f"✅ MUSL fallback success: {len(fetched_data)} draw(s) fetched")
            else:
                logger.error("❌ Both APIs failed - no data available")
                return len(get_all_draws())

    else:  # CURRENT state
        # Use MUSL for incremental updates (faster, single latest draw)
        logger.info("🔄 Strategy: MUSL API (incremental update)")
        logger.info("   Reason: Database is current - checking for new draws")

        fetched_data = _fetch_from_musl_api()

        if fetched_data:
            logger.info(f"✅ MUSL API success: {len(fetched_data)} draw(s) fetched")
        else:
            logger.warning("⚠️  MUSL API failed, falling back to NY State...")
            fetched_data = _fetch_from_nystate_api()

            if fetched_data:
                logger.info(f"✅ NY State fallback success: {len(fetched_data)} draws fetched")
            else:
                logger.error("❌ Both APIs failed - no data available")
                return len(get_all_draws())

    # Phase 3: Transform and insert
    transformed_df = _transform_api_data(fetched_data)

    if transformed_df is None or transformed_df.empty:
        logger.error("❌ Data transformation failed")
        return len(get_all_draws())

    logger.info(f"📊 Transformed {len(transformed_df)} valid draws")

    # Phase 4: Filter new draws
    if latest_date_in_db:
        transformed_df["draw_date"] = pd.to_datetime(transformed_df["draw_date"])
        latest_date_in_db_dt = pd.to_datetime(latest_date_in_db)
        new_draws_df = transformed_df[transformed_df["draw_date"] > latest_date_in_db_dt].copy()
        logger.info(f"🆕 New draws to add: {len(new_draws_df)}")
    else:
        new_draws_df = transformed_df.copy()
        logger.info(f"🆕 Populating empty DB with {len(new_draws_df)} draws")

    # Phase 5: Insert new draws
    if not new_draws_df.empty:
        final_draws_df = new_draws_df.copy()
        final_draws_df["draw_date"] = final_draws_df["draw_date"].dt.strftime("%Y-%m-%d")
        bulk_insert_draws(final_draws_df)

        # Update pb_era metadata (safety net)
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE powerball_draws
                SET 
                    pb_is_current = CASE WHEN pb BETWEEN 1 AND 26 THEN 1 ELSE 0 END,
                    pb_era = CASE
                        WHEN pb BETWEEN 1 AND 26 THEN '2015-now (1-26)'
                        WHEN pb BETWEEN 27 AND 35 THEN '2012-2015 (1-35)'
                        WHEN pb BETWEEN 36 AND 39 THEN '2009-2012 (1-39)'
                        WHEN pb BETWEEN 40 AND 42 THEN '1997-2009 (1-42)'
                        WHEN pb BETWEEN 43 AND 45 THEN '1992-1997 (1-45)'
                        ELSE 'other'
                    END
                WHERE pb_is_current = 0 AND pb_era = 'unknown'
            """)
            updated = cursor.rowcount
            conn.commit()
            if updated:
                logger.info(f"🔧 Updated pb_era metadata for {updated} draws")
        finally:
            try:
                conn.close()
            except Exception:
                pass
    else:
        logger.info("ℹ️  No new draws to insert - database already up to date")

    # Phase 6: Final summary
    final_df = get_all_draws()
    total_draws = len(final_df)

    logger.info("=" * 60)
    logger.info(f"✅ Data update complete: {total_draws} total draws in database")
    logger.info("=" * 60)

    return total_draws


def _transform_api_data(api_data: List[Dict]) -> Optional[pd.DataFrame]:
    """
    Transforms API response data into standardized DataFrame format.
    Handles both Powerball.com and NY State API response formats.
    
    Args:
        api_data: List of dictionaries from API response
        
    Returns:
        pd.DataFrame: Standardized DataFrame with columns [draw_date, n1, n2, n3, n4, n5, pb]
    """
    try:
        if not api_data:
            return None

        records = []

        for item in api_data:
            try:
                record = _parse_draw_record(item)
                if record:
                    records.append(record)
            except Exception as e:
                logger.warning(f"Skipping invalid record: {e}")
                continue

        if not records:
            logger.error("No valid records found in API data")
            return None

        df = pd.DataFrame(records)
        df["draw_date"] = pd.to_datetime(df["draw_date"])
        df.sort_values(by="draw_date", ascending=True, inplace=True)
        df.drop_duplicates(subset=["draw_date"], inplace=True)

        logger.info(f"Transformation complete. {len(df)} valid draws processed.")
        return df

    except Exception as e:
        logger.error(f"Error transforming API data: {e}")
        return None


def _parse_draw_record(item: Dict) -> Optional[Dict]:
    """
    Parses a single draw record from API response (handles MUSL and NY State formats).
    
    Args:
        item: Dictionary containing draw data
        
    Returns:
        Dict with standardized keys, or None if parsing fails
    """
    if "numbers" in item and isinstance(item.get("numbers"), list):
        return _parse_musl_format(item)
    elif "winning_numbers" in item:
        return _parse_nystate_format(item)
    else:
        logger.warning(f"Unknown API format: {list(item.keys())}")
        return None


def _parse_nystate_format(item: Dict) -> Optional[Dict]:
    """
    Parses NY State Open Data API format.
    
    Expected format:
    {
        "winning_numbers": "01 02 03 04 05 06",
        "draw_date": "2024-10-05T00:00:00.000"
    }
    """
    try:
        numbers_str = item.get("winning_numbers", "")
        numbers = [int(n.strip()) for n in numbers_str.split()]

        if len(numbers) != 6:
            return None

        draw_date_str = item.get("draw_date", "")
        draw_date = pd.to_datetime(draw_date_str).strftime("%Y-%m-%d")

        return {
            "draw_date": draw_date,
            "n1": numbers[0],
            "n2": numbers[1],
            "n3": numbers[2],
            "n4": numbers[3],
            "n5": numbers[4],
            "pb": numbers[5]
        }
    except Exception as e:
        logger.warning(f"Error parsing NY State format: {e}")
        return None


def _fetch_from_musl_api() -> Optional[List[Dict]]:
    """
    Fetches recent Powerball results from MUSL (Multi-State Lottery Association) API.
    
    Returns:
        List[Dict]: List containing the most recent drawing, or None if request fails.
    """
    try:
        api_key = os.getenv("MUSL_API_KEY")
        if not api_key:
            logger.warning("MUSL_API_KEY not found in environment variables")
            return None

        url = "https://api.musl.com/v3/numbers"
        headers = {
            "accept": "application/json",
            "x-api-key": api_key
        }
        params = {"GameCode": "powerball"}

        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()

        data = response.json()
        return [data] if data else None

    except requests.exceptions.RequestException as e:
        logger.warning(f"MUSL API request failed: {e}")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error fetching from MUSL API: {e}")
        return None


def _fetch_from_nystate_api() -> Optional[List[Dict]]:
    """
    Fetches Powerball results from NY State Open Data API (fallback/bulk source).
    
    Returns up to 5000 historical draws, suitable for:
    - Initial database population
    - Recovery from stale data
    - Fallback when MUSL unavailable
    
    Returns:
        List[Dict]: List of all historical drawings, or None if request fails.
    """
    try:
        url = "https://data.ny.gov/resource/d6yy-54nr.json"
        params = {
            "$limit": "5000",
            "$order": "draw_date DESC"
        }
        
        # Optional X-App-Token for higher rate limits
        app_token = os.getenv("NY_OPEN_DATA_APP_TOKEN")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        if app_token:
            headers["X-App-Token"] = app_token
            logger.debug("Using NY Open Data App Token for authenticated request")
        
        logger.info("Fetching from NY State Open Data API (up to 5000 draws)...")
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if data and len(data) > 0:
            logger.info(f"Successfully fetched {len(data)} draws from NY State API")
            return data
        else:
            logger.warning("NY State API returned empty response")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.warning(f"NY State API request failed: {e}")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error fetching from NY State: {e}")
        return None


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
