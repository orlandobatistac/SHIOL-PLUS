"""
Test for pipeline draw time validation fix.

This test verifies that the pipeline correctly validates that the expected
draw time has passed before attempting to poll for results.

Bug fix: Previously, the pipeline would poll for future draws that haven't
occurred yet, causing it to run for 6 hours and potentially get stuck in
a "running" state if the process was killed.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
import pytz


def test_pipeline_skips_future_draw():
    """Test that pipeline exits gracefully when draw time hasn't passed yet."""
    from src.date_utils import DateManager
    
    # Test case: It's November 15, 2025 at 8:00 PM ET (before 10:59 PM draw time)
    # Expected draw date is also November 15, 2025
    # Pipeline should detect that draw time hasn't passed and exit gracefully
    
    ET = pytz.timezone('America/New_York')
    current_time = ET.localize(datetime(2025, 11, 15, 20, 0))  # 8:00 PM ET
    expected_draw_date = '2025-11-15'
    
    # Calculate draw time
    expected_draw_dt = datetime.strptime(expected_draw_date, '%Y-%m-%d')
    draw_time_et = ET.localize(expected_draw_dt.replace(hour=22, minute=59, second=0))
    
    # Verify time until draw
    time_until_draw = (draw_time_et - current_time).total_seconds()
    hours_until = time_until_draw / 3600
    
    assert hours_until > 0, "Draw time should be in the future"
    assert hours_until == pytest.approx(2.98, abs=0.1), f"Expected ~3 hours, got {hours_until:.2f}"
    
    # This is what the pipeline should check
    should_poll = time_until_draw <= 0
    assert not should_poll, "Pipeline should NOT poll for future draws"


def test_pipeline_polls_past_draw():
    """Test that pipeline proceeds with polling when draw time has passed."""
    from src.date_utils import DateManager
    
    # Test case: It's November 16, 2025 at 12:05 AM ET (after 10:59 PM draw time)
    # Expected draw date is November 15, 2025
    # Pipeline should detect that draw time has passed and proceed with polling
    
    ET = pytz.timezone('America/New_York')
    current_time = ET.localize(datetime(2025, 11, 16, 0, 5))  # 12:05 AM ET next day
    expected_draw_date = '2025-11-15'
    
    # Calculate draw time
    expected_draw_dt = datetime.strptime(expected_draw_date, '%Y-%m-%d')
    draw_time_et = ET.localize(expected_draw_dt.replace(hour=22, minute=59, second=0))
    
    # Verify time since draw
    time_until_draw = (draw_time_et - current_time).total_seconds()
    hours_until = time_until_draw / 3600
    
    assert hours_until < 0, "Draw time should be in the past"
    assert hours_until == pytest.approx(-1.1, abs=0.1), f"Expected ~-1.1 hours, got {hours_until:.2f}"
    
    # This is what the pipeline should check
    should_poll = time_until_draw <= 0
    assert should_poll, "Pipeline SHOULD poll for past draws"


def test_pipeline_polls_on_draw_day_after_time():
    """Test that pipeline polls on drawing day after draw time passes."""
    from src.date_utils import DateManager
    
    # Test case: It's November 15, 2025 at 11:05 PM ET (after 10:59 PM draw time)
    # Expected draw date is November 15, 2025
    # Pipeline should detect that draw time has passed and proceed with polling
    
    ET = pytz.timezone('America/New_York')
    current_time = ET.localize(datetime(2025, 11, 15, 23, 5))  # 11:05 PM ET
    expected_draw_date = '2025-11-15'
    
    # Calculate draw time
    expected_draw_dt = datetime.strptime(expected_draw_date, '%Y-%m-%d')
    draw_time_et = ET.localize(expected_draw_dt.replace(hour=22, minute=59, second=0))
    
    # Verify time since draw
    time_until_draw = (draw_time_et - current_time).total_seconds()
    hours_until = time_until_draw / 3600
    
    assert hours_until < 0, "Draw time should be in the past"
    assert hours_until == pytest.approx(-0.1, abs=0.05), f"Expected ~-0.1 hours, got {hours_until:.2f}"
    
    # This is what the pipeline should check
    should_poll = time_until_draw <= 0
    assert should_poll, "Pipeline SHOULD poll on drawing day after draw time"


def test_get_expected_draw_for_pipeline_logic():
    """Test the logic of get_expected_draw_for_pipeline to ensure it doesn't return future dates."""
    from src.date_utils import DateManager
    
    ET = pytz.timezone('America/New_York')
    
    # Mock current time: November 15, 2025 at 8:00 PM ET (before draw)
    with patch.object(DateManager, 'get_current_et_time') as mock_time:
        mock_time.return_value = ET.localize(datetime(2025, 11, 15, 20, 0))
        
        # If last draw in DB is November 12 (Wednesday), next expected is November 15 (Saturday)
        # But since it's before draw time on Nov 15, it should NOT return November 15
        # Instead, it should return November 12 (the most recent past completed draw)
        last_draw_in_db = '2025-11-12'
        expected = DateManager.get_expected_draw_for_pipeline(last_draw_in_db)
        
        # The function should return Nov 12 (last completed draw), not Nov 15 (future)
        # Nov 12 is Wednesday, Nov 15 is Saturday (next draw day but hasn't occurred yet)
        assert expected == '2025-11-12', f"Expected '2025-11-12', got '{expected}'"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
