# Batch Ticket Pre-Generation System

## Overview

The Batch Ticket Pre-Generation System is a professional background processing module that generates lottery tickets using ML models (Random Forest and LSTM), stores them in a database, and provides fast API endpoints for retrieval.

## Architecture

### Components

1. **BatchTicketGenerator** (`src/batch_generator.py`)
   - Background ticket generation using threading
   - Non-blocking execution (daemon threads)
   - Error handling per mode
   - Comprehensive logging and metrics

2. **Database Layer** (`src/database.py`)
   - `pre_generated_tickets` table for cached tickets
   - 5 new database functions:
     - `insert_batch_tickets()` - Save generated tickets
     - `get_cached_tickets()` - Retrieve cached tickets
     - `clear_old_batch_tickets()` - Cleanup old entries
     - `get_batch_ticket_stats()` - Get statistics

3. **API Endpoints** (`src/api_batch_endpoints.py`)
   - `GET /api/v1/tickets/cached` - Fast retrieval (<10ms)
   - `GET /api/v1/tickets/batch-status` - System statistics

4. **Pipeline Integration** (`src/api.py`)
   - Triggers after STEP 6 (prediction generation)
   - Runs in background (non-blocking)
   - Passes pipeline_run_id for tracking

## Features

### 1. Background Processing
- Uses `threading.Thread` with `daemon=True`
- Doesn't block main pipeline or API
- Optimized for 2 CPU cores

### 2. Error Handling
- Per-mode error handling
- If one mode fails, continues with others
- Comprehensive logging
- Non-critical failures don't affect pipeline

### 3. Auto-Cleanup
- Automatically removes tickets older than 7 days
- Configurable cleanup period
- Runs before each batch generation

### 4. Fast Retrieval
- Database-backed caching
- Indexed for fast queries
- Target response time: <10ms

### 5. Metrics and Monitoring
- Generation statistics
- Per-mode metrics
- Database statistics
- Generation history

## Database Schema

```sql
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
);

CREATE INDEX idx_pre_generated_mode ON pre_generated_tickets(mode);
CREATE INDEX idx_pre_generated_created_at ON pre_generated_tickets(created_at DESC);
CREATE INDEX idx_pre_generated_pipeline_run ON pre_generated_tickets(pipeline_run_id);
```

## Usage

### Pipeline Integration

The batch generator is automatically triggered after successful pipeline execution:

```python
# After STEP 6 completes in trigger_full_pipeline_automatically()
from src.batch_generator import BatchTicketGenerator

batch_generator = BatchTicketGenerator(
    batch_size=100,
    modes=['random_forest', 'lstm'],
    auto_cleanup=True,
    cleanup_days=7
)

batch_result = batch_generator.generate_batch(
    pipeline_run_id=execution_id,
    async_mode=True  # Non-blocking
)
```

### Programmatic Usage

```python
from src.batch_generator import BatchTicketGenerator

# Initialize
generator = BatchTicketGenerator(
    batch_size=50,
    modes=['random_forest', 'lstm'],
    auto_cleanup=True
)

# Generate synchronously
result = generator.generate_batch(
    pipeline_run_id='custom-run-123',
    async_mode=False
)

# Generate asynchronously
result = generator.generate_batch(
    pipeline_run_id='custom-run-456',
    async_mode=True
)

# Wait for completion
generator.wait_for_completion(timeout=60)

# Get status
status = generator.get_status()
print(f"Is generating: {status['is_generating']}")
print(f"Metrics: {status['metrics']}")
```

### API Endpoints

#### Get Cached Tickets

```bash
# Get 10 cached random_forest tickets
curl "http://localhost:8000/api/v1/tickets/cached?mode=random_forest&limit=10"

# Response
{
  "mode": "random_forest",
  "count": 10,
  "tickets": [
    {
      "white_balls": [1, 12, 23, 34, 45],
      "powerball": 15,
      "confidence": 0.85,
      "strategy": "random_forest",
      "cached": true,
      "created_at": "2025-11-18T23:50:00"
    },
    ...
  ],
  "cached": true,
  "response_time_ms": 8.5
}
```

#### Get Batch Status

```bash
# Get batch system statistics
curl "http://localhost:8000/api/v1/tickets/batch-status"

# Response
{
  "total_tickets": 200,
  "by_mode": {
    "random_forest": 100,
    "lstm": 100
  },
  "oldest_ticket": "2025-11-11T23:50:00",
  "newest_ticket": "2025-11-18T23:50:00"
}
```

### Database Functions

```python
from src.database import (
    insert_batch_tickets,
    get_cached_tickets,
    clear_old_batch_tickets,
    get_batch_ticket_stats
)

# Insert tickets
tickets = [
    {
        'white_balls': [1, 2, 3, 4, 5],
        'powerball': 10,
        'confidence': 0.8
    }
]
inserted = insert_batch_tickets(tickets, 'random_forest', 'run-123')

# Retrieve cached tickets
cached = get_cached_tickets('random_forest', limit=10)

# Clear old tickets
deleted = clear_old_batch_tickets(days=7)

# Get statistics
stats = get_batch_ticket_stats()
```

## Configuration

