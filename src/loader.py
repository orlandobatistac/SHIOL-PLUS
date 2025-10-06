import os
from typing import Optional, Dict, List
from datetime import datetime

import pandas as pd
import requests
from loguru import logger

from src.database import (
    bulk_insert_draws,
    get_all_draws,
    get_latest_draw_date,
    initialize_database,
)


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


def update_database_from_source() -> int:
    """
    Fetches the latest Powerball data from official APIs, compares it with the existing database,
    and inserts only the new draws. Initializes the database if it's empty.

    Data Sources (in priority order):
    1. Powerball.com official API (primary)
    2. NY State Open Data API (fallback)

    Returns:
        int: Total number of rows in the database after the update.
    """
    logger.info("Starting data update process...")
    initialize_database()

    fetched_data = _fetch_powerball_data()
    
    if fetched_data is None or len(fetched_data) == 0:
        logger.error("Update process failed: could not fetch data from any source.")
        return len(get_all_draws())

    transformed_df = _transform_api_data(fetched_data)
    
    if transformed_df is None or transformed_df.empty:
        logger.error("Update process failed: could not transform data.")
        return len(get_all_draws())

    latest_date_in_db = get_latest_draw_date()

    if latest_date_in_db:
        transformed_df["draw_date"] = pd.to_datetime(transformed_df["draw_date"])
        latest_date_in_db_dt = pd.to_datetime(latest_date_in_db)

        new_draws_df = transformed_df[
            transformed_df["draw_date"] > latest_date_in_db_dt
        ].copy()
        logger.info(f"Found {len(new_draws_df)} new draws to add.")
    else:
        new_draws_df = transformed_df.copy()
        logger.info(f"Database is empty. Populating with {len(new_draws_df)} draws.")

    if not new_draws_df.empty:
        final_draws_df = new_draws_df.copy()
        final_draws_df["draw_date"] = final_draws_df["draw_date"].dt.strftime("%Y-%m-%d")
        bulk_insert_draws(final_draws_df)

    final_df = get_all_draws()
    return len(final_df)


def _fetch_powerball_data() -> Optional[List[Dict]]:
    """
    Fetches Powerball data from available API sources with automatic fallback.
    
    Priority order:
    1. MUSL API (official Multi-State Lottery Association) - Primary
    2. NY State Open Data - Fallback
    
    Returns:
        List[Dict]: List of drawing results, or None if all sources fail.
    """
    data = _fetch_from_musl_api()
    
    if data:
        logger.info(f"Successfully fetched {len(data)} draws from MUSL API")
        return data
    
    logger.warning("MUSL API failed, trying NY State fallback...")
    data = _fetch_from_nystate_api()
    
    if data:
        logger.info(f"Successfully fetched {len(data)} draws from NY State Open Data")
        return data
    
    logger.error("All data sources failed")
    return None


def _fetch_from_nystate_api() -> Optional[List[Dict]]:
    """
    Fetches Powerball results from NY State Open Data API (fallback source).
    
    Returns:
        List[Dict]: List of all historical drawings, or None if request fails.
    """
    try:
        url = "https://data.ny.gov/resource/d6yy-54nr.json?$limit=5000&$order=draw_date DESC"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        return data
        
    except requests.exceptions.RequestException as e:
        logger.warning(f"NY State API request failed: {e}")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error fetching from NY State: {e}")
        return None


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
