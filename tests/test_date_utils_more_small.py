from datetime import datetime

import pytz

from src.date_utils import DateManager


def test_days_until_next_drawing_is_reasonable():
    # Use a fixed aware datetime in UTC to avoid flakiness
    ref = datetime(2025, 10, 23, 12, 0, tzinfo=pytz.UTC)
    days = DateManager.days_until_next_drawing(reference_date=ref)
    # Should be within a week and non-negative
    assert 0 <= days <= 7


def test_get_recent_drawing_dates_count_and_format():
    dates = DateManager.get_recent_drawing_dates(count=5)
    assert isinstance(dates, list) and len(dates) == 5
    # YYYY-MM-DD format sanity check
    for d in dates:
        assert isinstance(d, str) and len(d) == 10 and d.count('-') == 2


def test_get_current_date_info_has_keys():
    info = DateManager.get_current_date_info()
    required_keys = {"date", "formatted_date", "day", "month", "year", "weekday", "weekday_name", "time", "is_drawing_day", "iso"}
    assert required_keys.issubset(info.keys())
