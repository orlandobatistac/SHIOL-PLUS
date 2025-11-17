"""
Test for SHIOL+ v2 Analytics API
=================================

Tests the /api/v3/analytics/overview endpoint.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import pandas as pd


def test_analytics_endpoint_integration():
    """Integration test for analytics endpoint"""
    # Import here to avoid circular imports
    from src.v2.analytics_api import analytics_router
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(analytics_router)
    
    client = TestClient(app)
    
    # Create mock draw data
    draws = []
    for i in range(100):
        draws.append({
            'draw_date': f'2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}',
            'n1': (i % 69) + 1,
            'n2': ((i + 10) % 69) + 1,
            'n3': ((i + 20) % 69) + 1,
            'n4': ((i + 30) % 69) + 1,
            'n5': ((i + 40) % 69) + 1,
            'pb': (i % 26) + 1
        })
    
    draws_df = pd.DataFrame(draws)
    
    # Mock the get_all_draws function
    with patch('src.v2.analytics_api.get_all_draws', return_value=draws_df):
        with patch('src.v2.analytics_api.get_db_connection') as mock_conn:
            # Mock co-occurrence query
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = [
                (23, 45, 15, 25.5),
                (12, 34, 12, 20.3)
            ]
            mock_conn.return_value.cursor.return_value = mock_cursor
            
            # Make request
            response = client.get("/api/v3/analytics/overview")
            
            # Check response
            assert response.status_code == 200
            
            data = response.json()
            
            # Validate structure
            assert 'hot_cold' in data
            assert 'momentum' in data
            assert 'gaps' in data
            assert 'patterns' in data
            assert 'top_cooccurrences' in data
            assert 'summary_commentary' in data
            assert 'total_draws' in data
            assert 'last_updated' in data
            
            # Validate hot_cold
            assert 'hot_numbers' in data['hot_cold']
            assert 'cold_numbers' in data['hot_cold']
            assert len(data['hot_cold']['hot_numbers']) == 10
            assert len(data['hot_cold']['cold_numbers']) == 10
            
            # Validate momentum
            assert 'rising_numbers' in data['momentum']
            assert 'falling_numbers' in data['momentum']
            assert 'momentum_chart' in data['momentum']
            
            # Validate gaps
            assert 'overdue_numbers' in data['gaps']
            assert 'avg_gap' in data['gaps']
            assert 'gap_chart' in data['gaps']
            
            # Validate patterns
            assert 'odd_even_distribution' in data['patterns']
            assert 'sum_stats' in data['patterns']
            
            # Validate co-occurrences
            assert len(data['top_cooccurrences']) == 2
            assert data['top_cooccurrences'][0]['number_a'] == 23
            
            # Validate summary
            assert isinstance(data['summary_commentary'], str)
            assert len(data['summary_commentary']) > 0
            
            # Validate total draws
            assert data['total_draws'] == 100


def test_analytics_endpoint_empty_database():
    """Test analytics endpoint with empty database"""
    from src.v2.analytics_api import analytics_router
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(analytics_router)
    
    client = TestClient(app)
    
    # Mock empty draws
    with patch('src.v2.analytics_api.get_all_draws', return_value=pd.DataFrame()):
        response = client.get("/api/v3/analytics/overview")
        
        # Should return 503 Service Unavailable
        assert response.status_code == 503
        assert "No historical data" in response.json()['detail']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
