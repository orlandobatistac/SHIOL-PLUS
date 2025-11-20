# SHIOL+ AI Coding Agent Instructions

## 🚨 CRITICAL RULES (ALWAYS FOLLOW)

### 0. **READ PROJECT_ROADMAP_V8.md FIRST** (MANDATORY BEFORE ANY WORK)

**BEFORE implementing any feature, fixing any bug, or writing any code:**

1. **READ** `PROJECT_ROADMAP_V8.md` completely to understand:

   - Current project vision and priorities
   - Active roadmap phases (PHASE 1-7)
   - Which tasks are PENDING, IN PROGRESS, or COMPLETED
   - Architectural decisions and why they were made
   - What NOT to do (deprecated systems, anti-patterns)

2. **VERIFY** your task aligns with roadmap priorities:

   - Is this task in the current active phase?
   - Does it conflict with planned deprecations? (e.g., batch system elimination)
   - Are there dependencies on other incomplete tasks?

3. **CONSULT** roadmap sections relevant to your work:
   - **PHASE 1** (THIS WEEK): Pipeline expansion with 11 strategies
   - **PHASE 2** (THIS WEEK): API for external project
   - **PHASE 3** (NEXT WEEK): Batch system elimination
   - **Architectural Decisions**: Why pipeline-centric, why SQLite, etc.

**Example workflow:**

```bash
# WRONG ❌ - Start coding immediately
git checkout -b feature/add-batch-optimization

# CORRECT ✅ - Read roadmap first
cat PROJECT_ROADMAP_V8.md  # Read completely
# Realize: Batch system is being ELIMINATED (Phase 3)
# Don't waste time optimizing deprecated code!
# Check roadmap: Current priority is PHASE 1 (expand pipeline to 11 strategies)
git checkout -b feature/add-ml-strategies-to-pipeline
```

**Why this matters:**

- Prevents working on deprecated features (e.g., optimizing batch system that will be deleted)
- Ensures alignment with project vision (pipeline-centric, not dual-system)
- Avoids conflicts with ongoing architectural changes
- Saves time by understanding context before coding

---

### 1. **Code Language**: ALL code, methods, functions, classes, variables, comments, and docstrings MUST be written in **English**

- ✅ `def calculate_next_draw()` → Good
- ❌ `def calcular_siguiente_sorteo()` → Never do this
- ✅ `# Calculate frequency distribution` → Good
- ❌ `# Calcular distribución de frecuencia` → Never do this

### 2. **Chat Communication**: Respond to the user (Orlando) in **Spanish (Latin American)**

- When explaining changes, debugging, or discussing architecture → use Spanish
- When writing code or documentation → use English

### 3. **Version Control**: After completing any significant improvement or fix:

- Always create a descriptive commit message (in English)
- Push changes immediately to remote repository
- Example workflow:
  ```bash
  git add .
  git commit -m "feat: add temporal weighting to analytics engine"
  git push origin main
  ```

## Project Overview

SHIOL+ is a production ML-powered lottery analytics platform with **pipeline-centric architecture**. The core mission is adaptive learning: continuously evaluate multiple prediction strategies and automatically adjust their weights based on real-world performance (ROI, win_rate).

**Current Goal (Phase 1)**: Expand from 6 to 11 strategies, integrating ML models (XGBoost, RandomForest, LSTM) as evaluable strategies within the pipeline.

**Stack**: Python 3.10+ | FastAPI | SQLite | APScheduler | XGBoost | RandomForest | LSTM (Keras)

## Architecture Mental Model

### Core Pipeline (5-Step Process) - BRAIN OF THE SYSTEM

The system runs an automated 5-step pipeline orchestrated by `trigger_full_pipeline_automatically()` in `src/api.py`:

1. **DATA**: `update_database_from_source()` fetches draws from MUSL API (primary) or NY State API (fallback)
2. **ANALYTICS**: `update_analytics()` computes co-occurrence matrices and pattern statistics
3. **EVALUATE**: `evaluate_predictions_for_draw()` scores predictions against official results
4. **ADAPTIVE LEARNING**: `adaptive_learning_update()` adjusts strategy weights via Bayesian-like update
5. **PREDICT**: `StrategyManager.generate_balanced_tickets()` generates 200 tickets using weighted strategies (currently 6, expanding to 11)

