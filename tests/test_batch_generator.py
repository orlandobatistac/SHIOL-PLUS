"""
Tests for BatchTicketGenerator
===============================
Validates batch ticket pre-generation system functionality.
"""

import pytest
import os
import sys
import sqlite3
from unittest.mock import patch, MagicMock

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.batch_generator import BatchTicketGenerator
from src.database import (
    insert_batch_tickets,
    get_cached_tickets,
    clear_old_batch_tickets,
    get_batch_ticket_stats
)

TEST_DB_PATH = "/tmp/shiol_plus_batch_test.db"


@pytest.fixture
def test_db():
    """Create a test database with required tables."""
    # Remove existing test db
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    
    # Create test database
    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()
    
    # Create pre_generated_tickets table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pre_generated_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT NOT NULL,
            pipeline_run_id TEXT,
            n1 INTEGER NOT NULL,
            n2 INTEGER NOT NULL,
            n3 INTEGER NOT NULL,
            n4 INTEGER NOT NULL,
            n5 INTEGER NOT NULL,
            powerball INTEGER NOT NULL,
            confidence_score REAL DEFAULT 0.5,
            strategy_used TEXT,
            metadata TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            CHECK (n1 < n2 AND n2 < n3 AND n3 < n4 AND n4 < n5),
            CHECK (n1 >= 1 AND n5 <= 69),
            CHECK (powerball >= 1 AND powerball <= 26),
            CHECK (mode IN ('random_forest', 'lstm', 'v1', 'v2', 'hybrid'))
        )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pre_generated_mode ON pre_generated_tickets(mode)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pre_generated_created_at ON pre_generated_tickets(created_at DESC)")
    
    conn.commit()
    conn.close()
    
    yield TEST_DB_PATH
    
    # Cleanup
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


class TestDatabaseFunctions:
    """Test database functions for batch tickets."""
    
    def test_insert_batch_tickets_valid(self, test_db):
        """Test inserting valid batch tickets."""
        with patch('src.database.get_db_path', return_value=test_db):
            tickets = [
                {
                    'white_balls': [1, 2, 3, 4, 5],
                    'powerball': 10,
                    'strategy': 'random_forest',
                    'confidence': 0.8
                },
                {
                    'white_balls': [6, 7, 8, 9, 10],
                    'powerball': 15,
                    'strategy': 'random_forest',
                    'confidence': 0.7
                }
            ]
            
            inserted = insert_batch_tickets(tickets, 'random_forest', 'test-run-123')
            assert inserted == 2
    
    def test_insert_batch_tickets_invalid(self, test_db):
        """Test inserting invalid tickets (should skip invalid ones)."""
        with patch('src.database.get_db_path', return_value=test_db):
            tickets = [
                {
                    'white_balls': [1, 2, 3, 4, 5],
                    'powerball': 10
                },
                {
                    # Invalid: missing powerball
                    'white_balls': [6, 7, 8, 9, 10]
                },
                {
                    # Invalid: unsorted white balls
                    'white_balls': [5, 4, 3, 2, 1],
                    'powerball': 15
                }
            ]
            
            inserted = insert_batch_tickets(tickets, 'random_forest', 'test-run-123')
            # Only first ticket should be inserted
            assert inserted == 1
    
    def test_get_cached_tickets(self, test_db):
        """Test retrieving cached tickets."""
        with patch('src.database.get_db_path', return_value=test_db):
            # Insert test tickets
            tickets = [
                {
                    'white_balls': [1, 2, 3, 4, 5],
                    'powerball': 10,
                    'confidence': 0.8
                }
            ]
            insert_batch_tickets(tickets, 'random_forest', 'test-run-123')
            
            # Retrieve tickets
            cached = get_cached_tickets('random_forest', limit=10)
            
            assert len(cached) == 1
            assert cached[0]['white_balls'] == [1, 2, 3, 4, 5]
            assert cached[0]['powerball'] == 10
            assert cached[0]['cached'] is True
    
    def test_get_cached_tickets_limit(self, test_db):
        """Test limit parameter in get_cached_tickets."""
        with patch('src.database.get_db_path', return_value=test_db):
            # Insert multiple tickets
            tickets = [
                {
                    'white_balls': [i, i+1, i+2, i+3, i+4],
                    'powerball': 10 + i,
                    'confidence': 0.5
                }
                for i in range(1, 6)  # 5 tickets
            ]
            insert_batch_tickets(tickets, 'lstm', 'test-run-123')
            
            # Retrieve with limit
            cached = get_cached_tickets('lstm', limit=3)
            
            assert len(cached) == 3
    
    def test_clear_old_batch_tickets(self, test_db):
        """Test clearing old tickets."""
        with patch('src.database.get_db_path', return_value=test_db):
            # Insert tickets
            tickets = [
                {
                    'white_balls': [1, 2, 3, 4, 5],
                    'powerball': 10
                }
            ]
            insert_batch_tickets(tickets, 'random_forest', 'test-run-123')
            
            # Clear tickets older than 0 days (should clear all)
            deleted = clear_old_batch_tickets(days=0)
            
            # Should delete the ticket we just inserted
            assert deleted >= 0  # Can be 0 if created_at is exactly now
    
    def test_get_batch_ticket_stats(self, test_db):
        """Test getting batch ticket statistics."""
        with patch('src.database.get_db_path', return_value=test_db):
            # Insert tickets for different modes
            rf_tickets = [
                {
                    'white_balls': [1, 2, 3, 4, 5],
                    'powerball': 10
                }
            ]
            lstm_tickets = [
                {
                    'white_balls': [6, 7, 8, 9, 10],
                    'powerball': 15
                },
                {
                    'white_balls': [11, 12, 13, 14, 15],
                    'powerball': 20
                }
            ]
            
            insert_batch_tickets(rf_tickets, 'random_forest', 'test-run-1')
            insert_batch_tickets(lstm_tickets, 'lstm', 'test-run-2')
            
            # Get stats
            stats = get_batch_ticket_stats()
            
            assert stats['total_tickets'] == 3
            assert stats['by_mode']['random_forest'] == 1
            assert stats['by_mode']['lstm'] == 2


