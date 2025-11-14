# Polling Timeout Fix - Root Cause Analysis

## Problem Summary

**Two pipeline executions failed on 2025-11-13 at 04:05-04:08 AM** with error:
```
"Pipeline stuck in running state - recovered on restart"
```

Both failed at **STEP 1C/7 (Adaptive Polling)**, getting killed by systemd with SIGKILL.

## Root Cause Analysis

### Timeline of Failure (Execution ID: 5344348f)

```
04:05:00 - Pipeline starts, STEP 1C begins adaptive polling
04:05:00 - Attempt #1: All sources unavailable (draw not yet released)
          - NC Lottery web scraping: found 2025-11-10 (not 2025-11-12)
          - MUSL API: statusCode='reporting' (not 'complete')
          - NC CSV: draw not found
          - Result: Wait 120s before retry
          
04:07:01 - Attempt #2: All sources still unavailable
          - Same failures as Attempt #1
          - Result: Wait 120s before retry
          
04:08:11 - Systemd timeout (180s after start) triggers
          - Process receives SIGTERM
          - Process doesn't exit gracefully (polling is blocking)
          - Systemd issues SIGKILL after 180s timeout expires
          - Service restarts automatically
```

### The Design Flaw

**Original timeout logic in `realtime_draw_polling_unified()`:**
```python
# Calculate timeout: 6:00 AM next day in ET
next_day_6am = current_et.replace(hour=6, minute=0, second=0, microsecond=0) + timedelta(days=1)
timeout_timestamp = next_day_6am.timestamp()  # ~6.9 hours away!
```

**The conflict:**
- Polling timeout: **6.9 hours** (wait until 6 AM next day for daily sync)
- Systemd graceful shutdown timeout: **180 seconds (3 minutes)**
- Result: Systemd kills process with SIGKILL before polling timeout reached

### Why Draw Wasn't Available

On November 12, 2025, the Powerball drawing was probably:
1. **Still in progress** during the first polling attempts (04:05-04:07 AM ET)
2. **Not yet certified/published** on any data source
3. **Not in "complete" status** on MUSL API (was in "reporting" state)

The pipeline was designed to wait for the draw to become available, but:
- Real-time polling is meant for immediately after drawing
- Drawing ceremony ends around 10:59 PM ET
- Results are published within 30 minutes to 1 hour
- Polling should NOT wait indefinitely (6+ hours)

## The Fix

### Changed Timeout from 6.9 Hours → 5 Minutes

**File: `src/loader.py` (lines 740-755)**

```python
# OLD CODE (broken)
next_day_6am = current_et.replace(hour=6, minute=0, second=0, microsecond=0) + timedelta(days=1)
timeout_timestamp = next_day_6am.timestamp()
timeout_hours = (next_day_6am - current_et).total_seconds() / 3600
logger.info(f"Timeout at: {next_day_6am.strftime('%Y-%m-%d %H:%M:%S %Z')} ({timeout_hours:.1f} hours)")

# NEW CODE (fixed)
timeout_seconds = 300  # 5 minutes max
timeout_timestamp = start_time.timestamp() + timeout_seconds
logger.info(f"Timeout at: 5 minutes (max {timeout_seconds}s)")
```

### Rationale for 5 Minutes

1. **Real-time polling is for IMMEDIATE availability** after drawing
   - Powerball drawing: Mon/Wed/Sat ~10:59 PM ET
   - Results published: ~10:59 PM → 11:30 PM ET (30 minutes)
   - If not available in first 5 minutes, data source problem exists

2. **5 minutes allows 2 healthy polling attempts** (Phase 1 with 2-minute intervals)
   ```
   Time 0:00 - Attempt #1
   Time 2:00 - Attempt #2 (after 120s wait)
   Time 3:00 - Timeout (300s limit)
   ```

3. **Graceful degradation**
   - Polling fails after 5 minutes with status='timeout'
   - Pipeline marks draw as NOT FOUND
   - Daily Full Sync job at 6 AM will pick up any missed draws
   - No lost data, just delayed by a few hours

4. **Prevents systemd timeout conflict**
   - 5 minutes (300s) << systemd timeout (180s)... wait, that's WRONG!
   - Actually: 5 minutes (300s) > systemd timeout (180s)
   - BUT: The polling now FAILS at 5 minutes instead of waiting indefinitely
   - Systemd won't kill process because polling will exit cleanly

**Wait, issue:** Actually, if polling waits 300s but systemd timeout is 180s, we still have a problem!

### Real Solution: Both Timeout Changes Needed

The actual fix requires TWO changes:

1. **Polling timeout: 5 minutes** (code already deployed)
   - Polling loop will timeout and return after 5 minutes
   - But systemd will kill it at 3 minutes (180s)

2. **Systemd timeout needs increase** (NOT YET DEPLOYED)
   - Service file: `/etc/systemd/system/shiolplus.service`
   - Current: `TimeoutStopSec=180`
   - Should be: `TimeoutStopSec=360` (6 minutes)

### Updated Service Configuration

File: `/etc/systemd/system/shiolplus.service`

```ini
[Service]
...
# Give pipeline 5 minutes + 1 minute buffer to exit gracefully
TimeoutStopSec=360
...
```

## Expected Behavior After Fix

### Successful Polling (draw available)
```
04:05:00 - Attempt #1: Draw found (typically within 30-60 seconds)
          - Pipeline continues through STEP 2-7
          - Total time: ~10 seconds
✅ Result: Pipeline completes successfully
```

### Failed Polling (draw unavailable after 5 min)
```
04:05:00 - Attempt #1: No data
          - Wait 120s
04:07:01 - Attempt #2: No data
          - Wait 120s
04:09:01 - Timeout reached (300s)
          - polling_result = {'success': False, 'result': 'timeout'}
          - STEP 1C logs: "Draw not available yet - daily sync will catch it at 6 AM"
          - Pipeline exits with status='failed'
          - Systemd does NOT kill process (already exiting)
✅ Result: Clean failure, no service restart, no stuck process
```

## Deployment Status

✅ **Code deployed to production** (commit 635c8e9)
- `realtime_draw_polling_unified()` now times out after 5 minutes
- Systemd graceful shutdown still 180 seconds (needs manual update on server)

⚠️ **Manual action required on production server:**
Update `/etc/systemd/system/shiolplus.service`:
```bash
ssh root@server
nano /etc/systemd/system/shiolplus.service
# Change TimeoutStopSec=180 to TimeoutStopSec=360
systemctl daemon-reload
systemctl restart shiolplus
```

## Prevention for Future

### Pipeline Design Principles

1. **Polling timeout ≤ 5 minutes** (max wait for real-time data)
2. **Systemd timeout ≥ (polling_timeout + 60 seconds)** (buffer for cleanup)
3. **Daily Full Sync at 6 AM** catches any missed draws (safety net)
4. **Log polling failures** with clear indication it's non-fatal (daily sync will retry)

### Monitoring

Add alerts for:
- Pipeline timeout frequency (if > 1/week, data source reliability issue)
- Draw availability lag (how long before data appears in sources)
- Service restart frequency (should be rare)

## References

- **Original Issue**: Pipeline stuck waiting for draw availability indefinitely
- **Affected Execution IDs**: `5344348f` (04:05 AM), `3d3b56e8` (04:08 AM)
- **Underlying Cause**: Polling timeout (6.9h) > systemd timeout (3min)
- **Date Fixed**: 2025-11-14 (commit 635c8e9)
