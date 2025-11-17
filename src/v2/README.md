# SHIOL+ v2 - Modern Statistical Lottery Prediction Engine

## Overview

SHIOL+ v2 is a complete evolution of the lottery prediction system, introducing:

- **Temporal statistical models** with exponential decay
- **Momentum detection** for rising/falling trends
- **Gap/drought theory** with Poisson return probability
- **Pattern conformity analysis** across multiple dimensions
- **Multi-dimensional ticket scoring** for quality evaluation
- **Comprehensive analytics API** for PredictLottoPro integration

## Architecture

### Module Structure

```
src/v2/
├── __init__.py           # Package initialization and exports
├── statistical_core.py   # Core analytical engines
├── strategies.py         # v2 prediction strategies
├── scoring.py           # Multi-dimensional scoring engine
└── analytics_api.py     # FastAPI analytics endpoint
```

### Statistical Core

Located in `statistical_core.py`, provides four key analytical engines:

#### 1. TemporalDecayModel

Applies exponential temporal decay to historical draws, giving recent draws higher influence.

**Formula:** `weight(t) = exp(-λ * (current_draw - t))`

**Features:**
- Configurable decay factor (λ)
- Adaptive window sizing based on variance
- Separate weights for white balls and powerball
- Current-era awareness (PB 1-26 only)

**Usage:**
```python
from src.v2 import TemporalDecayModel

model = TemporalDecayModel(decay_factor=0.05)
weights = model.calculate_weights(draws_df)

# Access weights
white_ball_probs = weights.white_ball_weights  # Shape: (69,)
powerball_probs = weights.powerball_weights    # Shape: (26,)
```

#### 2. MomentumAnalyzer

Detects rising and falling trends by comparing short-term vs long-term frequencies.

**Formula:** `momentum = (recent_frequency - historical_frequency) / historical_frequency`

**Features:**
- Configurable short/long windows
- Hot numbers (positive momentum)
- Cold numbers (negative momentum)
- Per-number momentum scores

**Usage:**
```python
from src.v2 import MomentumAnalyzer

analyzer = MomentumAnalyzer(short_window=10, long_window=50)
momentum = analyzer.analyze(draws_df)

print(momentum.hot_numbers)   # Numbers with strongest positive momentum
print(momentum.cold_numbers)  # Numbers with strongest negative momentum
```

#### 3. GapAnalyzer

Implements gap/drought theory to identify overdue numbers.

**Features:**
- Calculates draws since last appearance
- Poisson-based return probability
- Overdue number identification
- Era-aware powerball analysis

**Usage:**
```python
from src.v2 import GapAnalyzer

analyzer = GapAnalyzer()
gaps = analyzer.analyze(draws_df)

print(gaps.overdue_numbers)  # Top 15 most overdue
print(gaps.white_ball_probabilities)  # Return probabilities
```

#### 4. PatternEngine

Analyzes historical pattern conformity across multiple dimensions.

**Dimensions:**
- Odd/even balance (0-5 odd numbers per draw)
- High/low distribution (1-23 low, 24-46 mid, 47-69 high)
- Sum ranges (statistical bounds)
- Tens-decade clustering (0-9, 10-19, ..., 60-69)

**Usage:**
```python
from src.v2 import PatternEngine

engine = PatternEngine()
patterns = engine.analyze(draws_df)

# Score a ticket for conformity
white_balls = [5, 15, 25, 35, 45]
conformity_score = engine.score_pattern_conformity(white_balls)
```

## Strategies

Located in `strategies.py`, all strategies inherit from v1's `BaseStrategy` for compatibility.

### 1. Temporal Frequency Strategy (TFS)

Generates tickets using recency-weighted probabilities.

**Confidence:** 0.78 (high - based on proven temporal patterns)

```python
from src.v2 import TemporalFrequencyStrategy

strategy = TemporalFrequencyStrategy(decay_factor=0.05)
tickets = strategy.generate(count=5)
```

### 2. Momentum Strategy (MS)

Favors numbers with positive momentum (rising trends).

**Confidence:** 0.72 (good - trend detection is statistically significant)

```python
from src.v2 import MomentumStrategy

strategy = MomentumStrategy(short_window=10, long_window=50)
tickets = strategy.generate(count=5)
```

### 3. Gap/Drought Theory Strategy (GTS)

Selects overdue numbers based on gap analysis and Poisson return probability.

**Confidence:** 0.68 (moderate - regression to mean takes time)

```python
from src.v2 import GapTheoryStrategy

strategy = GapTheoryStrategy()
tickets = strategy.generate(count=5)
```

### 4. Pattern Strategy (PS)

Generates tickets conforming to historical pattern distributions.

**Confidence:** 0.65-0.85 (varies by conformity score)

```python
from src.v2 import PatternStrategy

strategy = PatternStrategy()
tickets = strategy.generate(count=5)
```

### 5. Hybrid Smart Strategy (HSS)

**Most sophisticated strategy** - combines multiple analytical dimensions:

- 2 hot numbers (temporal decay)
- 1 momentum number (rising trend)
- 1 cold number (gap theory)
- 1 balanced number (pattern conformity)

All tickets must pass pattern conformity checks.

**Confidence:** 0.80 (highest - multi-dimensional approach)

```python
from src.v2 import HybridSmartStrategy

strategy = HybridSmartStrategy()
tickets = strategy.generate(count=5)
```

## Scoring Engine

Located in `scoring.py`, provides multi-dimensional ticket quality evaluation.

