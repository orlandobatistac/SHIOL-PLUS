# Weekly Utilities for SHIOL+ Ticket Verification Limits
"""
Utilities for calculating weekly verification limits with Sunday 00:00 ET as week start.
All functions handle DST transitions and edge cases correctly.
"""

import pytz
from datetime import datetime, date, time, timedelta
from typing import Optional


def get_week_start_sunday_et(reference_date: Optional[datetime] = None) -> date:
    """
    Always returns the Sunday 00:00 ET that starts the current week.
    
    Args:
        reference_date: Optional reference datetime (for testing)
        
    Returns:
        Date of the Sunday that starts the week (always 00:00 ET)
        
    Test cases:
        - Saturday 23:59 ET -> Current week's Sunday
        - Sunday 00:00 ET -> Same Sunday  
        - Sunday 00:01 ET -> Same Sunday
        - During DST transitions -> Handles correctly
    """
    et_tz = pytz.timezone('US/Eastern')

    if reference_date is None:
        now_et = datetime.now(et_tz)
    else:
        if reference_date.tzinfo is None:
            now_et = et_tz.localize(reference_date)
        else:
            now_et = reference_date.astimezone(et_tz)

    # Calculate days back to Sunday (0=Monday, 6=Sunday in weekday())
    days_since_sunday = (now_et.weekday() + 1) % 7

    # Go back to Sunday 00:00 ET
    week_start_dt = now_et - timedelta(days=days_since_sunday)
    week_start_dt = week_start_dt.replace(hour=0, minute=0, second=0, microsecond=0)

    return week_start_dt.date()


def get_next_reset_datetime() -> datetime:
    """
    Returns next Sunday 00:00 ET as aware datetime object.
    
    Returns:
        Next Sunday 00:00 ET as timezone-aware datetime
    """
    current_week_start = get_week_start_sunday_et()
    next_sunday = current_week_start + timedelta(days=7)

    et_tz = pytz.timezone('US/Eastern')
    return et_tz.localize(datetime.combine(next_sunday, time(0, 0, 0)))


def get_time_until_reset() -> timedelta:
    """
    Returns time remaining until next weekly reset.
    
    Returns:
        Timedelta until next Sunday 00:00 ET
    """
    next_reset = get_next_reset_datetime()
    et_tz = pytz.timezone('US/Eastern')
    now_et = datetime.now(et_tz)

    return next_reset - now_et


def is_same_week(date1: datetime, date2: datetime) -> bool:
    """
    Check if two datetimes fall within the same verification week.
    
    Args:
        date1: First datetime to compare
        date2: Second datetime to compare
        
    Returns:
        True if both dates are in the same verification week
    """
    week1 = get_week_start_sunday_et(date1)
    week2 = get_week_start_sunday_et(date2)

    return week1 == week2


def format_reset_time(reset_datetime: datetime) -> str:
    """
    Format reset datetime for user display.
    
    Args:
        reset_datetime: The reset datetime
        
    Returns:
        Formatted string for UI display
    """
    # Convert to local timezone for display but keep ET reference
    return f"{reset_datetime.strftime('%A at %H:%M ET')} ({reset_datetime.strftime('%Y-%m-%d')})"


def get_week_info(reference_date: Optional[datetime] = None) -> dict:
    """
    Get comprehensive week information for debugging and display.
    
    Args:
        reference_date: Optional reference datetime
        
    Returns:
        Dictionary with week start, end, next reset, and time remaining
    """
    et_tz = pytz.timezone('US/Eastern')

    if reference_date is None:
        now_et = datetime.now(et_tz)
    else:
        if reference_date.tzinfo is None:
            now_et = et_tz.localize(reference_date)
        else:
            now_et = reference_date.astimezone(et_tz)

    week_start = get_week_start_sunday_et(reference_date)
    next_reset = get_next_reset_datetime()
    time_until_reset = next_reset - now_et

    return {
        'current_time_et': now_et.isoformat(),
        'week_start_date': week_start.isoformat(),
        'week_end_date': (week_start + timedelta(days=6)).isoformat(),
        'next_reset_datetime': next_reset.isoformat(),
        'time_until_reset_seconds': int(time_until_reset.total_seconds()),
        'time_until_reset_readable': str(time_until_reset).split('.')[0],  # Remove microseconds
        'is_weekend': now_et.weekday() in [5, 6],  # Saturday=5, Sunday=6
        'day_of_week': now_et.strftime('%A')
    }
