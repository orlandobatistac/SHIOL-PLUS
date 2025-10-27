import sqlite3
from unittest.mock import patch

from src.utils import validate_date_format, format_date, get_latest_draw_date


def test_validate_date_format_ok_and_bad():
    assert validate_date_format("2025-10-23") is True
    assert validate_date_format("23-10-2025") is False


def test_format_date_conversions():
    assert format_date("2025-10-23") == "October 23, 2025"
    assert format_date("2025-10-23", output_format="%Y/%m/%d") == "2025/10/23"
    # Bad input returns original string
    assert format_date("BAD-DATE") == "BAD-DATE"


def _memory_conn_with_table_and_rows(rows=None):
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE powerball_draws (draw_date TEXT)")
    if rows:
        cur.executemany("INSERT INTO powerball_draws (draw_date) VALUES (?)", [(r,) for r in rows])
    conn.commit()
    return conn


def test_get_latest_draw_date_none_when_empty():
    with patch("src.utils.get_db_connection", return_value=_memory_conn_with_table_and_rows([])):
        result = get_latest_draw_date()
        assert result is None


def test_get_latest_draw_date_returns_latest():
    rows = ["2025-10-20", "2025-10-22", "2025-10-21"]
    with patch("src.utils.get_db_connection", return_value=_memory_conn_with_table_and_rows(rows)):
        result = get_latest_draw_date()
        assert result == "2025-10-22"
