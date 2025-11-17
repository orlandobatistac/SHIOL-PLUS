# SHIOL+ Enhanced Pipeline - Technical Documentation

**Version**: 2.0 (October 2025)  
**Author**: Orlando B.  
**Repository**: [github.com/orlandobatistac/SHIOL-PLUS](https://github.com/orlandobatistac/SHIOL-PLUS)

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Database Schema & Design](#2-database-schema--design)
3. [Enhanced Pipeline (5-Step Process)](#3-enhanced-pipeline-5-step-process)
4. [Strategy Implementations](#4-strategy-implementations)
   - 4.1 Base Strategy
   - 4.2 FrequencyWeightedStrategy
   - 4.3 CooccurrenceStrategy
   - 4.4 CoverageOptimizerStrategy
   - 4.5 RangeBalancedStrategy
   - 4.6 AIGuidedStrategy
   - 4.7 RandomBaselineStrategy
5. [Co-occurrence Analysis Algorithm](#5-co-occurrence-analysis-algorithm)
6. [Adaptive Learning System](#6-adaptive-learning-system)
7. [Era-Aware Data System](#7-era-aware-data-system)
8. [API Reference](#8-api-reference)
9. [Testing & Development](#9-testing--development)
10. [Deployment & Operations](#10-deployment--operations)

---

## 1. Architecture Overview

### 1.1 System Components

The system is split into a concise set of components that orchestrate data ingestion, analytics, strategy generation, evaluation, and serving. The major components and their responsibilities are:

- Loader (src/loader.py): fetches and normalizes draw data from external APIs (MUSL primary, NY State fallback) and writes to the SQLite database.
- Database (src/database.py): schema management, helpers, and analytics storage (cooccurrences, patterns, strategy_performance, generated_tickets, predictions_log, etc.).
- Analytics Engine (src/analytics_engine.py): computes co-occurrence matrices and pattern statistics and writes them back to the DB.
- Strategy Manager & Generators (src/strategy_generators.py): the six strategies and orchestration logic used to generate predictions.
- API (src/api.py + endpoint routers): pipeline orchestration, endpoints for generating predictions, evaluation, and system health.

Component diagram (conceptual):

```
┌─────────────────────────────────────────────────┐
│              SHIOL+ SYSTEM                      │
├─────────────────────────────────────────────────┤
│  [MUSL API] → [Loader] → [Database]             │
│                     ↓                           │
│              [Analytics Engine]                 │
│                     ↓                           │
│              [Strategy Manager]                 │
│                     ↓                           │
│              [6 Strategies] → [Prediction API]  │
└─────────────────────────────────────────────────┘
```

### 1.2 Data Flow

1. MUSL API → Loader parses JSON → inserts into `powerball_draws` (triggers classify era)
2. Analytics Engine reads `powerball_draws`, computes co-occurrence and pattern statistics, writes `cooccurrences` and `pattern_stats`
3. StrategyManager loads weights from `strategy_performance`, calls strategies to generate tickets (saved to `generated_tickets`)
4. After official draw results exist, predictions are evaluated; results persist in `performance_tracking` and `predictions_log`
5. Adaptive learning calculates ROI/weights and updates `strategy_performance`

### 1.3 File Structure (core files & sizes)

Relevant source files analyzed (lines):

```
src/api.py                    # 987 lines - pipeline orchestration, scheduler, endpoints
src/database.py               # 2,587 lines - schema, DB helpers, migration logic
src/analytics_engine.py       # 265 lines - co-occurrence + pattern statistics
src/strategy_generators.py    # 527 lines - 6 strategies and StrategyManager
src/loader.py                 # 458 lines - data fetch & transform
src/auth_middleware.py        # 376 lines - JWT/premium/pass/session handling
data/shiolplus.db             # 792 KB (binary SQLite file)
```

---

## 2. Database Schema & Design

All schema and table definitions are implemented in `src/database.py`. The repository's live database contains the following main tables (as of inspection):

```
adaptive_weights            premium_passes            
cooccurrences               pwa_installs             
generated_tickets           reliable_plays           
idempotency_keys            strategy_performance     
ip_rate_limits              stripe_customers         
model_feedback              stripe_subscriptions     
pattern_analysis            system_config            
pattern_stats               unique_visits            
performance_tracking        users                    
pipeline_executions         validation_results       
powerball_draws             webhook_events           
predictions_log             weekly_verification_limits
premium_pass_devices
```

Row counts for key tables (live DB):

- `powerball_draws`: 1,851 rows
- `cooccurrences`: 2,346 rows (C(69,2))
- `strategy_performance`: 6 rows (one per strategy)

### 2.1 powerball_draws Table

Schema excerpt (created during initialization):

```sql
CREATE TABLE powerball_draws (
    draw_date DATE PRIMARY KEY,
    n1 INTEGER NOT NULL,
    n2 INTEGER NOT NULL,
    n3 INTEGER NOT NULL,
    n4 INTEGER NOT NULL,
    n5 INTEGER NOT NULL,
    pb INTEGER NOT NULL
    , pb_is_current INTEGER DEFAULT 0, pb_era TEXT DEFAULT 'unknown'
);
```

Notes:
- `pb_is_current` and `pb_era` were added during a non-destructive migration to guard PB-range changes across eras.
- Indexes are created for `draw_date`, `pb_era`, and `pb_is_current`.

### 2.2 cooccurrences Table

Excerpt (analytics tables are created via `create_analytics_tables()`):

```sql
CREATE TABLE cooccurrences (
    number_a INTEGER NOT NULL,
    number_b INTEGER NOT NULL,
    count INTEGER DEFAULT 0,
    expected REAL DEFAULT 0.0,
    deviation_pct REAL DEFAULT 0.0,
    is_significant BOOLEAN DEFAULT FALSE,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (number_a, number_b),
    CHECK (number_a >= 1 AND number_a <= 69),
    CHECK (number_b >= 1 AND number_b <= 69),
    CHECK (number_a < number_b)
);
```

The analytics engine computes counts for all 2,346 unique pairs (C(69,2)) and stores expected values and percentage deviations.

### 2.3 strategy_performance Table

Schema excerpt:

```sql
CREATE TABLE strategy_performance (
    strategy_name TEXT PRIMARY KEY,
    total_plays INTEGER DEFAULT 0,
    total_wins INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0.0,
    total_prizes REAL DEFAULT 0.0,
    total_cost REAL DEFAULT 0.0,
    roi REAL DEFAULT 0.0,
    avg_prize REAL DEFAULT 0.0,
    current_weight REAL DEFAULT 0.1667,
    confidence REAL DEFAULT 0.5,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

This table is central to the adaptive learning system; the pipeline updates `current_weight` and `confidence` based on `total_plays`, `total_wins`, and calculated ROI.

### 2.4 Generated Tickets & Predictions

- `generated_tickets`: stores generated tickets (strategy attribution, confidence, draw_date). The table enforces sorted unique white-balls and PB range (1..26).
- `predictions_log`: stores prediction metadata and dataset hashes (used for reproducibility and evaluation).
- `performance_tracking`: stores evaluation results for predictions after an official draw.

### 2.5 Triggers

`create_pb_era_triggers()` creates 2 triggers:

- `set_pb_era_on_insert` (AFTER INSERT): computes `pb_is_current` and `pb_era` using PB ranges and updates the inserted row.
- `set_pb_era_on_update` (AFTER UPDATE OF pb): re-classifies if PB value changes.

Trigger logic uses PB numeric ranges to map to era labels like '2015-now (1-26)', '2012-2015 (1-35)', etc.

---

## 2.6 Data Source Fallback System (v6.3)

**Version**: 6.3 (October 2025)  
**Implementation**: `src/loader.py`

### 2.6.1 Overview

SHIOL+ uses a **smart dual-source data loading system** to ensure reliable Powerball draw data availability. The system automatically selects the optimal data source based on database state and provides automatic failover between sources.

**Data Sources**:
- **MUSL API** (Multi-State Lottery Association) - Official primary source
  - URL: `https://api.musl.com/v3/numbers?GameCode=powerball`
  - Auth: `MUSL_API_KEY` environment variable
  - Returns: Single latest draw (incremental updates)
  - Best for: Regular maintenance, current data checks
  
- **NY State Open Data API** - Public fallback/bulk source
  - URL: `https://data.ny.gov/resource/d6yy-54nr.json`
  - Auth: Optional `NY_OPEN_DATA_APP_TOKEN` for higher rate limits
  - Returns: Up to 5000 historical draws
  - Best for: Initial population, recovery, bulk refresh

### 2.6.2 Intelligent Source Selection

The system implements a **state-based orchestration strategy** in `update_database_from_source()`:

```python
# Phase 1: Analyze database state
latest_date = get_latest_draw_date()
is_stale = _is_database_stale(latest_date, threshold_days=1)

# Determine state
if latest_date is None:
    state = "EMPTY"
elif is_stale:
    state = "STALE"  # Latest draw >1 day old
else:
    state = "CURRENT"  # Fresh data
```

**Decision Matrix**:

| Database State | Primary Source | Reason | Fallback |
|---------------|----------------|--------|----------|
| **EMPTY** | NY State API | Need full historical data (~5000 draws) | MUSL API (get at least 1 draw) |
| **STALE** (>1 day) | NY State API | Full refresh recommended for recovery | MUSL API (incremental) |
| **CURRENT** | MUSL API | Efficient incremental check (1 draw) | NY State API (full dataset) |

### 2.6.3 Implementation Details

**Key Functions**:

1. **`_is_database_stale(latest_date_str, staleness_threshold_days=1)`**
   - Compares latest draw date with current ET time
   - Returns `True` if DB is empty or latest draw is older than threshold
   - Uses `DateManager` for timezone-aware calculations

2. **`_fetch_from_musl_api()`**
   - Fetches latest draw from MUSL
   - Requires `MUSL_API_KEY` env variable
   - Returns single draw in list format
   - 15-second timeout with graceful failure

3. **`_fetch_from_nystate_api()`**
   - Fetches up to 5000 historical draws
   - Optional `NY_OPEN_DATA_APP_TOKEN` for authenticated requests
   - Orders by `draw_date DESC` for latest-first
   - 30-second timeout with graceful failure

4. **`update_database_from_source()`** (orchestrator)
   - Phase 1: Analyze DB state (EMPTY/STALE/CURRENT)
   - Phase 2: Smart source selection with automatic fallback
   - Phase 3: Transform API data to standardized format
   - Phase 4: Filter new draws (avoid duplicates)
   - Phase 5: Bulk insert with pb_era metadata update
   - Phase 6: Return total draw count

### 2.6.4 Fallback Behavior

**Scenario 1: EMPTY/STALE DB - NY State failure**
```
1. Try NY State API → FAIL
2. Log warning: "NY State API failed, falling back to MUSL..."
3. Try MUSL API → SUCCESS (get 1 draw)
4. Result: DB populated with at least latest draw
```

**Scenario 2: CURRENT DB - MUSL failure**
```
1. Try MUSL API → FAIL (no API key or network issue)
2. Log warning: "MUSL API failed, falling back to NY State..."
3. Try NY State API → SUCCESS (get all draws)
4. Result: DB updated with complete dataset
```

**Scenario 3: Both APIs fail**
```
1. Primary source → FAIL
2. Fallback source → FAIL
3. Log error: "Both APIs failed - no data available"
4. Return current draw count (no crash, graceful degradation)
```

### 2.6.5 Logging & Observability

The system provides comprehensive logging at each decision point:

```
============================================================
Starting intelligent data update process...
============================================================
📊 Database State: EMPTY
   Latest draw date: None
🔄 Strategy: NY State API (bulk historical data)
   Reason: Database is empty or stale - need full refresh
✅ NY State API success: 1853 draws fetched
📊 Transformed 1853 valid draws
🆕 Populating empty DB with 1853 draws
🔧 Updated pb_era metadata for 1853 draws
============================================================
✅ Data update complete: 1853 total draws in database
============================================================
```

### 2.6.6 Integration Points

The `update_database_from_source()` function is called from:

1. **scripts/update_draws.py** - Manual DB initialization
2. **scripts/run_pipeline.py** - Full pipeline execution (now with STEP 0)
3. **src/api.py scheduler** - **v3.1 Smart Polling Configuration:**
   - `post_drawing_pipeline` (Tue/Thu/Sun **11:05 PM ET**) - Full pipeline with STEP 0 (Smart Polling)
   - ~~`maintenance_data_update`~~ - **REMOVED** in v3.1 (redundant with 120min polling)
   - `maintenance_data_retry` (Tue/Thu/Sun 11:35 PM ET) - Backup data refresh (30min after start)

**Scheduler Changes in v3.1:**
- Pipeline now starts **11:05 PM** (6 min after 10:59 PM draw) instead of 1:00 AM
- STEP 0 polls MUSL API with infinite attempts and 120-minute timeout
- Removed `maintenance_data_update` job (no longer needed - polling guarantees data)
- Results available ~10-15 minutes after draw (vs 2+ hours before)

All integration points benefit from the smart source selection automatically.

### 2.6.7 Performance & Rate Limits

**MUSL API**:
- Rate limit: Dependent on API key tier
- Response time: ~200-500ms
- Data size: ~2KB per draw

**NY State Open Data API**:
- Rate limit: 1000 requests/day (no token), 10,000/day (with token)
- Response time: ~300-800ms for 5000 draws
- Data size: ~500KB for full dataset
- No authentication required (public API)

**Recommendation**: Set `NY_OPEN_DATA_APP_TOKEN` for production to ensure higher rate limits for recovery scenarios.

### 2.6.8 Testing

The system was validated across three scenarios:

1. ✅ **Empty Database Test**
   ```bash
   rm data/shiolplus.db
   python scripts/update_draws.py
   # Result: NY State API → 1853 draws inserted
   ```

2. ✅ **Stale Database Test**
   ```python
   # Set latest draw to 3 days ago
   update_database_from_source()
   # Result: STALE detected → NY State API → new draws added
   ```

3. ✅ **Current Database Test**
   ```bash
   # No MUSL_API_KEY set
   update_database_from_source()
   # Result: MUSL failed → NY State fallback → success
   ```

---

## 3. Enhanced Pipeline v3.1 (6-Step Process with Smart Polling)

The orchestrator lives primarily in `src/api.py` (`trigger_full_pipeline_automatically()`), which performs the six steps:

0. **SMART POLLING** — `wait_for_draw_results()` (src/loader.py) — **NEW in v3.1**
1. **DATA** — `update_database_from_source()` (src/loader.py)
2. **ANALYTICS** — `update_analytics()` (src/analytics_engine.py)
3. **EVALUATE** — `evaluate_predictions_for_draw()` (src/api.py)
4. **ADAPTIVE LEARNING** — `adaptive_learning_update()` (src/api.py)
5. **PREDICT** — `StrategyManager.generate_balanced_tickets()` (src/strategy_generators.py)

### 3.1 STEP 0: Smart Polling System (NEW in v3.1)

**Purpose:** Intelligently wait for MUSL API to publish draw results instead of using fixed delay.

**Timeline:**
- **Before v3.1:** Pipeline started at 1:00 AM (2 hours after 10:59 PM draw)
- **v3.1:** Pipeline starts at 11:05 PM (6 minutes after draw), polls until data available

**Implementation:** `wait_for_draw_results()` in `src/loader.py`

```python
def wait_for_draw_results(
    expected_draw_date: str,
    check_interval_seconds: int = 120,  # 2 minutes
    timeout_minutes: int = 120           # 2 hours
) -> Dict[str, any]
```

**Behavior:**
- Starts polling MUSL API at 11:05 PM ET (configurable via `POLLING_START_MINUTES_AFTER_DRAW`)
- Checks API every 2 minutes (configurable via `POLLING_INTERVAL_SECONDS`)
- **Infinite attempts** until timeout (no max_attempts limit)
- Timeout: 120 minutes (configurable via `POLLING_TIMEOUT_MINUTES`)
- Returns summary dict with key metrics (attempts, elapsed_seconds, result, data_available_at)

**Data Storage:**
- **Metadata JSON only** (no separate database table)
- Summary stored in `pipeline_execution_logs.metadata.polling_summary`:

```json
{
  "polling_summary": {
    "enabled": true,
    "result": "complete",              // "complete", "timeout", or "error"
    "attempts": 3,                     // Total API checks performed
    "elapsed_seconds": 245.7,          // Time from start to finish
    "started_at": "2025-11-05T23:05:00Z",
    "completed_at": "2025-11-05T23:09:15Z",
    "final_status_code": "complete"    // Last statusCode from MUSL API
  }
}
```

**File Logs:**
- All intermediate polling attempts logged to `logs/shiolplus.log`
- Example: `[polling] Attempt #1 at 23:05:00 → statusCode: "processing" (265ms)`

**Error Handling:**
- STEP 0 is **NON-CRITICAL**: Exceptions logged but don't halt pipeline
- Timeout or errors trigger fallback to standard data fetch in STEP 1
- Missing `MUSL_API_KEY` returns error immediately (no polling)

**Benefits:**
- ⚡ **1h 50min faster** predictions (available ~11:09 PM vs 1:00 AM)
- 🎯 **Guaranteed execution** (120min timeout covers any realistic delay)
- 📊 **Observability** (polling metrics visible in frontend and logs)
- 🧹 **Simplified scheduler** (removed redundant maintenance job)

**Frontend Display:**
- Admin dashboard (`/status.html`) shows polling summary
- Example: "🔍 STEP 0: Smart Polling ✅ Available • 3 attempts in 4.5 minutes"

### 3.2 Sequence and resilience

- Each step is wrapped with try/except. Failures don't abort the whole pipeline; the pipeline logs and proceeds to next steps where possible.
- Scheduler uses APScheduler with a persistent SQLite jobstore (`data/scheduler.db`).
- **v3.1 Scheduler Update:**
  - `post_drawing_pipeline`: Now runs at **11:05 PM** (was 1:00 AM)
  - Removed `maintenance_data_update` job (redundant with 120min polling)
  - Kept `maintenance_data_retry` as backup (11:35 PM)

### 3.3 Key orchestration points (practical notes)

- The orchestrator expects the `DateManager` (src/date_utils.py) to compute the next drawing date reliably; failing that, it logs and uses fallbacks.
- Generated ticket persistence is handled by `save_generated_tickets()` (in `src/api.py`), which inserts records into `generated_tickets`.
- Evaluation writes to `performance_tracking` and updates `predictions_log` with evaluation results and prize amounts.
- **v3.1:** STEP 0 calculates `expected_draw_date` from `DateManager.get_recent_drawing_dates(count=1)`

---

## 4. Strategy Implementations

All strategies implement `BaseStrategy` (src/strategy_generators.py). Each strategy returns a list of ticket dictionaries of the shape:

```python
{
  'white_balls': [n1, n2, n3, n4, n5],
  'powerball': pb,
  'strategy': strategy_name,
  'confidence': float
}
```

### 4.1 Base Strategy Interface

`BaseStrategy` provides `generate(count)` and `validate_ticket()` and loads draws via `get_all_draws()`.

### 4.2 FrequencyWeightedStrategy

- Uses historical frequencies of white balls (1–69) across `powerball_draws`.
- For Powerball (pb 1–26), it filters draws to current-era (PB ∈ [1,26]) to compute PB frequencies and avoid index errors.
- Sampling uses numpy's `np.random.choice` with `replace=False` and a normalized frequency vector for white balls.

Key safety and fixes:
- The implementation validates PB frequency array length and sums; when invalid, it falls back to uniform sampling.

### 4.3 CooccurrenceStrategy

This strategy leverages statistically significant number pairs saved in `cooccurrences`.

Implementation highlights (from `src/strategy_generators.py`):

```python
class CooccurrenceStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("cooccurrence")
        self.strong_pairs = self._get_strong_pairs()

    def _get_strong_pairs(self) -> List[Tuple[int, int]]:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT number_a, number_b
                FROM cooccurrences
                WHERE is_significant = TRUE AND deviation_pct > 20
                ORDER BY deviation_pct DESC
                LIMIT 50
            """)
            pairs = [(row[0], row[1]) for row in cursor.fetchall()]
            conn.close()
            if not pairs:
                # fallback
                return [(i, i+10) for i in range(1, 60, 10)]
            return pairs
        except Exception as e:
            # fallback pairs
            return [(1, 11), (5, 15), (10, 20), (20, 30), (30, 40)]

    def generate(self, count: int = 5) -> List[Dict]:
        tickets = []
        for _ in range(count):
            if self.strong_pairs:
                pair = random.choice(self.strong_pairs)
                white_balls = list(pair)
            else:
                white_balls = random.sample(range(1, 70), 2)

            # Fill remaining 3 numbers
            available = [n for n in range(1, 70) if n not in white_balls]
            white_balls.extend(random.sample(available, 3))
            white_balls.sort()

            tickets.append({
                'white_balls': white_balls,
                'powerball': random.randint(1, 26),
                'strategy': self.name,
                'confidence': 0.65
            })

        return tickets
```

Notes:
- The strategy reads top significant pairs (deviation_pct > 20%). If no significant pairs exist in DB, the code provides deterministic fallback pairs.
- The generated tickets maintain uniqueness and sorted white ball order.

### 4.4 CoverageOptimizerStrategy

- Ensures coverage across tickets by preferring unused numbers when assembling tickets.
- If `available` numbers drop below 5, the `used_numbers` set is reset to continue generation.

### 4.5 RangeBalancedStrategy

- Draws samples distributed across three ranges: low (1–23), mid (24–46), high (47–69). Typical selection is 2 low, 2 mid, 1 high.

### 4.6 AIGuidedStrategy (ML-Powered)

**Updated: November 2025 - Now uses XGBoost ML model**

This strategy now integrates the trained XGBoost machine learning model for intelligent prediction:

- **Primary Mode**: Uses `Predictor.predict_probabilities()` to obtain ML-based probability distributions
  - XGBoost MultiOutputClassifier generates white ball probabilities (1-69)
  - Separate powerball probabilities (1-26)
  - Samples numbers using ML-guided probability distributions
  - Confidence score: 0.85 (higher than other strategies)

- **Fallback Mode**: If ML model unavailable, falls back to `IntelligentGenerator` (frequency-based analysis)
  - Uses historical frequency analysis
  - Confidence score: 0.70

- **Final Fallback**: Pure random generation if both fail
  - Confidence score: 0.50

**Technical Details:**
```python
# ML model integration flow:
AIGuidedStrategy.__init__()
  └─> _initialize_ml_predictor()
      └─> Predictor(config/config.ini)
          └─> ModelTrainer.load_model('models/shiolplus.pkl')
              └─> XGBoost MultiOutputClassifier loaded

AIGuidedStrategy.generate(count=5)
  └─> predictor.predict_probabilities(use_ensemble=False)
      └─> Returns (wb_probs, pb_probs) numpy arrays
  └─> np.random.choice(range(1,70), p=wb_probs, replace=False)
  └─> np.random.choice(range(1,27), p=pb_probs)
```

**Model Information:**
- File: `models/shiolplus.pkl` (18.2 MB)
- Type: `sklearn.multioutput.MultiOutputClassifier` wrapping XGBoost
- Features: 15 engineered features (frequency, temporal, pattern-based)
- Targets: 95 binary outputs (69 white balls + 26 powerballs)

### 4.7 RandomBaselineStrategy

- Purely random sampling; used as a control group.

### StrategyManager

- Holds instances of each strategy; initializes `strategy_performance` rows if missing.
- `generate_balanced_tickets(total)` selects strategies proportionally to their `current_weight` from DB and calls each strategy's `generate()` to produce tickets until `total` is met.
- Ensures unique Powerballs across the returned tickets via `_ensure_different_powerballs()`.

---

## 5. Co-occurrence Analysis Algorithm

The co-occurrence algorithm lives in `AnalyticsEngine.calculate_cooccurrence_matrix()` and `save_cooccurrence_to_db()`.

Key steps:

1. Iterate over all draws in `powerball_draws` and for each draw increment counts for every white-ball pair observed.
2. The matrix is symmetric and built for numbers 1..69 (0-indexed in numpy arrays).
3. Expected frequency per pair is computed as the combinatorial probability of both numbers appearing in a draw. The implementation uses:

   expected_per_pair = (5/69) * (4/68) * total_draws

4. Deviation percentage is calculated as ((observed - expected) / expected * 100). Pairs with |deviation| > 20% are marked `is_significant` in `cooccurrences`.

Complexity and performance:

- Time: O(n_draws * k^2) where k=5 (numbers per draw). For ~1,678 draws, the analytics run in ~2–3 seconds on the dev container.

Storage:

- All 2,346 pair rows are stored in `cooccurrences` with columns: (number_a, number_b, count, expected, deviation_pct, is_significant).

---

## 6. Adaptive Learning System

Adaptive learning is implemented in `adaptive_learning_update()` (src/api.py) and is executed as STEP 4 in the orchestrator.

Process:

1. Read `strategy_performance` rows (total_plays, total_wins).
2. Compute a `raw` score from win_rate + small prior (0.01) to avoid zeroes.
3. Normalize raw scores to weights: new_weight = raw / total_score.
4. Confidence is computed as min(0.95, 0.1 + plays / (plays + 100)).
5. Persist `current_weight` and `confidence`.

Notes and safeguards:

- The update uses a simple empirical Bayes-like heuristic; it is lightweight and robust to zeros.
- If no data exists (total_score=0), the pipeline falls back to equal weights for all strategies.

---

## 7. Era-Aware Data System

Problem:

Powerball's Powerball (PB) range changed over time. Using historical PB numbers directly in algorithms that assume PB ∈ [1,26] causes index errors and distribution skew.

Solution:

- Database triggers (`set_pb_era_on_insert`, `set_pb_era_on_update`) classify `pb_is_current` and `pb_era` using numeric ranges.
- Application-level safety net: `update_pb_era_metadata()` in `src/loader.py` updates any rows still classified with defaults.
- Analytics code filters PB calculations to `pb_is_current = 1` when computing PB frequency distributions.

Distribution in DB (inspection):

```
Total Draws: 1,851
Current Era (2015-now, PB 1-26):  1,678 (90.7%)
Historical (2012-2015, PB 27-35):   152 (8.2%)
Historical (2009-2012, PB 36-39):    21 (1.1%)
```

Design rationale:

- White-ball analytics can use all draws (white ball range is consistent), but PB analytics must use current-era draws only. This avoids out-of-range sampling and preserves historical data for white-ball patterns.

---

## 8. API Reference

The system exposes endpoints via FastAPI; core endpoints relevant to the pipeline and predictions are:

### POST /api/v1/predictions/generate-multi-strategy

Description: Generate predictions using the 6-strategy system.

Query Params:
- `count` (int): number of tickets to request (1-100; orchestrator commonly calls with batches of 5)

Response: JSON with tickets, metadata and strategy distribution.

Example:

```bash
curl -X POST "http://localhost:3000/api/v1/predictions/generate-multi-strategy?count=5"
```

### GET /api/v1/predictions/strategy-performance

Description: Returns ROI, win_rate, current_weight and confidence for each strategy.

Example response excerpt:

```json
{
  "coverage_optimizer": { "total_plays": 150, "roi": 1.25, "current_weight": 0.1850 }
}
```

### System & Debug Endpoints

- GET /api/v1/system/info — returns version, DB connection and model status.
- GET /api/v1/health — simple health check.
- GET /api/v1/scheduler/health — returns scheduler job list and next run times.

### Admin Endpoints

- POST /api/v1/admin/pipeline/trigger?async_run=true — Manually trigger the full pipeline run (admin only).
  - Uses FastAPI BackgroundTasks to ensure immediate HTTP response, preventing nginx 504 Gateway Timeout.
  - See `docs/NGINX_TIMEOUT_FIX.md` for technical details on the timeout prevention mechanism.

Router composition:

- `api.py` includes routers: `auth_router`, `billing_router`, `prediction_router`, `draw_router`, `ticket_router`, `admin_router`, and `public_frontend_router`.

---

## 9. Testing & Development

Quick tests (examples):

```bash
# Strategy test
python3 -c "from src.strategy_generators import CooccurrenceStrategy; print(CooccurrenceStrategy().generate(3))"

# Analytics update
python3 -c "from src.analytics_engine import update_analytics; print(update_analytics())"

# Full pipeline (async)
python3 -c "import asyncio; from src.api import trigger_full_pipeline_automatically; asyncio.run(trigger_full_pipeline_automatically())"
```

Database checks:

```sql
SELECT pb_era, COUNT(*) FROM powerball_draws GROUP BY pb_era;
SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='powerball_draws';
SELECT num1, num2, deviation_pct FROM cooccurrences ORDER BY deviation_pct DESC LIMIT 10;
```

Unit test recommendations:

- Add a unit test for `FrequencyWeightedStrategy._calculate_pb_frequencies()` to cover: empty DB, historical-only draws, mixed-era draws.
- Add a test for `CooccurrenceStrategy._get_strong_pairs()` to ensure DB fallback is used when `cooccurrences` is empty.
- Add an integration test for `StrategyManager.generate_balanced_tickets()` verifying total ticket count and unique powerballs.

---

## 10. Deployment & Operations

Runtime requirements:

- Python 3.10+
- SQLite file store (data/shiolplus.db)

Quick start (local/prod):

```bash
git clone https://github.com/orlandobatistac/SHIOL-PLUS.git
cd SHIOL-PLUS
pip install -r requirements.txt
python3 -c "from src.database import initialize_database; initialize_database()"
python3 -c "from src.loader import update_database_from_source; update_database_from_source()"
python3 -c "from src.analytics_engine import update_analytics; update_analytics()"
```

Scheduling:

- APScheduler cron jobs are configured in `src/api.py` (persistent jobstore) to run full pipeline next-day after draws (01:00 ET) and a maintenance update job (06:00 ET on non-drawing days).

Backups & monitoring:

- Regularly copy `data/shiolplus.db` to `data/backups/`. A recommended cron entry is provided in `src/database.py`.
- Monitor `pipeline_executions` table and `logs/` (if configured) for failures.

---

## Appendix A: Runtime Metrics (observed during local runs)

- Pipeline time (observed): DATA 0.5s | ANALYTICS 2.0s | EVALUATE 0.3s | ADAPT 0.1s | PREDICT 1.5s → Total ~4.4s
- DB size (data/shiolplus.db): ~792 KB

## Appendix B: Complexity

- Co-occurrence: O(n_draws * k^2) time, O(69^2) space.
- Strategy generation: roughly O(total_tickets * k) per run.

---

## 11. Intelligent Prediction Architecture (v6.2)

### 11.1 System Overview

**SHIOL-PLUS uses a strategy-based prediction system, NOT an ensemble ML model system.**

The production pipeline generates predictions through `StrategyManager.generate_balanced_tickets()`, which orchestrates 6 competing strategies with adaptive weight adjustment based on historical performance.

### 11.2 Architecture Components

#### Primary System: StrategyManager + 6 Strategies

```
┌─────────────────────────────────────────────────────────────┐
│          PRODUCTION PREDICTION PIPELINE                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  trigger_full_pipeline_automatically()                      │
│            ↓                                                │
│  StrategyManager.generate_balanced_tickets(200)             │
│            ↓                                                │
│  ┌───────────────────────────────────────────────┐         │
│  │  Strategy Selection (Adaptive Weights)        │         │
│  │  - Reads current_weight from DB               │         │
│  │  - Selects proportionally                     │         │
│  └───────────────────────────────────────────────┘         │
│            ↓                                                │
│  ┌─────────────────────┐  ┌─────────────────────┐          │
│  │ FrequencyWeighted   │  │ CoverageOptimizer   │          │
│  │ (Historical freq)   │  │ (Number diversity)  │          │
│  └─────────────────────┘  └─────────────────────┘          │
│                                                             │
│  ┌─────────────────────┐  ┌─────────────────────┐          │
│  │ Cooccurrence        │  │ RangeBalanced       │          │
│  │ (Statistical pairs) │  │ (Low/mid/high dist) │          │
│  └─────────────────────┘  └─────────────────────┘          │
│                                                             │
│  ┌─────────────────────┐  ┌─────────────────────┐          │
│  │ AIGuidedStrategy    │  │ RandomBaseline      │          │
│  │ ↓ [ML-POWERED]      │  │ (Control group)     │          │
│  │ XGBoost Model       │  │                     │          │
│  └─────────────────────┘  └─────────────────────┘          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Note**: As of November 2025, AIGuidedStrategy is now integrated with the XGBoost ML model, making it a true ML-powered strategy.

#### Integration: Predictor + XGBoost Model

```
┌─────────────────────────────────────────────────────────────┐
│        ML MODEL INTEGRATION (ACTIVE SINCE NOV 2025)         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  AIGuidedStrategy._initialize_ml_predictor()                │
│            ↓                                                │
│  Predictor.predict_probabilities(use_ensemble=False)        │
│            ↓                                                │
│  ModelTrainer.predict_probabilities(features)               │
│            ↓                                                │
│  XGBoost MultiOutputClassifier                              │
│  - Input: 15 engineered features                            │
│  - Output: 95 binary probabilities (69 WB + 26 PB)          │
│            ↓                                                │
│  Returns: (wb_probs[69], pb_probs[26])                      │
│            ↓                                                │
│  np.random.choice() with ML probabilities                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 11.3 AIGuidedStrategy: The ML-Powered Intelligence Layer

**Class:** `AIGuidedStrategy` (src/strategy_generators.py)  
**Updated:** November 2025 - Now uses trained XGBoost model

#### Initialization Flow (Current)

```python
# In AIGuidedStrategy.__init__()
def _initialize_ml_predictor(self) -> bool:
    from src.predictor import Predictor
    self._predictor = Predictor()
    
    if self._predictor.model is not None:
        logger.info("XGBoost ML model loaded successfully")
        return True
    return False

# In AIGuidedStrategy.generate()
if self._ml_available:
    wb_probs, pb_probs = self._predictor.predict_probabilities(use_ensemble=False)
    # Sample using ML probabilities
    white_balls = np.random.choice(range(1, 70), size=5, replace=False, p=wb_probs)
    powerball = np.random.choice(range(1, 27), p=pb_probs)
```

#### ML Model Pipeline

**XGBoost Model Details:**
- **File**: `models/shiolplus.pkl` (18.2 MB)
- **Type**: `MultiOutputClassifier` wrapping XGBoost base estimators
- **Architecture**: One binary classifier per target (95 total)
  - 69 classifiers for white balls (1-69)
  - 26 classifiers for powerball (1-26)

**Feature Engineering (15 features):**
1. Even/odd count
2. Number sum
3. Number spread (max - min)
4. Consecutive count
5. Average delay (since last seen)
6. Max delay
7. Min delay
8. Distance to recent draws
9. Distance to top-N frequent numbers
10. Distance to centroid
11. Temporal weight
12. Increasing trend count
13. Decreasing trend count
14. Stable trend count
15. (Reserved)

**Prediction Process:**

1. **Feature Generation**: `FeatureEngineer.engineer_features(use_temporal_analysis=True)`
2. **Model Inference**: `model.predict_proba(features)` → 95 probability arrays
3. **Probability Extraction**: Extract P(y=1) for each target
4. **Normalization**: Ensure probabilities sum to 1.0 for sampling
5. **Sampling**: Use probabilities to guide random selection

**Output:**
```python
{
    'white_balls': [12, 16, 19, 21, 44],  # Sampled using ML probabilities
    'powerball': 25,                      # Sampled using ML probabilities
    'strategy': 'ai_guided',
    'confidence': 0.85                    # Higher confidence for ML
}
```

#### Key Characteristics (Updated)

- ✅ **Uses trained ML model:** XGBoost with 15 engineered features
- ✅ **Probability-guided sampling:** Numbers selected according to ML predictions
- ✅ **Multi-layer fallback:** ML → IntelligentGenerator → Random
- ✅ **Historical data integration:** Model trained on 1,800+ draws
- ✅ **Active in production:** Integrated into StrategyManager pipeline
- ⚠️ **Not predictive:** Lottery is random; ML provides informed sampling, not guarantees

### 11.4 Adaptive Learning System

**Location:** `adaptive_learning_update()` in src/api.py

**Process:**

1. Read `strategy_performance` table (tracks wins, plays, ROI per strategy)
2. Calculate raw score: `win_rate + 0.01` (prior to avoid zeros)
3. Normalize to weights: `new_weight = raw_score / total_score`
4. Update confidence: `min(0.95, 0.1 + plays / (plays + 100))`
5. Persist to database

**Effect:**

Strategies that perform better get assigned more tickets in future generations. Over time, the system automatically shifts toward better-performing approaches.

**Example Evolution:**
```
Initial:     All strategies = 16.67% each
After 50:    Coverage = 22%, Frequency = 19%, Random = 9%
After 200:   Best strategy = 25%, Worst = 5%
```

### 11.5 Current System Strengths

1. **Diversity:** 6 different approaches ensure broad coverage
2. **Adaptability:** Weights adjust based on actual results
3. **Transparency:** Each ticket tagged with strategy and confidence
4. **Simplicity:** No complex ML model management
5. **Performance:** Fast execution (1.5s for 200 tickets)
6. **Maintainability:** Easy to add/remove/modify strategies

### 11.6 Current System Limitations

1. **Limited intelligence (fallback mode):** When ML unavailable, uses frequency analysis (basic pattern detection)
2. **Dummy ensemble (deprecated):** Old EnsemblePredictor class returns uniform probabilities (not used)
3. **Random lottery:** No system can predict truly random draws (inherent limitation)
4. ~~**XGBoost unused:**~~ **✓ RESOLVED (Nov 2025):** XGBoost model now integrated into AIGuidedStrategy

### 11.7 Technical Improvements (Historical Reference)

#### ~~Improvement 1: Integrate Real XGBoost Model into AIGuidedStrategy~~ ✓ COMPLETED

**Status:** ✅ **IMPLEMENTED (November 2025)**

**Previous State:** XGBoost model existed but wasn't used by generation pipeline.

**Current Implementation:**
```python
class AIGuidedStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("ai_guided")
        # Load actual XGBoost model ✓ DONE
        self._predictor = None
        self._ml_available = self._initialize_ml_predictor()
    
    def _initialize_ml_predictor(self) -> bool:
        from src.predictor import Predictor
        self._predictor = Predictor()
        return self._predictor.model is not None
        
    def generate(self, count: int = 5) -> List[Dict]:
        if self._ml_available:
            # Get probability distribution from ML model ✓ DONE
            wb_probs, pb_probs = self._predictor.predict_probabilities(use_ensemble=False)
            
            # Sample using ML probabilities ✓ DONE
            for _ in range(count):
                white_balls = np.random.choice(
                    range(1, 70), size=5, replace=False, p=wb_probs
                )
                powerball = np.random.choice(range(1, 27), p=pb_probs)
                # ... build ticket with confidence=0.85
        else:
            # Fallback to IntelligentGenerator
```

**Results:**
- ✅ ML model actively used in production pipeline
- ✅ Leverages 15 engineered features (temporal, pattern-based, statistical)
- ✅ More sophisticated than raw frequency analysis
- ✅ Confidence score increased to 0.85 (vs 0.70 for frequency-based)
- ✅ Seamless fallback to IntelligentGenerator if ML unavailable
- ✅ All tests passing (5/5 in test_ml_integration.py)

**Implementation Date:** November 2025  
**Code Changes:** src/strategy_generators.py (AIGuidedStrategy rewritten)  
**Test Coverage:** tests/test_ml_integration.py (5 comprehensive tests)  
**Documentation:** Demo script at scripts/demo_ml_integration.py

---

#### Improvement 2: Hybrid Statistical Filtering

**Current State:** Strategies generate numbers independently with no cross-validation.

**Proposal:** Add a post-generation filter that checks tickets against statistical outliers:

```python
class StatisticalFilter:
    """Filters out statistically improbable combinations"""
    
    def __init__(self, historical_data):
        self.historical_data = historical_data
        self._build_probability_models()
    
    def _build_probability_models(self):
        # Build historical distribution models
        self.sum_distribution = self._calculate_sum_distribution()
        self.gap_distribution = self._calculate_gap_distribution()
        self.low_mid_high_ratios = self._calculate_range_ratios()
    
    def filter_ticket(self, white_balls: List[int]) -> Tuple[bool, float]:
        """
        Returns: (should_keep, quality_score)
        
        Rejects tickets that are:
        - Outside 95% confidence interval for sum
        - Have consecutive numbers >3
        - All numbers in same decade
        - Duplicate recent patterns
        """
        score = 0.0
        
        # Check sum (e.g., 175 ± 60 for 95% CI)
        ticket_sum = sum(white_balls)
        if 115 <= ticket_sum <= 235:
            score += 0.3
        else:
            return False, 0.0  # Hard reject
        
        # Check for excessive consecutive numbers
        consecutive = self._count_consecutive(white_balls)
        if consecutive > 3:
            return False, 0.0
        elif consecutive <= 1:
            score += 0.2
        
        # Check range distribution
        low = sum(1 for n in white_balls if n <= 23)
        mid = sum(1 for n in white_balls if 24 <= n <= 46)
        high = sum(1 for n in white_balls if n >= 47)
        
        if max(low, mid, high) <= 3:  # No range has >3 numbers
            score += 0.3
        
        # Check for duplication of recent patterns
        if not self._is_recent_duplicate(white_balls):
            score += 0.2
        
        return True, score
```

**Integration:**
```python
# In StrategyManager.generate_balanced_tickets()
filter = StatisticalFilter(historical_data)
tickets = []
attempts = 0

while len(tickets) < total and attempts < total * 3:
    candidate = strategy.generate(1)[0]
    keep, score = filter.filter_ticket(candidate['white_balls'])
    if keep:
        candidate['quality_score'] = score
        tickets.append(candidate)
    attempts += 1
```

**Benefits:**
- Eliminates statistically improbable combinations
- Reduces wasted tickets on "bad" patterns
- Based on historical probability distributions
- Minimal performance impact

**Estimated Effort:** 4-6 hours  
**Expected Improvement:** 15-20% reduction in low-quality tickets

---

#### Improvement 3: Temporal Weighting with Recency Bias

**Current State:** All historical draws weighted equally (draw from 2010 = draw from 2025).

**Proposal:** Apply exponential decay to give more weight to recent patterns:

```python
class TemporalWeightedAnalyzer:
    """Analyzes historical patterns with recency bias"""
    
    def __init__(self, historical_data, decay_rate=0.95):
        self.data = historical_data.sort_values('draw_date')
        self.decay_rate = decay_rate  # 0.95 = 5% decay per draw
        self._calculate_temporal_weights()
    
    def _calculate_temporal_weights(self):
        """Assign exponentially decaying weights to draws"""
        n_draws = len(self.data)
        # Most recent draw = weight 1.0
        # Each older draw = weight * decay_rate
        weights = [self.decay_rate ** (n_draws - i - 1) 
                   for i in range(n_draws)]
        self.data['temporal_weight'] = weights
    
    def get_weighted_frequencies(self):
        """Calculate frequency with temporal weighting"""
        wb_freq = {}
        pb_freq = {}
        
        for idx, row in self.data.iterrows():
            weight = row['temporal_weight']
            
            # White balls
            for col in ['n1', 'n2', 'n3', 'n4', 'n5']:
                num = row[col]
                wb_freq[num] = wb_freq.get(num, 0) + weight
            
            # Powerball
            pb_num = row['pb']
            pb_freq[pb_num] = pb_freq.get(pb_num, 0) + weight
        
        return wb_freq, pb_freq
```

**Integration into IntelligentGenerator:**
```python
def generate_smart_play(self):
    # Use temporal analyzer instead of raw frequency
    analyzer = TemporalWeightedAnalyzer(self.historical_data)
    wb_freq, pb_freq = analyzer.get_weighted_frequencies()
    
    # Rest of selection logic uses weighted frequencies
    ...
```

**Benefits:**
- Recent patterns have more influence than old patterns
- Adapts to rule changes (e.g., 2015 Powerball range change)
- More responsive to trend shifts
- Mathematically sound (exponential decay standard in time series)

**Estimated Effort:** 3-4 hours  
**Expected Improvement:** 10-12% better alignment with recent patterns

---

### 11.8 Implementation Priority

**High Priority:**
1. **Improvement 2: Statistical Filtering** (highest ROI)
   - Easy to implement
   - No model training required
   - Immediate quality improvement

**Medium Priority:**
2. **Improvement 3: Temporal Weighting** (good balance)
   - Moderate complexity
   - Improves existing system
   - Compatible with current architecture

**~~Low Priority:~~ COMPLETED:**
3. ~~**Improvement 1: XGBoost Integration**~~ ✅ **DONE (Nov 2025)**
   - ✓ Model integrated into AIGuidedStrategy
   - ✓ Tests added and passing
   - ✓ Documentation updated

### 11.9 Technical Debt Notes

**Items to Address:**

1. **~~Unused Code Cleanup:~~** PARTIALLY RESOLVED
   - ✓ `Predictor.predict_probabilities()` now actively used by AIGuidedStrategy
   - ⚠️ Consider removing dummy `EnsemblePredictor` class (low priority)
   - ⚠️ Clean up unused imports in `predictor.py` (low priority)

2. **Documentation:**
   - Update README to clarify "AI" refers to strategy selection, not deep learning
   - Document that XGBoost model exists but isn't used in generation

3. **Testing:**
   - Add unit tests for `IntelligentGenerator.generate_smart_play()`
   - Add integration tests for `StrategyManager.generate_balanced_tickets()`
   - Test adaptive learning weight convergence

4. **Performance:**
   - Profile `generate_balanced_tickets()` for bottlenecks
   - Consider caching frequency calculations
   - Optimize database queries in strategy initialization

---

**Document Version**: 1.1  
**Last Updated**: October 24, 2025  
**Author**: Orlando B.

---

*End of Technical Documentation*

---

## Ticket Verification Date Normalization

Context: Some uploaded ticket images produced a 422 Unprocessable Entity with the message "No official draw results found for date: <date>" despite the date existing in the database.

Root cause:

- Draw date values extracted by OCR/LLM could be in multiple human formats (e.g., "Sep 13 25", "10/13/25", or ISO timestamps like "2025-10-13T00:00:00Z").
- The verification step expects an ISO date (YYYY-MM-DD). If a non-ISO date reaches the matcher, strict parsing can fail and no match is found.
- Additionally, the fallback OCR flow didn't capture the "MON-less" format (e.g., "SEP 13 25").

Changes implemented (October 24, 2025):

- Added robust normalization in `src/ticket_processor.py`:
    - New method `normalize_date(raw: str) -> Optional[str]` that standardizes multiple formats to `YYYY-MM-DD`.
    - It handles: `Sep 13 25`, `Oct 13 2025`, `10/13/25`, `2025-9-3`, and ISO timestamps like `2025-10-13T00:00:00.000Z`.
    - Integrated into the Gemini path: `_process_with_gemini_ai()` now normalizes `draw_date` returned by Gemini before returning `ticket_data`.

- Extended OCR fallback regex in `extract_draw_date()` to capture month+day+2-digit-year without weekday (e.g., `SEP 13 25`).

- Note: `TicketVerifier.find_matching_draw()` already includes a ±3-day tolerance window when searching for the closest official draw.

Verification and evidence:

- Database check (latest 10 draws contained October 2025 dates including `2025-10-13`).
- Programmatic test:
    - Input: `"Oct 13 25"` → `normalize_date` → `"2025-10-13"` → `find_matching_draw("2025-10-13")` → exact match found.

Operational guidance:

- If future tickets show new date styles, update `normalize_date()` and/or `extract_draw_date()` with a minimal additional pattern.
- Keep `powerball_draws` updated via the existing scheduler in `src/api.py` (jobs: `post_drawing_pipeline` and `maintenance_data_update`) which call `update_database_from_source()`.

Recommended future hardening:

- Add a lightweight unit test for `normalize_date()` covering the most common observed formats.
- Consider using `dateutil.parser` if introducing an external dependency is acceptable; current implementation avoids new dependencies and uses explicit patterns.

---

## 12. Payments & Billing (Stripe)

This section consolidates prior payment “fix” notes into an authoritative reference.

### 12.1 Overview

The billing system uses Stripe Checkout (Test/Sandbox mode for demos). Verification is resilient via a dual approach:
- Primary: Direct session verification (client passes `session_id` to backend).
- Fallback: Webhook processing (production-ready; optional in local tests).

Premium access is represented by a server-side record and an HttpOnly cookie for the browser session. Admins can directly toggle premium for 1 year via admin endpoints.

### 12.2 Endpoints

- GET `/api/v1/billing/status` — Optional query `session_id`.
    - If `session_id` provided, backend retrieves session from Stripe, verifies `payment_status == 'paid'` and `status == 'complete'`.
    - If paid and no Premium Pass exists, it creates one immediately (webhook fallback).
    - Returns `is_premium` and related details.

- POST `/api/v1/billing/activate-premium`
    - Body: `{ session_id: string }` (optional).
    - Purpose: Set an HttpOnly, Secure cookie for the current browser session after payment confirmation.
    - Decoupled from webhooks (webhooks cannot set browser cookies).

### 12.3 Client Flow (payment-success)

1. Read `session_id` from URL.
2. Poll `/billing/status?session_id=...` until confirmed (typically 1–3 attempts in test mode).
3. Call `/billing/activate-premium` to set the HttpOnly cookie.
4. Redirect to the app; premium features are available immediately.

### 12.4 Cookies & Security

- Cookie flags: HttpOnly, Secure, SameSite=Lax.
- Expiration: 1 year.
- Cookie contains a signed token; backend always validates on each request.
- Webhook processing remains enabled for production lifecycle events.

### 12.5 Operational Notes

- Test Mode: No real charges; demonstrates production practices safely.
- Production: Configure webhooks (`checkout.session.completed`, `invoice.paid`, etc.).
- Admin Panel: Allows toggling premium for exactly 1 year (server-side timestamped).

### 12.6 Troubleshooting Summary

- “Taking longer” message: Verify env vars, ensure URL has `session_id`, inspect `/billing/status` and `/activate-premium` responses.
- Cookie not set: In production, ensure HTTPS (Secure flag); check network console for `/activate-premium`.
- Webhook signature errors: Verify `STRIPE_WEBHOOK_SECRET` and Stripe Dashboard endpoint configuration.

