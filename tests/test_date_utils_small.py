from datetime import datetime

import pytz

from src.date_utils import DateManager, validate_date_format, is_valid_drawing_date, convert_to_et


def test_validate_date_format_good_and_bad():
    assert validate_date_format("2025-10-23") is True
    assert validate_date_format("2025/10/23") is False
    assert validate_date_format("2025-10-230") is False


def test_convert_to_et_from_string_and_datetime():
    # naive string treated as ET localized
    et_dt = convert_to_et("2025-10-23 12:34:00")
    assert et_dt.tzinfo is not None
    assert str(et_dt.tzinfo) == str(DateManager.POWERBALL_TIMEZONE)

    # aware datetime converted to ET
    aware_utc = datetime(2025, 10, 23, 12, 0, tzinfo=pytz.UTC)
    et_dt2 = convert_to_et(aware_utc)
    assert et_dt2.tzinfo is not None
    assert str(et_dt2.tzinfo) == str(DateManager.POWERBALL_TIMEZONE)


def test_is_valid_drawing_date_known_days():
    # Wednesday (2025-10-22) and Saturday (2025-10-25)
    assert is_valid_drawing_date("2025-10-22") is True
    assert is_valid_drawing_date("2025-10-25") is True
    # Tuesday
    assert is_valid_drawing_date("2025-10-21") is False


def test_format_datetime_for_display_basic():
    # Naive datetime assumed as ET
    dt = datetime(2025, 10, 23, 9, 5)
    s = DateManager.format_datetime_for_display(dt)
    assert "10/23/2025" in s and "ET" in s