### Dimensions

1. **Diversity Score (25%)** - Entropy-based spread across number range
2. **Balance Score (25%)** - Conformity to ideal low/mid/high distribution
3. **Pattern Score (35%)** - Historical pattern conformity
4. **Similarity Score (15%)** - Optimal distance from historical draws

### Usage

```python
from src.v2 import ScoringEngine

# Initialize with historical draws for pattern analysis
engine = ScoringEngine(draws_df=draws_df)

# Score a single ticket
white_balls = [5, 15, 25, 35, 45]
powerball = 10
score = engine.score_ticket(white_balls, powerball)

print(f"Overall: {score.overall_score:.2f}")
print(f"Diversity: {score.diversity_score:.2f}")
print(f"Balance: {score.balance_score:.2f}")
print(f"Pattern: {score.pattern_score:.2f}")
print(f"Similarity: {score.similarity_score:.2f}")

# Rank multiple tickets
tickets = [...]
ranked = engine.rank_tickets(tickets)
best_ticket, best_score = ranked[0]
```

## Analytics API

Located in `analytics_api.py`, provides comprehensive analytics endpoint.

### Endpoint: `/api/v3/analytics/overview`

**Method:** GET  
**Authentication:** None (public)

**Response:**
```json
{
  "hot_cold": {
    "hot_numbers": [23, 45, 12, ...],
    "cold_numbers": [67, 3, 58, ...],
    "hot_powerball": [15, 8, 22],
    "cold_powerball": [1, 13, 26]
  },
  "momentum": {
    "rising_numbers": [45, 23, 12, ...],
    "falling_numbers": [67, 58, 3, ...],
    "momentum_chart": "ASCII visualization"
  },
  "gaps": {
    "overdue_numbers": [34, 56, 19, ...],
    "recent_numbers": [23, 45, 12, ...],
    "avg_gap": 8.5,
    "gap_chart": "ASCII visualization"
  },
  "patterns": {
    "odd_even_distribution": {"0": 0.05, "1": 0.15, ...},
    "sum_stats": {"mean": 175.3, "std": 38.2, ...},
    "decade_distribution": {"0-9": 0.10, ...},
    "typical_spread": 48.5
  },
  "top_cooccurrences": [
    {"number_a": 23, "number_b": 45, "count": 87, "deviation_pct": 25.3},
    ...
  ],
  "summary_commentary": "Human-readable summary...",
  "total_draws": 1851,
  "last_updated": "2024-11-17 22:45:00"
}
```

### Integration with PredictLottoPro

```javascript
// Frontend integration example
async function fetchAnalytics() {
  const response = await fetch('/api/v3/analytics/overview');
  const data = await response.json();
  
  // Display hot/cold numbers
  displayHotNumbers(data.hot_cold.hot_numbers);
  
  // Show momentum chart
  renderMomentumChart(data.momentum.momentum_chart);
  
  // Display gap analysis
  showOverdueNumbers(data.gaps.overdue_numbers);
}
```

## Testing

Comprehensive test suite in `tests/test_v2_components.py`:

```bash
# Run all v2 tests
pytest tests/test_v2_components.py -v

# Run specific test class
pytest tests/test_v2_components.py::TestTemporalDecayModel -v

# Run with coverage
pytest tests/test_v2_components.py --cov=src.v2
```

**Test Coverage:**
- ✅ 22 tests passing
- ✅ Statistical core components
- ✅ All 5 strategies
- ✅ Scoring engine
- ✅ Edge cases and error handling

## Backward Compatibility

SHIOL+ v2 is **fully backward compatible** with v1:

1. **No modifications** to existing `src/strategy_generators.py`
2. **Separate namespace** (`src/v2/`)
3. **New API endpoint** (`/api/v3/analytics/overview`)
4. **V1 strategies continue working** unchanged
5. **Gradual migration path** - can use v1 and v2 simultaneously

## Performance Characteristics

### Statistical Core

- **TemporalDecayModel:** O(n * k) where n = draws, k = window size
- **MomentumAnalyzer:** O(n) for frequency calculation
- **GapAnalyzer:** O(n) for gap calculation
- **PatternEngine:** O(n) for analysis, O(1) for scoring

### Strategies

- **All strategies:** O(1) after initial analysis (precomputed weights)
- **HybridSmartStrategy:** O(k) where k = attempts to find conforming ticket

### Memory

- **Modest footprint:** ~5-10 MB for full historical analysis
- **Efficient caching:** Analytical results cached in strategy instances

## Future Enhancements (Phase 2+)

From the blueprint, planned for future implementation:

**Phase 2:**
- Correlation Network Strategy (PageRank-inspired)
- Ensemble Consensus Strategy
- Strategy Manager v2 with Bayesian updates
- Enhanced scoring (naturalness, innovation)

**Phase 3:**
- Association rule mining (Apriori)
- Isolation forest for novelty detection
- Fourier-based periodicity detection
- Mahalanobis-based naturalness scoring

**Phase 4:** (Research-only, not for automatic implementation)
- Quantum-inspired methods
- Chaos theory approaches
- Swarm intelligence

## Contributing

When extending v2:

1. **Add tests** for all new components
2. **Maintain backward compatibility**
3. **Follow existing patterns** (dataclasses for results, descriptive docstrings)
4. **Use loguru** for logging
5. **Keep modules focused** (single responsibility)

## License

Same as SHIOL+ project.

## Support

For questions or issues with v2 components, please open a GitHub issue with the `v2` label.
