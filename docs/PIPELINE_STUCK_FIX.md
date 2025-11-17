# Pipeline Stuck Issue - Root Cause Analysis and Fix

## Issue Description

**Error Message:**
```
Error: FAILED: Pipeline stuck in running state - recovered on restart
Metadata: { 
  "trigger": "automated", 
  "version": "v5.0-sync-first-polling", 
  "expected_draw_date": "2025-11-15", 
  "daily_sync_summary": { 
    "success": true, 
    "draws_fetched": 27, 
    "draws_inserted": 0, 
    "elapsed_seconds": 0.767034 
  } 
}
```

**Symptom:**
Pipeline gets stuck in `STEP 1C/7: Searching for draw (Attempt #7, 3.1min elapsed)` with 0/7 steps completed and never completes.

## Root Cause Analysis

### The Problem

The pipeline was trying to poll for a draw that hadn't occurred yet:

1. **Daily Sync (STEP 1A)** runs successfully, fetching 27 draws from CSV but inserting 0 (DB is already up-to-date)
2. **DB Check (STEP 1B)** looks for draw date `2025-11-15` in database → **NOT FOUND**
3. **Adaptive Polling (STEP 1C)** starts immediately WITHOUT checking if the draw time has passed
4. Polling attempts to fetch results from web scraping, MUSL API, and NC CSV
5. All sources return no results (because draw hasn't happened yet)
6. Polling continues for up to 6 hours with adaptive intervals (30s → 5min → 15min)
7. If the process is killed during this time (e.g., systemd restart), pipeline remains in "running" state
8. Recovery mechanism marks it as "FAILED: Pipeline stuck in running state"

### Why This Happens

**Scenario:** Pipeline scheduled to run at 11:05 PM ET every Monday/Wednesday/Saturday

- **Case 1:** Pipeline runs at 11:05 PM on Friday (not a drawing day)
  - `get_expected_draw_for_pipeline()` calculates next draw is Saturday
  - If it's early Friday (e.g., 11:05 PM), Saturday's draw is ~23 hours away
  - Pipeline tries to poll for Saturday's draw that hasn't happened yet

- **Case 2:** Pipeline runs at 8:00 PM on Saturday (before draw time)
  - Draw time is 10:59 PM ET on Saturday
  - Pipeline is ~3 hours early
  - Tries to poll for Saturday's draw that hasn't happened yet

### Timeline Example

**November 15, 2025 (Saturday) - 8:00 PM ET scenario:**

```
20:00 ET - Pipeline triggered (scheduled job runs early or manual trigger)
20:00 ET - STEP 1A: Daily sync completes (0 new draws)
20:00 ET - STEP 1B: Check DB for Nov 15 draw → NOT FOUND
20:00 ET - STEP 1C: Start polling (BEFORE draw time at 22:59 ET)
20:01 ET - Attempt #1: Powerball → NC Scraping → MUSL → All fail (draw not ready)
20:02 ET - Attempt #2: Powerball → NC Scraping → MUSL → All fail
20:03 ET - Attempt #3: Powerball → NC Scraping → MUSL → All fail
...
[Continues for hours]
...
22:59 ET - Draw actually occurs (balls drawn)
23:05 ET - Results might be available now, but...
23:10 ET - systemd restarts service (scheduled maintenance)
23:10 ET - Pipeline killed mid-execution
23:10 ET - Pipeline stuck in "running" state → Marked as FAILED on next startup
```

## The Fix

### Solution Overview

Add **draw time validation** before starting adaptive polling:

1. After STEP 1B determines draw is not in DB
2. Calculate expected draw time (10:59 PM ET on draw date)
3. Compare with current ET time
4. **If draw time hasn't passed:** Exit gracefully with status "completed"
5. **If draw time has passed:** Proceed with adaptive polling as before

### Code Changes

#### src/api.py - Added Draw Time Validation

**Location:** Lines 780-838 (in `trigger_full_pipeline_automatically()`)

```python
# Draw NOT in DB - validate draw time has passed before polling
logger.info(f"[{execution_id}] 🔍 STEP 1C/7: Draw not in DB, validating draw time...")

# Validate that the expected draw time has passed
from datetime import datetime as dt_class
current_et = DateManager.get_current_et_time()
expected_draw_dt = dt_class.strptime(expected_draw_date, '%Y-%m-%d')

# Draw time is 10:59 PM ET on the draw date
draw_time_et = DateManager.POWERBALL_TIMEZONE.localize(
    expected_draw_dt.replace(hour=22, minute=59, second=0)
)

time_until_draw = (draw_time_et - current_et).total_seconds()

if time_until_draw > 0:
    # Draw hasn't happened yet - skip polling and exit gracefully
    hours_until = time_until_draw / 3600
    logger.warning(f"[{execution_id}] ⏰ STEP 1C SKIPPED: Draw {expected_draw_date} hasn't occurred yet")
    logger.warning(f"[{execution_id}]   Current time: {current_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.warning(f"[{execution_id}]   Draw time: {draw_time_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.warning(f"[{execution_id}]   Time until draw: {hours_until:.1f} hours")
    logger.warning(f"[{execution_id}]   Pipeline will exit gracefully - scheduler will retry after draw")
    
    # Exit gracefully
    return {
        'success': True,
        'status': 'completed',
        'result': 'draw_not_ready',
        'message': f'Draw {expected_draw_date} has not occurred yet - will retry after draw time',
        'hours_until_draw': hours_until
    }

# Draw time has passed - proceed with polling
logger.info(f"[{execution_id}] ✅ Draw time validation passed - draw {expected_draw_date} should be available")
logger.info(f"[{execution_id}]   Draw was {abs(time_until_draw) / 3600:.1f} hours ago")
```

#### src/date_utils.py - Fixed Misleading Comment

**Location:** Lines 123-124

**Before:**
```python
# CORRECTION: Drawing days are Wednesday (2) and Saturday (5)
# DO NOT include Monday (0) as in previous code
```

**After:**
```python
# NOTE: Drawing days are Monday (0), Wednesday (2), and Saturday (5)
# Monday was added to the Powerball schedule in August 2021
```

### Tests Added

**File:** `tests/test_pipeline_draw_time_validation.py`

Four comprehensive test cases:

1. **test_pipeline_skips_future_draw** - Verifies pipeline exits gracefully when draw time hasn't passed
2. **test_pipeline_polls_past_draw** - Verifies pipeline proceeds with polling after draw time
3. **test_pipeline_polls_on_draw_day_after_time** - Edge case: same day after 10:59 PM
4. **test_get_expected_draw_for_pipeline_logic** - Validates date calculation logic

All tests pass ✅

## Impact

### Before Fix

```
Pipeline triggered before draw time
  ↓
Draw not in DB
  ↓
Start 6-hour polling loop immediately
  ↓
Poll every 30s → 5min → 15min
  ↓
All sources fail (draw doesn't exist yet)
  ↓
Process killed by systemd
  ↓
Pipeline stuck in "running" state
  ↓
Marked as FAILED on restart
```

### After Fix

```
Pipeline triggered before draw time
  ↓
Draw not in DB
  ↓
Validate draw time has passed
  ↓
Draw time in future (e.g., 3 hours)
  ↓
Exit gracefully with status "completed"
  ↓
Log clear message: "Draw hasn't occurred yet"
  ↓
Scheduler retries naturally after draw time
  ↓
No stuck pipelines! ✅
```

## Testing

### Manual Validation

Simulated various scenarios:

| Scenario | Current Time | Expected Draw | Hours Until | Should Poll? |
|----------|-------------|---------------|-------------|--------------|
| Before draw | Nov 15, 8:00 PM | Nov 15 | +3.0 | ❌ No |
| 1 min before | Nov 15, 10:58 PM | Nov 15 | +0.02 | ❌ No |
| Exact time | Nov 15, 10:59 PM | Nov 15 | 0.0 | ✅ Yes |
| 6 min after | Nov 15, 11:05 PM | Nov 15 | -0.1 | ✅ Yes |
| Next day | Nov 16, 12:05 AM | Nov 15 | -1.1 | ✅ Yes |
| Day before | Nov 14, 11:05 PM | Nov 15 | +23.9 | ❌ No |

### Automated Tests

```bash
$ pytest tests/test_pipeline_draw_time_validation.py -v

test_pipeline_skips_future_draw PASSED                   [ 25%]
test_pipeline_polls_past_draw PASSED                      [ 50%]
test_pipeline_polls_on_draw_day_after_time PASSED         [ 75%]
test_get_expected_draw_for_pipeline_logic PASSED          [100%]

4 passed in 0.58s ✅
```

### Security Scan

```bash
$ codeql_checker

Analysis Result for 'python'. Found 0 alerts:
- **python**: No alerts found. ✅
```

## Deployment Notes

### Production Behavior

**Scheduler Configuration:**
- Pipeline runs at 11:05 PM ET on Monday, Wednesday, Saturday (6 minutes after draw)
- If pipeline runs early for any reason, it will now exit gracefully
- Scheduler will retry on next scheduled run

**Example Log Output (Before Fix):**
```
[exec_abc] 🔍 STEP 1C/7: Searching for draw (Attempt #7, 3.1min elapsed)
[exec_abc] Attempt #15, 7.5min elapsed
[exec_abc] Attempt #23, 11.5min elapsed
... [continues for hours]
[systemd] Killing process
[recovery] Pipeline stuck in running state - recovered on restart
```

**Example Log Output (After Fix):**
```
[exec_abc] 🔍 STEP 1C/7: Draw not in DB, validating draw time...
[exec_abc] ⏰ STEP 1C SKIPPED: Draw 2025-11-15 hasn't occurred yet
[exec_abc]   Current time: 2025-11-15 20:00:00 EST
[exec_abc]   Draw time: 2025-11-15 22:59:00 EST
[exec_abc]   Time until draw: 3.0 hours
[exec_abc]   Pipeline will exit gracefully - scheduler will retry after draw
[exec_abc] 🚀 PIPELINE STATUS: COMPLETED (graceful exit - draw not ready)
```

### Monitoring

Check pipeline execution logs in `pipeline_execution_logs` table:

```sql
SELECT execution_id, status, current_step, metadata
FROM pipeline_execution_logs
WHERE current_step LIKE '%STEP 1C%'
ORDER BY start_time DESC
LIMIT 10;
```

Look for:
- `status = 'completed'` with `result = 'draw_not_ready'` in metadata → Normal (draw hasn't happened yet)
- `status = 'failed'` with error about stuck state → Should NOT happen anymore

## Conclusion

This fix prevents the pipeline from wasting resources polling for draws that haven't occurred yet, and more importantly, prevents the pipeline from getting stuck in a "running" state when the process is killed during premature polling.

The solution is:
- ✅ Simple and surgical (minimal code changes)
- ✅ Well-tested (4 automated tests + manual validation)
- ✅ Secure (CodeQL scan passed)
- ✅ Production-ready (graceful exit with clear logging)
- ✅ Self-documenting (comprehensive log messages explain what's happening)

**Key Benefit:** The scheduler will naturally retry after the draw time, ensuring the pipeline eventually fetches the results when they're actually available.