### BatchTicketGenerator Parameters

- `batch_size` (int): Number of tickets per mode (default: 100)
- `modes` (List[str]): Prediction modes to use (default: ['random_forest', 'lstm'])
- `auto_cleanup` (bool): Enable auto-cleanup (default: True)
- `cleanup_days` (int): Days to keep tickets (default: 7)

### Supported Modes

- `random_forest` - Random Forest ensemble model
- `lstm` - LSTM neural network model
- `v1` - StrategyManager (legacy)
- `v2` - XGBoost ML model
- `hybrid` - Weighted combination

## Performance

### Benchmarks

- **On-demand generation**: 500-5000ms per request
- **Cached retrieval**: <10ms per request
- **Speedup**: 50-500x faster

### Optimization

- Indexed database queries
- Background generation (doesn't block)
- Auto-cleanup prevents table bloat
- Configurable batch size for resource management

## Error Handling

### Per-Mode Error Handling

If one mode fails, the system continues with others:

```python
# Example: random_forest fails, lstm continues
results = {
    'modes_processed': ['lstm'],
    'modes_failed': ['random_forest'],
    'errors': {
        'random_forest': 'Model not available'
    }
}
```

### Pipeline Integration

Batch generation errors don't affect pipeline success:

```python
try:
    batch_generator.generate_batch(...)
except Exception as e:
    # Log but continue - batch generation is non-critical
    logger.warning(f"Batch generation failed: {e}")
```

## Testing

### Test Coverage

- 25+ unit tests
- Mock-based testing (no external dependencies)
- Coverage includes:
  - Database functions
  - BatchTicketGenerator class
  - Validation logic
  - Error handling
  - Async/sync generation

### Running Tests

```bash
# Run all batch generator tests
pytest tests/test_batch_generator.py -v

# Run specific test
pytest tests/test_batch_generator.py::TestBatchTicketGenerator::test_generate_batch_sync -v

# Run with coverage
pytest tests/test_batch_generator.py --cov=src.batch_generator --cov-report=html
```

### Demo Script

```bash
# Run demonstration
python scripts/demo_batch_generation.py
```

## Security

### Input Validation

- Ticket format validation
- Mode validation (whitelist)
- Range checks (white balls: 1-69, powerball: 1-26)
- SQL injection prevention (parameterized queries)

### Database Constraints

```sql
CHECK (n1 < n2 AND n2 < n3 AND n3 < n4 AND n4 < n5)
CHECK (n1 >= 1 AND n5 <= 69)
CHECK (powerball >= 1 AND powerball <= 26)
CHECK (mode IN ('random_forest', 'lstm', 'v1', 'v2', 'hybrid'))
```

## Monitoring

### Metrics

```python
status = batch_generator.get_status()

# Available metrics:
# - total_runs: Total generation runs
# - successful_runs: Successful runs
# - failed_runs: Failed runs
# - last_run_time: Last run timestamp
# - last_run_status: Last run status
# - last_run_duration: Last run duration
# - tickets_generated: Total tickets generated
# - by_mode: Per-mode statistics
```

### Logging

All operations are logged with appropriate levels:

- `INFO`: Normal operations, generation completion
- `WARNING`: Partial failures, skipped modes
- `ERROR`: Critical failures
- `DEBUG`: Detailed execution traces

## Troubleshooting

### Issue: Batch generation not triggered

**Solution**: Check pipeline completion status. Batch generation only runs after successful pipeline execution.

### Issue: Slow retrieval from cached endpoint

**Solution**: Verify database indexes are created. Run `initialize_database()` to create missing indexes.

### Issue: No tickets available for mode

**Solution**: 
1. Check batch generation logs
2. Verify mode is configured in BatchTicketGenerator
3. Check if tickets were cleaned up (check cleanup_days)

### Issue: High memory usage

**Solution**: Reduce batch_size or limit number of concurrent modes.

## Future Enhancements

### Planned Features

1. **Multiprocessing Support**
   - Use multiprocessing.Pool for CPU-intensive modes
   - Distribute work across CPU cores

2. **Configurable Strategies**
   - Per-mode batch sizes
   - Per-mode cleanup policies
   - Priority-based generation

3. **Advanced Caching**
   - LRU cache for frequently requested modes
   - Pre-warming cache on startup
   - Predictive generation based on usage patterns

4. **Monitoring Dashboard**
   - Real-time generation status
   - Performance metrics visualization
   - Error rate tracking

5. **API Rate Limiting**
   - Prevent cache exhaustion
   - Fair usage policies
   - Quota management

## License

This module is part of SHIOL+ and follows the same license as the main project.

## Support

For issues or questions, please:
1. Check this documentation
2. Review logs in `/var/log/shiolplus/` or `logs/`
3. Run demo script: `python scripts/demo_batch_generation.py`
4. Check test suite: `pytest tests/test_batch_generator.py -v`

## Changelog

### v1.0.0 (2025-11-18)

**Initial Release**
- Background ticket generation with threading
- Database-backed caching
- Fast API endpoints (<10ms)
- Pipeline integration
- Comprehensive test suite
- Auto-cleanup functionality
- Per-mode error handling
- Metrics and monitoring