**Key Point**: ALL predictions from pipeline are evaluable (have `draw_date`), enabling continuous improvement through feedback loop.

### Strategy System (Adaptive Learning, NOT Static Ensemble)

**Critical**: The production system uses **competing strategies with adaptive weights**, NOT a traditional ML ensemble:

- **Current (6 strategies)** in `src/strategy_generators.py`: `FrequencyWeightedStrategy`, `CooccurrenceStrategy`, `CoverageOptimizerStrategy`, `RangeBalancedStrategy`, `AIGuidedStrategy`, `RandomBaselineStrategy`
- **Expansion (5 new strategies)** to be added: `XGBoostMLStrategy`, `RandomForestMLStrategy`, `LSTMNeuralStrategy`, `HybridEnsembleStrategy`, `IntelligentScoringStrategy`
- `StrategyManager` selects strategies proportionally to their `current_weight` (stored in `strategy_performance` table)
- Adaptive learning increases weights of high-performing strategies, decreases weights of poor performers
- `AIGuidedStrategy` wraps `IntelligentGenerator` which uses frequency analysis + deterministic scoring

### Database Schema

SQLite (`data/shiolplus.db`, ~792 KB) with 20+ tables. Key tables:

- `powerball_draws` (1,864 rows): Official results with `pb_era` classification via triggers
- `cooccurrences` (2,346 rows): Statistical pair analysis for `CooccurrenceStrategy`
- `generated_tickets`: **PRIMARY TABLE** - Pipeline predictions (200 tickets/run) with strategy attribution, confidence scores, and draw_date (evaluable)
- `strategy_performance`: Tracks ROI, win_rate, current_weight for adaptive learning (currently 6 rows, will expand to 11)
- `pre_generated_tickets`: **DEPRECATED** - ML cache for batch system (to be phased out in Phase 3)
- `users`, `premium_passes`, `stripe_subscriptions`: Auth and billing state

**Pipeline-Centric Design**:

- **`generated_tickets`**: Core predictions from Pipeline STEP 5, linked to specific `draw_date`, evaluable against official results
- **`pre_generated_tickets`**: Legacy batch cache (random_forest, lstm, v1, v2, hybrid), will be eliminated once ML strategies are integrated into pipeline

**Era-Aware System**: Powerball range changed (1-35 → 1-26 in 2015). Database triggers (`set_pb_era_on_insert`) auto-classify `pb_era` and `pb_is_current`. Analytics code filters to `pb_is_current = 1` to avoid index errors.

### API Architecture

FastAPI app in `src/api.py` with modular routers:

- `api_prediction_endpoints.py`: Prediction generation and draw data
- `api_auth_endpoints.py`: JWT registration/login with bcrypt password hashing
- `api_billing_endpoints.py`: Stripe Checkout + webhook verification + Premium Pass management
- `api_ticket_endpoints.py`: Gemini Vision OCR for uploaded ticket photos
- `api_admin_endpoints.py`: Admin dashboard endpoints (requires `is_admin = True`)
- `api_plp_v2.py`: Feature-flagged PLP v2 API (set `PLP_API_ENABLED=true`)

### Scheduler Configuration

APScheduler with persistent SQLite jobstore (`data/scheduler.db`):

- `post_drawing_pipeline`: Tue/Thu/Sun 1:00 AM ET (full 5-step pipeline after draws)
- `maintenance_data_update`: Tue/Thu/Fri/Sun 6:00 AM ET (data refresh only)
- **Timezone**: All jobs use `America/New_York` via `DateManager` (src/date_utils.py)

## Development Workflows

### Running the Application

```bash
# Local development
python main.py  # Starts Uvicorn on 0.0.0.0:8000

# Environment variables (use .env file)
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=info
MUSL_API_KEY=<required for MUSL API>
```

### Database Initialization

```bash
# Initialize schema (idempotent)
python -c "from src.database import initialize_database; initialize_database()"

# Populate with historical draws
python scripts/update_draws.py

# Run analytics
python -c "from src.analytics_engine import update_analytics; update_analytics()"
```

