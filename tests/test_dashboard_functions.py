
import pytest
import asyncio
import json
import os
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import HTTPException

# Import the functions to test
import sys
sys.path.append('src')

from api_pipeline_endpoints import (
    _get_current_pipeline_status,
    _get_scheduler_status,
    _get_execution_history,
    _get_last_generated_plays,
    _determine_health_status,
    _execute_pipeline_async,
    _add_to_execution_history
)

class TestDashboardFunctions:
    """Test suite for dashboard backend functions"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_data_dir = "test_data"
        os.makedirs(self.test_data_dir, exist_ok=True)
        
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)
    
    @pytest.mark.asyncio
    async def test_get_current_pipeline_status_idle(self):
        """Test getting pipeline status when idle"""
        # Test when no status file exists
        result = await _get_current_pipeline_status()
        
        assert result["status"] == "idle"
        assert "ready for execution" in result["description"]
    
    @pytest.mark.asyncio
    async def test_get_current_pipeline_status_running(self):
        """Test getting pipeline status when running"""
        # Create mock status file
        status_file = "data/pipeline_status.json"
        os.makedirs(os.path.dirname(status_file), exist_ok=True)
        
        status_data = {
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "description": "Pipeline is executing"
        }
        
        with open(status_file, 'w') as f:
            json.dump(status_data, f)
        
        try:
            result = await _get_current_pipeline_status()
            assert result["status"] == "running"
            assert "currently executing" in result["description"]
        finally:
            # Cleanup
            if os.path.exists(status_file):
                os.remove(status_file)
    
    @pytest.mark.asyncio
    async def test_get_scheduler_status_active(self):
        """Test getting scheduler status when active"""
        # Mock the scheduler
        mock_scheduler = MagicMock()
        mock_scheduler.running = True
        mock_job = MagicMock()
        mock_job.next_run_time = datetime.now()
        mock_scheduler.get_jobs.return_value = [mock_job]
        
        with patch('src.api_pipeline_endpoints.scheduler', mock_scheduler):
            result = await _get_scheduler_status()
            
            assert result["active"] is True
            assert result["job_count"] == 1
            assert result["next_run"] is not None
    
    @pytest.mark.asyncio
    async def test_get_scheduler_status_inactive(self):
        """Test getting scheduler status when inactive"""
        with patch('src.api_pipeline_endpoints.scheduler', None):
            result = await _get_scheduler_status()
            
            assert result["active"] is False
            assert result["job_count"] == 0
            assert result["next_run"] is None
    
    @pytest.mark.asyncio
    async def test_get_execution_history_empty(self):
        """Test getting execution history when empty"""
        result = await _get_execution_history(limit=5)
        assert result == []
    
    @pytest.mark.asyncio
    async def test_get_execution_history_with_data(self):
        """Test getting execution history with data"""
        # Create mock history file
        history_file = "data/pipeline_history.json"
        os.makedirs(os.path.dirname(history_file), exist_ok=True)
        
        mock_history = [
            {
                "execution_id": "test_1",
                "status": "completed",
                "start_time": "2025-01-11T10:00:00",
                "end_time": "2025-01-11T10:05:00"
            },
            {
                "execution_id": "test_2", 
                "status": "failed",
                "start_time": "2025-01-11T11:00:00",
                "end_time": "2025-01-11T11:02:00"
            }
        ]
        
        with open(history_file, 'w') as f:
            json.dump(mock_history, f)
        
        try:
            result = await _get_execution_history(limit=5)
            assert len(result) == 2
            assert result[0]["execution_id"] == "test_1"
            assert result[1]["status"] == "failed"
        finally:
            if os.path.exists(history_file):
                os.remove(history_file)
    
    @pytest.mark.asyncio
    async def test_get_last_generated_plays(self):
        """Test getting last generated plays"""
        # Mock database function
        mock_predictions = [
            {
                'numbers': [1, 2, 3, 4, 5],
                'powerball': 10,
                'score_total': 0.85,
                'timestamp': '2025-01-11T10:00:00'
            }
        ]
        
        with patch('src.api_pipeline_endpoints.get_prediction_history', return_value=mock_predictions):
            result = await _get_last_generated_plays()
            
            assert len(result) == 1
            assert result[0]['numbers'] == [1, 2, 3, 4, 5]
            assert result[0]['powerball'] == 10
            assert result[0]['score'] == 0.85
    
    def test_determine_health_status_healthy(self):
        """Test health status determination - healthy"""
        result = _determine_health_status(50.0, 60.0, 70.0)
        assert result == "healthy"
    
    def test_determine_health_status_degraded(self):
        """Test health status determination - degraded"""
        result = _determine_health_status(75.0, 80.0, 85.0)
        assert result == "degraded"
    
    def test_determine_health_status_warning(self):
        """Test health status determination - warning"""
        result = _determine_health_status(85.0, 90.0, 92.0)
        assert result == "warning"
    
    def test_determine_health_status_critical(self):
        """Test health status determination - critical"""
        result = _determine_health_status(95.0, 98.0, 99.0)
        assert result == "critical"
    
    @pytest.mark.asyncio
    async def test_add_to_execution_history(self):
        """Test adding execution to history"""
        history_file = "data/pipeline_history.json"
        
        status_data = {
            "execution_id": "test_execution",
            "status": "completed",
            "start_time": datetime.now().isoformat(),
            "triggered_by": "test_user"
        }
        
        await _add_to_execution_history(status_data)
        
        # Verify history was saved
        assert os.path.exists(history_file)
        
        with open(history_file, 'r') as f:
            history = json.load(f)
        
        assert len(history) == 1
        assert history[0]["execution_id"] == "test_execution"
        assert history[0]["status"] == "completed"
        
        # Cleanup
        if os.path.exists(history_file):
            os.remove(history_file)
    
    @pytest.mark.asyncio
    async def test_execute_pipeline_async_success(self):
        """Test async pipeline execution - success case"""
        # Mock subprocess execution
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"Success output", b"")
        mock_process.returncode = 0
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch('src.api_pipeline_endpoints._add_to_execution_history') as mock_add_history:
                await _execute_pipeline_async("test_user")
                
                # Verify history was added
                mock_add_history.assert_called_once()
                
                # Verify status file was created
                status_file = "data/pipeline_status.json"
                assert os.path.exists(status_file)
                
                with open(status_file, 'r') as f:
                    status = json.load(f)
                
                assert status["status"] == "completed"
                assert status["triggered_by"] == "test_user"
                
                # Cleanup
                if os.path.exists(status_file):
                    os.remove(status_file)
    
    @pytest.mark.asyncio
    async def test_execute_pipeline_async_failure(self):
        """Test async pipeline execution - failure case"""
        # Mock subprocess execution failure
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"Error occurred")
        mock_process.returncode = 1
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch('src.api_pipeline_endpoints._add_to_execution_history') as mock_add_history:
                await _execute_pipeline_async("test_user")
                
                # Verify history was added
                mock_add_history.assert_called_once()
                
                # Verify status file shows failure
                status_file = "data/pipeline_status.json"
                assert os.path.exists(status_file)
                
                with open(status_file, 'r') as f:
                    status = json.load(f)
                
                assert status["status"] == "failed"
                assert status["exit_code"] == 1
                assert "Error occurred" in status.get("error", "")
                
                # Cleanup
                if os.path.exists(status_file):
                    os.remove(status_file)

# Integration tests for API endpoints
class TestPipelineAPI:
    """Integration tests for pipeline API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        from src.api import app
        return TestClient(app)
    
    def test_pipeline_status_unauthorized(self, client):
        """Test pipeline status endpoint without auth"""
        response = client.get("/api/v1/pipeline/status")
        assert response.status_code == 401
    
    @patch('src.api_pipeline_endpoints.get_current_user')
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_pipeline_status_authorized(self, mock_disk, mock_memory, mock_cpu, mock_user, client):
        """Test pipeline status endpoint with auth"""
        # Mock user authentication
        mock_user.return_value = MagicMock(username="test_user")
        
        # Mock system metrics
        mock_cpu.return_value = 50.0
        mock_memory.return_value = MagicMock(percent=60.0)
        mock_disk.return_value = MagicMock(percent=70.0)
        
        response = client.get("/api/v1/pipeline/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "pipeline_status" in data
        assert "system_health" in data["pipeline_status"]
        assert data["pipeline_status"]["system_health"]["status"] == "healthy"

if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
