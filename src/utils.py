
"""
SHIOL+ Utilities Module
======================

Common utility functions used across the application.
"""

from datetime import datetime
from loguru import logger
from src.database import get_db_connection


def get_latest_draw_date():
    """
    Get the latest draw date from the database.
    
    Returns:
        str: Latest draw date in YYYY-MM-DD format, or None if no data found
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT draw_date 
            FROM powerball_draws 
            ORDER BY draw_date DESC 
            LIMIT 1
        """)

        result = cursor.fetchone()
        conn.close()

        if result:
            return result[0]
        else:
            logger.warning("No draw dates found in database")
            return None

    except Exception as e:
        logger.error(f"Error getting latest draw date: {e}")
        return None


def format_date(date_str, input_format="%Y-%m-%d", output_format="%B %d, %Y"):
    """
    Format a date string from one format to another.
    
    Args:
        date_str: Input date string
        input_format: Format of input date string
        output_format: Desired output format
        
    Returns:
        str: Formatted date string
    """
    try:
        date_obj = datetime.strptime(date_str, input_format)
        return date_obj.strftime(output_format)
    except Exception as e:
        logger.error(f"Error formatting date {date_str}: {e}")
        return date_str


def validate_date_format(date_str, date_format="%Y-%m-%d"):
    """
    Validate if a date string matches the expected format.
    
    Args:
        date_str: Date string to validate
        date_format: Expected date format
        
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        datetime.strptime(date_str, date_format)
        return True
    except ValueError:
        return False