### Testing

```bash
# Run all tests
pytest tests/

# Specific test file
pytest tests/test_strategy_generators.py -v

# Test with coverage
pytest --cov=src tests/
```

**Test Structure**: `tests/conftest.py` provides fixtures with test DB at `/tmp/shiol_plus_test.db`. Tests use `pytest` fixtures and mock external dependencies (Stripe API, Gemini API).

### Manual Pipeline Execution

```bash
python scripts/run_pipeline.py  # Runs full 5-step pipeline synchronously
```

### Code Quality

```bash
# Linting (relaxed for legacy code)
ruff check src/ tests/

# Type checking (permissive mode)
mypy src/
```

**Style Notes**: Ruff and mypy are configured permissively (`ruff.toml`, `mypy.ini`) due to legacy code. Ignore E501, F401, F841 temporarily. Focus on F-level errors (syntax, undefined names).

## Critical Patterns and Conventions

### 1. Database Connection Management

**Always use `get_db_connection()` context manager**:

```python
from src.database import get_db_connection

with get_db_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT ...")
    conn.commit()
# Connection auto-closes, avoiding locks
```

**Why**: SQLite is single-writer. Context manager ensures connections close promptly. Set `timeout=30` and `busy_timeout=5000` PRAGMA for write contention.

### 2. Date Handling (Critical for Scheduler)

**Always use `DateManager` for date calculations**:

```python
from src.date_utils import DateManager

# Get current ET time
current_et = DateManager.get_current_et_time()

# Calculate next drawing date (Mon/Wed/Sat 10:59 PM ET cutoff)
next_draw = DateManager.calculate_next_drawing_date()

# NEVER use datetime.now() directly for business logic
```

**Why**: Powerball draws are scheduled in ET. Naive datetime leads to off-by-one errors across timezones.

### 3. Strategy Implementation Pattern

When adding new strategies, subclass `BaseStrategy`:

```python
from src.strategy_generators import BaseStrategy
from typing import List, Dict

class MyStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("my_strategy_name")
        # Load data/state if needed

    def generate(self, count: int = 5) -> List[Dict]:
        tickets = []
        for _ in range(count):
            # Generate white balls (1-69, sorted, unique)
            white_balls = sorted(random.sample(range(1, 70), 5))

            # Generate powerball (1-26)
            powerball = random.randint(1, 26)

            tickets.append({
                'white_balls': white_balls,
                'powerball': powerball,
                'strategy': self.name,
                'confidence': 0.5  # 0.0-1.0
            })
        return tickets
```

Register in `StrategyManager.__init__()` and initialize row in `strategy_performance` table.

### 4. Stripe Payment Flow

**Two-step verification** (resilient to webhook delays):

1. **Client-side**: `payment-success.html` polls `/api/v1/billing/status?session_id=...`
2. **Backend**: Fetches session from Stripe API, verifies `payment_status == 'paid'`
3. **Premium activation**: `/api/v1/billing/activate-premium` sets HttpOnly cookie (1-year expiry)
4. **Webhook backup**: `webhook_events` table processes lifecycle events asynchronously

**Why**: Webhooks can't set browser cookies. Direct session verification provides immediate UX.

### 5. Authentication System

- **JWT tokens**: 15-day access tokens, 30-day refresh tokens (httpOnly cookies)
- **Premium Pass**: Separate token system for subscription-based access (jti stored in `premium_passes`)
- **Device tracking**: `device_fingerprint` in `premium_pass_devices` (max 3 devices per pass)
- **Admin access**: Check `users.is_admin` flag, NOT role-based system

### 6. Async Pipeline Safety

Pipeline steps are wrapped in try/except to continue on partial failures:

```python
try:
    # STEP 2: Analytics
    update_analytics()
    db.update_pipeline_execution_log(execution_id, steps_completed=2)
except Exception as e:
    logger.error(f"Analytics failed: {e}")
    db.update_pipeline_execution_log(execution_id, error=str(e))
    # Continue to next step
```