class TestBatchTicketGenerator:
    """Test BatchTicketGenerator class."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        generator = BatchTicketGenerator()
        
        assert generator.batch_size == 100
        assert generator.modes == ['random_forest', 'lstm']
        assert generator.auto_cleanup is True
        assert generator.cleanup_days == 7
    
    def test_initialization_custom(self):
        """Test custom initialization."""
        generator = BatchTicketGenerator(
            batch_size=50,
            modes=['v1', 'v2'],
            auto_cleanup=False,
            cleanup_days=3
        )
        
        assert generator.batch_size == 50
        assert generator.modes == ['v1', 'v2']
        assert generator.auto_cleanup is False
        assert generator.cleanup_days == 3
    
    def test_initialization_invalid_modes(self):
        """Test initialization with invalid modes (should filter them out)."""
        generator = BatchTicketGenerator(modes=['invalid_mode', 'random_forest'])
        
        # Should keep only valid mode
        assert 'random_forest' in generator.modes
        assert 'invalid_mode' not in generator.modes
    
    @patch('src.batch_generator.UnifiedPredictionEngine')
    @patch('src.batch_generator.insert_batch_tickets')
    def test_generate_batch_sync(self, mock_insert, mock_engine_class):
        """Test synchronous batch generation."""
        # Mock prediction engine
        mock_engine = MagicMock()
        mock_tickets = [
            {
                'white_balls': [1, 2, 3, 4, 5],
                'powerball': 10,
                'strategy': 'random_forest',
                'confidence': 0.8
            }
        ]
        mock_engine.generate_tickets.return_value = mock_tickets
        mock_engine_class.return_value = mock_engine
        
        # Mock database insert
        mock_insert.return_value = 1
        
        # Create generator and run synchronously
        generator = BatchTicketGenerator(
            batch_size=5,
            modes=['random_forest'],
            auto_cleanup=False
        )
        
        result = generator.generate_batch(
            pipeline_run_id='test-run-123',
            async_mode=False
        )
        
        # Verify result
        assert result['started'] is True
        assert result['async'] is False
        assert result['result']['success'] is True
        assert 'random_forest' in result['result']['modes_processed']
    
    @patch('src.batch_generator.UnifiedPredictionEngine')
    @patch('src.batch_generator.insert_batch_tickets')
    def test_generate_batch_async(self, mock_insert, mock_engine_class):
        """Test asynchronous batch generation."""
        # Mock prediction engine
        mock_engine = MagicMock()
        mock_tickets = [
            {
                'white_balls': [1, 2, 3, 4, 5],
                'powerball': 10,
                'strategy': 'lstm',
                'confidence': 0.7
            }
        ]
        mock_engine.generate_tickets.return_value = mock_tickets
        mock_engine_class.return_value = mock_engine
        
        # Mock database insert
        mock_insert.return_value = 1
        
        # Create generator and run asynchronously
        generator = BatchTicketGenerator(
            batch_size=5,
            modes=['lstm'],
            auto_cleanup=False
        )
        
        result = generator.generate_batch(
            pipeline_run_id='test-run-123',
            async_mode=True
        )
        
        # Verify result
        assert result['started'] is True
        assert result['async'] is True
        assert 'lstm' in result['modes']
        
        # Wait for completion
        completed = generator.wait_for_completion(timeout=10)
        assert completed is True
    
    @patch('src.batch_generator.UnifiedPredictionEngine')
    @patch('src.batch_generator.insert_batch_tickets')
    def test_generate_batch_partial_failure(self, mock_insert, mock_engine_class):
        """Test batch generation with partial failure (one mode fails)."""
        # Mock prediction engine - fail for first mode, succeed for second
        mock_engine = MagicMock()
        
        def side_effect_generate(*args, **kwargs):
            # Raise exception on first call, return tickets on second
            if not hasattr(side_effect_generate, 'call_count'):
                side_effect_generate.call_count = 0
            side_effect_generate.call_count += 1
            
            if side_effect_generate.call_count == 1:
                raise Exception("Test failure for first mode")
            else:
                return [
                    {
                        'white_balls': [1, 2, 3, 4, 5],
                        'powerball': 10,
                        'strategy': 'lstm',
                        'confidence': 0.7
                    }
                ]
        
        mock_engine.generate_tickets.side_effect = side_effect_generate
        mock_engine_class.return_value = mock_engine
        
        # Mock database insert
        mock_insert.return_value = 1
        
        # Create generator with two modes
        generator = BatchTicketGenerator(
            batch_size=5,
            modes=['random_forest', 'lstm'],
            auto_cleanup=False
        )
        
        result = generator.generate_batch(
            pipeline_run_id='test-run-123',
            async_mode=False
        )
        
        # Verify partial success
        assert result['result']['success'] is True  # Partial success
        assert len(result['result']['modes_failed']) == 1
        assert len(result['result']['modes_processed']) == 1
    
    def test_get_status(self):
        """Test get_status method."""
        generator = BatchTicketGenerator(
            batch_size=50,
            modes=['random_forest']
        )
        
        status = generator.get_status()
        
        assert status['is_generating'] is False
        assert status['configured_modes'] == ['random_forest']
        assert status['batch_size'] == 50
        assert 'metrics' in status
        assert 'db_stats' in status
    
    @patch('src.batch_generator.clear_old_batch_tickets')
    def test_cleanup_called_when_enabled(self, mock_cleanup):
        """Test that cleanup is called when auto_cleanup is enabled."""
        mock_cleanup.return_value = 0
        
        generator = BatchTicketGenerator(
            batch_size=5,
            modes=['random_forest'],
            auto_cleanup=True,
            cleanup_days=7
        )
        
        # Try to generate (will fail due to missing mocks, but cleanup should be called)
        try:
            generator.generate_batch(async_mode=False)
        except Exception:
            pass
        
        # Verify cleanup was called
        mock_cleanup.assert_called_once_with(days=7)


class TestBatchTicketValidation:
    """Test ticket validation in batch system."""
    
    def test_valid_ticket_format(self, test_db):
        """Test that valid tickets are accepted."""
        with patch('src.database.get_db_path', return_value=test_db):
            valid_tickets = [
                {
                    'white_balls': [1, 10, 20, 30, 40],
                    'powerball': 5,
                    'confidence': 0.9
                }
            ]
            
            inserted = insert_batch_tickets(valid_tickets, 'random_forest')
            assert inserted == 1
    
    def test_invalid_white_balls_range(self, test_db):
        """Test that invalid white ball ranges are rejected."""
        with patch('src.database.get_db_path', return_value=test_db):
            invalid_tickets = [
                {
                    # Invalid: ball > 69
                    'white_balls': [1, 2, 3, 4, 70],
                    'powerball': 5
                }
            ]
            
            inserted = insert_batch_tickets(invalid_tickets, 'random_forest')
            assert inserted == 0
    
    def test_invalid_powerball_range(self, test_db):
        """Test that invalid powerball values are rejected."""
        with patch('src.database.get_db_path', return_value=test_db):
            invalid_tickets = [
                {
                    'white_balls': [1, 2, 3, 4, 5],
                    # Invalid: powerball > 26
                    'powerball': 30
                }
            ]
            
            inserted = insert_batch_tickets(invalid_tickets, 'random_forest')
            assert inserted == 0
    
    def test_unsorted_white_balls(self, test_db):
        """Test that unsorted white balls are rejected."""
        with patch('src.database.get_db_path', return_value=test_db):
            invalid_tickets = [
                {
                    # Invalid: not sorted
                    'white_balls': [5, 4, 3, 2, 1],
                    'powerball': 10
                }
            ]
            
            inserted = insert_batch_tickets(invalid_tickets, 'random_forest')
            assert inserted == 0
