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

## 3. Enhanced Pipeline (5-Step Process)

The orchestrator lives primarily in `src/api.py` (`trigger_full_pipeline_automatically()`), which performs the five steps:

1. DATA — `update_database_from_source()` (src/loader.py)
2. ANALYTICS — `update_analytics()` (src/analytics_engine.py)
3. EVALUATE — `evaluate_predictions_for_draw()` (src/api.py)
4. ADAPTIVE LEARNING — `adaptive_learning_update()` (src/api.py)
5. PREDICT — `StrategyManager.generate_balanced_tickets()` (src/strategy_generators.py)

### 3.1 Sequence and resilience

- Each step is wrapped with try/except. Failures don't abort the whole pipeline; the pipeline logs and proceeds to next steps where possible.
- Scheduler uses APScheduler with a persistent SQLite jobstore (`data/scheduler.db`).
- A 'UNIFIED' subprocess mode exists as fallback (`run_full_pipeline_background()`), which runs `main.py` in a subprocess to isolate long-running jobs.

### 3.2 Key orchestration points (practical notes)

- The orchestrator expects the `DateManager` (src/date_utils.py) to compute the next drawing date reliably; failing that, it logs and uses fallbacks.
- Generated ticket persistence is handled by `save_generated_tickets()` (in `src/api.py`), which inserts records into `generated_tickets`.
- Evaluation writes to `performance_tracking` and updates `predictions_log` with evaluation results and prize amounts.

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

### 4.6 AIGuidedStrategy

- Wraps the project `IntelligentGenerator` (src/intelligent_generator.py). The code attempts multiple instantiation patterns for backward compatibility.
- If ML model is unavailable or generation fails, it falls back to random generation.

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

Router composition:

- `api.py` includes routers: `auth_router`, `billing_router`, `prediction_router`, `draw_router`, `ticket_router`, and `public_frontend_router`.

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

**Document Version**: 1.0  
**Last Updated**: October 19, 2025  
**Author**: Orlando B.

---

*End of Technical Documentation*
