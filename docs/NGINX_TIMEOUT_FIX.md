# Nginx 504 Gateway Timeout Fix for Pipeline Trigger

## Problem

When triggering the pipeline manually via the "Run Now" button in the status page (`/api/v1/admin/pipeline/trigger?async_run=true`), users would see a 504 Gateway Timeout error in the browser console, even though the pipeline would complete successfully on the server.

**Error Example:**
```
Failed to load resource: the server responded with a status of 504 (Gateway Time-out)
Error triggering pipeline: Error: Failed to start pipeline: 504
```

## Root Cause

The issue occurred because:

1. **nginx reverse proxy** has a default timeout (typically 60 seconds via `proxy_read_timeout`)
2. The `/api/v1/admin/pipeline/trigger` endpoint was using `asyncio.create_task()` to schedule the pipeline
3. Even though `create_task()` is async, when the coroutine starts executing, it immediately performs blocking database operations:
   - `db.get_latest_draw_date()` - Database query
   - `DateManager.get_expected_draw_for_pipeline()` - Date calculation
   - `db.insert_pipeline_execution_log()` - Database write

4. If these operations took time (e.g., database lock, high load), the HTTP response wouldn't be sent within nginx's timeout window
5. nginx would then return 504 Gateway Timeout to the client
6. Meanwhile, the pipeline would continue running successfully on the server

## Solution

**Changed from:** `asyncio.create_task()` (which starts executing immediately)

**Changed to:** FastAPI's `BackgroundTasks.add_task()` (which guarantees response is sent first)

### Code Changes

**Before:**
```python
async def trigger_pipeline(async_run: bool = True, admin: dict = Depends(require_admin_access)):
    if async_run:
        asyncio.create_task(trigger_full_pipeline_automatically())
        return {"success": True, "message": "Pipeline started", "async": True}
```

**After:**
```python
async def trigger_pipeline(
    background_tasks: BackgroundTasks,
    async_run: bool = True, 
    admin: dict = Depends(require_admin_access)
):
    if async_run:
        background_tasks.add_task(_run_pipeline_in_background)
        return {"success": True, "message": "Pipeline started", "async": True}
```

### How BackgroundTasks Works

FastAPI's `BackgroundTasks` is specifically designed for this use case:

1. The endpoint function completes and returns the response
2. FastAPI sends the HTTP response to the client
3. **Only then** does FastAPI execute the background tasks
4. This guarantees the client gets a response before any long-running work begins

## Benefits

✅ **No more 504 errors** - HTTP response is sent before pipeline starts
✅ **Better user experience** - Users see immediate confirmation that pipeline started
✅ **Same functionality** - Pipeline still runs in background exactly as before
✅ **Proper error handling** - Background task exceptions are logged separately

## Testing

The fix can be verified by:

1. **Manual testing:**
   - Click "Run Now" button in status page
   - Should see immediate success message
   - No 504 error in browser console
   - Pipeline execution shows up in logs within seconds

2. **Automated testing:**
   - Response time should be < 1 second
   - Background task should be scheduled
   - Pipeline should execute after response is sent

## Related nginx Configuration

If you want to increase nginx timeout as a safeguard, you can add to your nginx config:

```nginx
location /api/ {
    proxy_pass http://localhost:8000;
    proxy_read_timeout 300;       # 5 minutes
    proxy_connect_timeout 300;    # 5 minutes
    proxy_send_timeout 300;       # 5 minutes
}
```

However, with the `BackgroundTasks` fix, this should no longer be necessary for the pipeline trigger endpoint.

## References

- [FastAPI BackgroundTasks documentation](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- Issue: 504 Gateway Timeout on manual pipeline trigger
- Fix commit: `d1ba27b` - Fix 504 Gateway Timeout on pipeline trigger by using FastAPI BackgroundTasks

## Date

Fixed: 2024-11-17
Version: SHIOL+ v6.x