**Why**: Data fetch failures shouldn't abort prediction generation. Log failures and proceed.

### 7. Era-Aware Data Access

When computing Powerball frequencies, **always filter to current era**:

```python
# CORRECT
current_draws = draws[draws['pb_is_current'] == 1]
pb_freq = current_draws['pb'].value_counts()

# WRONG (causes IndexError)
pb_freq = draws['pb'].value_counts()  # Includes PB > 26
```

**Why**: Historical draws have PB ∈ [1, 45]. Current era is PB ∈ [1, 26]. Unfiltered data causes out-of-range array access.

## Common Tasks

### Add New API Endpoint

1. Create function in appropriate `src/api_*_endpoints.py` file
2. Use `@router.get("/path")` or `@router.post("/path")`
3. Import router in `src/api.py` and call `app.include_router(router)`
4. Add authentication decorator if needed: `Depends(get_current_user_from_cookie)`

Example:

```python
# src/api_admin_endpoints.py
@router.get("/stats")
async def get_admin_stats(user: dict = Depends(require_admin)):
    # Implementation
    return {"total_users": count}
```

### Add New Database Table

1. Define schema in `src/database.py` in appropriate `_create_*_tables()` helper
2. Add indexes in `_create_indexes()`
3. Call `initialize_database()` (idempotent - uses CREATE TABLE IF NOT EXISTS)
4. For migrations, use ALTER TABLE with column existence checks via PRAGMA table_info

### Modify Pipeline Behavior

1. Edit `trigger_full_pipeline_automatically()` in `src/api.py`
2. Update step logging via `db.update_pipeline_execution_log(execution_id, current_step="...")`
3. Test with `python scripts/run_pipeline.py`
4. Check `pipeline_execution_logs` table for execution trace

### Debug Strategy Generation

```python
# Test single strategy
from src.strategy_generators import CooccurrenceStrategy
strategy = CooccurrenceStrategy()
tickets = strategy.generate(5)
print(tickets)

# Test full manager
from src.strategy_generators import StrategyManager
manager = StrategyManager()
tickets = manager.generate_balanced_tickets(10)
print([t['strategy'] for t in tickets])  # See distribution
```

### Add Gemini Vision OCR Feature

OCR implementation in `src/ticket_processor.py`:

1. `process_ticket()`: Main entry point accepting PIL Image
2. `_process_with_gemini_ai()`: Structured extraction using Gemini 1.5 Flash
3. `normalize_date()`: Normalizes OCR dates to YYYY-MM-DD
4. `extract_draw_date()`: Regex fallback for OCR failures

**Prompt Engineering**: Gemini prompt in `_process_with_gemini_ai()` requests JSON with `draw_date`, `numbers`, `powerball`. Use specific examples in prompt for better accuracy.

## Deployment Notes

### Production Environment

- Runs on Contabo VPS ($2/month, 1 GB RAM)
- Gunicorn/Uvicorn workers: 2-3 workers max (memory constraint)
- Nginx reverse proxy with Let's Encrypt SSL
- Systemd service: `shiolplus.service`
- Logs: `/var/log/shiolplus/` or `logs/` in repo (configure LOG_LEVEL env var)

### Database Backup

```bash
# Automated backup (add to cron)
cp data/shiolplus.db data/backups/shiolplus_$(date +%Y%m%d_%H%M%S).db
```

### Monitoring

- Health check: `GET /api/v1/health`
- Scheduler status: `GET /api/v1/scheduler/health`
- System metrics: `GET /api/v1/system/stats` (admin only)
- Pipeline execution history: Query `pipeline_execution_logs` table

## Testing Philosophy

- Unit tests in `tests/` use pytest fixtures from `conftest.py`
- Test DB path: `/tmp/shiol_plus_test.db` (ephemeral)
- Mock external APIs (Stripe, Gemini, MUSL) in tests
- Test strategies independently before integration tests
- Coverage focus: strategies, date calculations, auth flows

## Troubleshooting Quick Reference

### "IndexError: index out of bounds" in FrequencyWeightedStrategy

- **Cause**: PB frequency array includes historical ranges (> 26)
- **Fix**: Filter draws to `pb_is_current == 1` in `_calculate_pb_frequencies()`

