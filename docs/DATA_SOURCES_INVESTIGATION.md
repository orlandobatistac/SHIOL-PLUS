# Data Source Investigation Summary

## 🔍 Investigation Results

### Local Environment
- ✅ **MUSL API**: Configured and working
- ✅ **Database State**: CURRENT (latest draw 2025-11-03)
- ✅ **API Selection**: Using MUSL (primary for incremental updates)
- ✅ **Behavior**: CORRECT

### Why NY State is Being Used

The system has intentional logic for API selection:

```
IF DB is EMPTY or STALE (>1 day):
  → Use NY State API (bulk historical data for recovery)
  → Fallback to MUSL if NY State fails

IF DB is CURRENT:
  → Use MUSL API (incremental, single latest draw - faster)
  → Fallback to NY State if MUSL fails or not configured
```

Orlando sees NY State being used, which means ONE of these is true:

1. **DB is STALE/EMPTY in production**
   - This is EXPECTED behavior (NY State used for bulk recovery)
   - Once DB becomes current, MUSL will be used
   
2. **MUSL_API_KEY not configured in production**
   - Check: `echo $MUSL_API_KEY` on production server
   - If empty, add to `.env` or production secrets and restart
   
3. **MUSL API not accessible from production server**
   - Network/firewall issue
   - Run `diagnose_api_sources.py` in production to verify

## 📋 Diagnostic Scripts Created

Two new diagnostic scripts:

### 1. `scripts/diagnose_api_sources.py`
Tests both API connections directly:
```bash
python3 scripts/diagnose_api_sources.py
```

### 2. `scripts/diagnose_pipeline_sources.py`
Shows which source pipeline WILL use based on DB state:
```bash
python3 scripts/diagnose_pipeline_sources.py
```

## ✅ Recommendations for Orlando

### Immediate Action
SSH to production and run:
```bash
cd /var/www/SHIOL-PLUS
python3 scripts/diagnose_pipeline_sources.py
```

This will tell you:
- Is MUSL_API_KEY configured?
- What's the DB state?
- Which strategy will be used?

### Expected Results
If DB is CURRENT and MUSL_API_KEY is set → Should show MUSL being used
If DB is STALE or EMPTY → Will show NY State (this is CORRECT)

### If MUSL is Not Available
1. Verify MUSL_API_KEY is in production environment
2. If not, add it to `/etc/environment` or restart systemd service with env var
3. If network is blocked, work with infrastructure to allow access to `https://api.musl.com`

## 🔄 Data Source Priority

### For Quick/Incremental Updates (Default)
**MUSL API** → Faster, single latest draw, ideal for scheduled jobs

### For Bulk/Recovery
**NY State API** → Slower, but provides full history, used when DB stale/empty

## 📊 Current System Health

- ✅ Both APIs functional locally
- ✅ Pipeline logic correct
- ✅ DB schema matches code
- ✅ Fallback mechanism working

The system is designed to be RESILIENT - using NY State as fallback ensures data always updates even if MUSL is temporarily down.
