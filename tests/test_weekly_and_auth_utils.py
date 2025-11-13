from datetime import datetime
import pytz


def test_weekly_utils_core():
    from src.weekly_utils import get_week_start_sunday_et, is_same_week, format_reset_time
    et = pytz.timezone('US/Eastern')
    dt_sat = et.localize(datetime(2025, 1, 4, 23, 59))  # Saturday
    dt_sun = et.localize(datetime(2025, 1, 5, 0, 0))    # Sunday

    start_sat = get_week_start_sunday_et(dt_sat)
    start_sun = get_week_start_sunday_et(dt_sun)
    # Saturday belongs to the week starting previous Sunday (2024-12-29)
    assert str(start_sat) == "2024-12-29"
    # Sunday is the new week start
    assert str(start_sun) == "2025-01-05"
    # They are different weeks
    assert is_same_week(dt_sat, dt_sun) is False

    # format function returns a string with weekday
    from src.weekly_utils import get_next_reset_datetime
    reset_dt = get_next_reset_datetime()
    formatted = format_reset_time(reset_dt)
    assert isinstance(formatted, str) and 'ET' in formatted


def test_apply_freemium_restrictions_guest_free_premium(monkeypatch):
    from src.auth_middleware import apply_freemium_restrictions
    from types import SimpleNamespace

    # Mock request is not used by access directly here
    request = SimpleNamespace(headers={})

    # Prepare predictions unsorted to verify sorting by confidence_score desc
    preds = [
        {"id": 1, "confidence_score": 0.1, "draw_date": "2025-01-05"},
        {"id": 2, "confidence_score": 0.9, "draw_date": "2025-01-05"},
        {"id": 3, "confidence_score": 0.5, "draw_date": "2025-01-05"},
    ]

    # Guest: get_user_access_level returns None user (max 1)
    monkeypatch.setattr(
        'src.auth_middleware.get_user_access_level',
        lambda req, dd=None: {
            "authenticated": False, "is_premium": False, "max_predictions": 1, "access_level": "guest", "user": None
        },
        raising=True,
    )
    out_guest = apply_freemium_restrictions(preds, request, "2025-01-05")
    assert out_guest["accessible_count"] == 1
    assert out_guest["locked_count"] == 2
    # First prediction must be the highest confidence id=2
    assert out_guest["predictions"][0]["id"] == 2

    # Free registered user: max 5 on Saturday -> our list has 3, all unlocked
    monkeypatch.setattr(
        'src.auth_middleware.get_user_access_level',
        lambda req, dd=None: {
            "authenticated": True, "is_premium": False, "max_predictions": 5, "access_level": "free", "user": {"id": 1}
        },
        raising=True,
    )
    out_free = apply_freemium_restrictions(preds, request, "2025-01-04")
    assert out_free["accessible_count"] == 3
    assert out_free["locked_count"] == 0

    # Premium user: cap at 200
    monkeypatch.setattr(
        'src.auth_middleware.get_user_access_level',
        lambda req, dd=None: {
            "authenticated": True, "is_premium": True, "max_predictions": 100, "access_level": "premium", "user": {"id": 2}
        },
        raising=True,
    )
    out_premium = apply_freemium_restrictions(preds * 300, request, "2025-01-07")
    assert out_premium["accessible_count"] == 200
    assert out_premium["locked_count"] == len(preds * 300) - 200
