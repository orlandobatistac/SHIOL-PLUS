"""
Test pipeline validation functions.

These tests verify that the validation gates correctly identify
success/failure scenarios for each pipeline step.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date


@pytest.fixture
def mock_execution_id():
    """Return a test execution ID."""
    return "test1234"


@pytest.fixture
def mock_db_connection(monkeypatch):
    """Mock database connection for testing."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    
    def mock_get_db_connection():
        return mock_conn
    
    monkeypatch.setattr("src.database.get_db_connection", mock_get_db_connection)
    
    return mock_conn, mock_cursor


class TestStep1Validation:
    """Test STEP 1: Data download validation."""
    
    def test_success_new_draws_fetched(self, mock_execution_id, monkeypatch):
        """Test validation passes when new draws are fetched."""
        # Mock database functions
        monkeypatch.setattr("src.database.get_latest_draw_date", lambda: "2025-11-01")
        
        from src.api import validate_step_1_data_download
        
        # Simulate 1857 draws in DB (new data fetched)
        result = validate_step_1_data_download(1857, mock_execution_id)
        
        assert result['success'] is True
        assert result['error'] is None
        assert result['details']['new_draws_count'] == 1857
        assert result['details']['validation'] == 'new_data_fetched'
    
    def test_success_same_day_rerun(self, mock_execution_id, monkeypatch):
        """Test validation passes for same-day re-run scenario."""
        # Mock database to return today's date as latest draw
        current_date = date.today().strftime("%Y-%m-%d")
        monkeypatch.setattr("src.database.get_latest_draw_date", lambda: current_date)
        
        from src.api import validate_step_1_data_download
        
        # Simulate 0 new draws (re-run scenario, data already fresh)
        result = validate_step_1_data_download(0, mock_execution_id)
        
        assert result['success'] is True
        assert result['error'] is None
        assert result['details']['validation'] == 'same_day_rerun'
    
    def test_failure_stale_data(self, mock_execution_id, monkeypatch):
        """Test validation fails when no new draws and data is stale."""
        # Mock database to return old date
        monkeypatch.setattr("src.database.get_latest_draw_date", lambda: "2025-10-25")
        
        from src.api import validate_step_1_data_download
        
        # Simulate 0 new draws with stale data
        result = validate_step_1_data_download(0, mock_execution_id)
        
        assert result['success'] is False
        assert "stale" in result['error'].lower()
        assert result['details']['new_draws_count'] == 0


class TestStep2Validation:
    """Test STEP 2: Analytics update validation."""
    
    def test_success_analytics_populated(self, mock_execution_id, mock_db_connection):
        """Test validation passes when analytics tables have data."""
        mock_conn, mock_cursor = mock_db_connection
        
        # Mock cursor to return counts > 0
        mock_cursor.fetchone.side_effect = [(2346,), (10,)]  # cooccurrences, patterns
        
        from src.api import validate_step_2_analytics
        
        result = validate_step_2_analytics(mock_execution_id)
        
        assert result['success'] is True
        assert result['error'] is None
        assert result['details']['cooccurrence_count'] == 2346
        assert result['details']['pattern_count'] == 10
    
    def test_failure_empty_tables(self, mock_execution_id, mock_db_connection):
        """Test validation fails when analytics tables are empty."""
        mock_conn, mock_cursor = mock_db_connection
        
        # Mock cursor to return 0 counts
        mock_cursor.fetchone.side_effect = [(0,), (0,)]
        
        from src.api import validate_step_2_analytics
        
        result = validate_step_2_analytics(mock_execution_id)
        
        assert result['success'] is False
        assert "empty" in result['error'].lower()


class TestStep3Validation:
    """Test STEP 3: Evaluation validation (always succeeds)."""
    
    def test_success_with_draw(self, mock_execution_id):
        """Test validation succeeds with latest draw present."""
        from src.api import validate_step_3_evaluation
        
        result = validate_step_3_evaluation(mock_execution_id, "2025-11-01")
        
        assert result['success'] is True
        assert result['error'] is None
        assert result['details']['latest_draw'] == "2025-11-01"
    
    def test_success_no_draw(self, mock_execution_id):
        """Test validation succeeds even with no draw (informational)."""
        from src.api import validate_step_3_evaluation
        
        result = validate_step_3_evaluation(mock_execution_id, None)
        
        assert result['success'] is True  # Still succeeds
        assert result['error'] is None
        assert 'note' in result['details']


class TestStep4Validation:
    """Test STEP 4: Adaptive learning validation."""
    
    def test_success_valid_weights(self, mock_execution_id, mock_db_connection):
        """Test validation passes with valid strategy weights."""
        mock_conn, mock_cursor = mock_db_connection
        
        # Mock strategy_performance table
        mock_cursor.fetchone.return_value = (6,)  # 6 strategies
        mock_cursor.fetchall.return_value = [
            ('frequency_weighted', 0.25),
            ('cooccurrence', 0.20),
            ('coverage_optimizer', 0.15),
            ('range_balanced', 0.15),
            ('ai_guided', 0.15),
            ('random_baseline', 0.10)
        ]
        
        from src.api import validate_step_4_adaptive_learning
        
        result = validate_step_4_adaptive_learning(mock_execution_id)
        
        assert result['success'] is True
        assert result['error'] is None
        assert result['details']['strategy_count'] == 6
    
    def test_failure_invalid_weights(self, mock_execution_id, mock_db_connection):
        """Test validation fails with out-of-range weights."""
        mock_conn, mock_cursor = mock_db_connection
        
        # Mock invalid weight (> 1.0)
        mock_cursor.fetchone.return_value = (2,)
        mock_cursor.fetchall.return_value = [
            ('frequency_weighted', 1.5),  # Invalid
            ('cooccurrence', 0.5)
        ]
        
        from src.api import validate_step_4_adaptive_learning
        
        result = validate_step_4_adaptive_learning(mock_execution_id)
        
        assert result['success'] is False
        assert "invalid" in result['error'].lower()


class TestStep5Validation:
    """Test STEP 5: Prediction generation validation."""
    
    def test_success_all_tickets_saved(self, mock_execution_id):
        """Test validation passes when all tickets are saved."""
        from src.api import validate_step_5_prediction
        
        result = validate_step_5_prediction(200, 200, mock_execution_id)
        
        assert result['success'] is True
        assert result['error'] is None
        assert result['details']['saved_count'] == 200
        assert result['details']['expected_count'] == 200
    
    def test_failure_ticket_mismatch(self, mock_execution_id):
        """Test validation fails when ticket counts don't match."""
        from src.api import validate_step_5_prediction
        
        result = validate_step_5_prediction(150, 200, mock_execution_id)
        
        assert result['success'] is False
        assert "mismatch" in result['error'].lower()
        assert result['details']['saved_count'] == 150
        assert result['details']['expected_count'] == 200