### Pipeline stuck or jobs not running

- **Cause**: Scheduler timezone mismatch or missed jobs accumulation
- **Fix**: Check `GET /scheduler/health`, verify `timezone="America/New_York"` in job definitions

### Stripe webhook signature failures

- **Cause**: Wrong `STRIPE_WEBHOOK_SECRET` or endpoint URL mismatch
- **Fix**: Verify secret in Stripe Dashboard → Webhooks, ensure endpoint matches deployment URL

### "No official draw results found for date"

- **Cause**: OCR date format not normalized
- **Fix**: Add pattern to `normalize_date()` in `src/ticket_processor.py`

### Database locked errors

- **Cause**: Long-running transaction or missing `conn.close()`
- **Fix**: Always use `with get_db_connection()` context manager, reduce transaction scope

## Key Files Reference

- `src/api.py` (987 lines): Main app, pipeline orchestration, scheduler config
- `src/database.py` (3,268 lines): Schema definitions, DB helpers, migrations
- `src/strategy_generators.py` (527 lines): 6 strategies + StrategyManager
- `src/analytics_engine.py` (265 lines): Co-occurrence and pattern statistics
- `src/intelligent_generator.py` (1,500+ lines): Frequency-based "AI" generator
- `src/date_utils.py`: DateManager for ET timezone calculations
- `src/loader.py` (458 lines): MUSL/NY State API data fetching with smart fallback
- `docs/TECHNICAL.md`: Comprehensive architecture documentation

## External Dependencies to Mock in Tests

- `stripe.checkout.Session.retrieve()`: Stripe API calls
- `google.generativeai.GenerativeModel()`: Gemini Vision API
- `requests.get()`: MUSL/NY State data APIs
- `bcrypt.hashpw()`: Password hashing (use fixture hash)

## Production Deployment Workflow

**IMPORTANT**: No manual `git pull` needed on production server.

Orlando has configured a GitHub Actions workflow that:

1. Detects push to `main` branch
2. Automatically pulls latest code
3. Restarts services (systemd/gunicorn/uvicorn)
4. Syncs changes to production immediately

**Workflow for code changes:**

```bash
# 1. Make changes locally (already done)
# 2. Commit with descriptive message
git add .
git commit -m "feat: your feature description"

# 3. Push to main (this triggers auto-deploy)
git push origin main

# That's it! GitHub Actions handles the rest automatically.
```

**No need to:**

- SSH into production server for code updates
- Manually restart services
- Run database migrations manually (unless specified)

The GitHub Actions will handle deployment within seconds of push.

## Production Server Configuration

### Server Details

- **Location**: `/var/www/SHIOL-PLUS`
- **Python Virtual Environment**: `/root/.venv_shiolplus/`
- **Service Name**: `shiolplus.service`
- **Service File**: `/etc/systemd/system/shiolplus.service`

### Virtual Environment Usage

**To activate venv:**

```bash
source /root/.venv_shiolplus/bin/activate
```

**To run scripts without activating:**

```bash
/root/.venv_shiolplus/bin/python scripts/script_name.py
```

**Example: Create demo user in production:**

```bash
# Option 1: With activation
ssh root@server
cd /var/www/SHIOL-PLUS
source /root/.venv_shiolplus/bin/activate
python scripts/create_demo_user.py

# Option 2: Direct execution
ssh root@server "cd /var/www/SHIOL-PLUS && /root/.venv_shiolplus/bin/python scripts/create_demo_user.py"
```

### Finding the Virtual Environment

If you need to locate the venv in production:

```bash
# Check systemd service configuration
cat /etc/systemd/system/shiolplus.service | grep ExecStart

# Find Python executables
find /var/www/SHIOL-PLUS -type f -name "python*" | grep bin

# Find pyvenv.cfg (venv marker)
find /var/www/SHIOL-PLUS -name "pyvenv.cfg" -type f

# Check running process
ps aux | grep python | grep SHIOL
```

### Demo User Management

**Create demo user in production:**

```bash
ssh root@server
cd /var/www/SHIOL-PLUS
/root/.venv_shiolplus/bin/python scripts/create_demo_user.py
```

**Verify demo user:**

```bash
/root/.venv_shiolplus/bin/python scripts/test_demo_user.py
```

**Demo credentials:**

- Email: `demo@shiolplus.com`
- Username: `demo`
- Password: `Demo2025!`
- Permissions: Admin + Premium (365 days)

---

## 📋 Documentation Maintenance Protocol

**CRITICAL**: After fixing bugs, implementing features, or making architectural changes, AI agents MUST update documentation:

### 1. Update PROJECT_ROADMAP_V8.md (REQUIRED)

**When to update**: After every significant change (bug fix, feature implementation, optimization, completing roadmap tasks)

**What to update**:

- Mark completed tasks: Change `[ ]` to `[x]` and update status from PENDING to COMPLETED
- Add performance metrics (before/after benchmarks) if applicable
- Update "Last Updated" timestamp at bottom of document
- Reference commit hash and related documentation
- Update "PROJECT STATISTICS" section if architecture changed
- Move completed phases from "ACTIVE ROADMAP" to "✅ COMPLETED MILESTONES" section

**Example commit flow**:

```bash
# 1. Make your fix/feature
git add src/your_changes.py

# 2. Update PROJECT_ROADMAP_V8.md
# - Mark task as completed: [ ] → [x]
# - Update status: PENDING → COMPLETED
# - Add metrics if applicable
# - Update timestamp

git add PROJECT_ROADMAP_V8.md

# 3. Commit everything together
git commit -m "feat: add 5 ML strategies to pipeline

- Added XGBoostML, RandomForestML, LSTMNeural, HybridEnsemble, IntelligentScoring
- Pipeline now generates 200 tickets with 11 strategies (~18/strategy)
- All strategies evaluable with draw_date for adaptive learning
- Updated PROJECT_ROADMAP_V8.md to mark Task 1.1 as completed"

git push origin main
```

### 2. Update Technical Documentation (AS NEEDED)

**Files to consider**:

- `docs/TECHNICAL.md` → Architecture changes
- `.github/copilot-instructions.md` → This file, for major architecture shifts
- `README.md` → User-facing changes
- `docs/RANDOM_FOREST_OPTIMIZATION.md` → ML model changes
- Strategy-specific docs if adding new strategies

### 3. Standard Task Completion Template

When marking a roadmap task as COMPLETED in PROJECT_ROADMAP_V8.md, use this format:

```markdown
#### Task X.Y: [Task Name] ✅ COMPLETED

- [x] Subtask 1
- [x] Subtask 2
- [x] Subtask 3

**Implementation Summary:**

- ✅ [What was built/changed]
- ✅ [Files modified]
- ✅ [Tests added]

**Performance Results:** (if applicable)
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| [Metric 1] | [Value] | [Value] | [%] ✅ |

**Commits:**

- [commit hash]: [commit message]

**Time Estimate:** X hours  
**Actual Time:** Y hours  
**Priority:** [CRITICAL/HIGH/MEDIUM/LOW]  
**Status:** ✅ COMPLETED  
**Date Completed:** YYYY-MM-DD
```

### 4. Quick Reference Checklist

After completing a roadmap task:

- [ ] Code changes committed
- [ ] Tests added/updated (if applicable)
- [ ] PROJECT_ROADMAP_V8.md updated:
  - [ ] Task marked as completed: `[ ]` → `[x]`
  - [ ] Status updated: `PENDING` → `✅ COMPLETED`
  - [ ] Date completed added
  - [ ] Performance metrics added (if applicable)
  - [ ] "Last Updated" timestamp updated
- [ ] Related technical docs updated (if architecture changed)
- [ ] Commit message follows conventional commits format (feat:/fix:/docs:/refactor:)
- [ ] All changes pushed to remote
- [ ] Production deployment verified (if applicable)

---

**Last Updated**: 2025-11-19  
**Version**: 8.0 (Strategic Realignment - Pipeline-Centric Architecture)  
**Maintainer**: Orlando B. (orlandobatistac)  
**Roadmap Document**: PROJECT_ROADMAP_V8.md
