# PLP V2 Core Analytics Engines - Usage Guide

## Overview

This module provides three core mathematical engines for PredictLottoPro V2:

1. **Analytics Engine**: Statistical analysis of historical draws
2. **Ticket Scorer**: 0-100 scoring system for user tickets
3. **Interactive Generator**: Custom ticket generation based on user parameters

## Quick Start

### 1. Analytics Overview

Get all analytics in one call:

```python
from src.analytics_engine import get_analytics_overview

# Get comprehensive analytics
overview = get_analytics_overview()

print(overview['gap_analysis'])          # Days since last appearance
print(overview['temporal_frequencies'])  # Weighted frequencies
print(overview['momentum_scores'])       # Rising/falling trends
print(overview['pattern_statistics'])    # Traditional patterns
print(overview['data_summary'])          # Dataset info
```

### 2. Individual Analytics Functions

For more control, use individual functions:

```python
from src.analytics_engine import (
    compute_gap_analysis,
    compute_temporal_frequencies,
    compute_momentum_scores
)
from src.database import get_all_draws

# Get historical data
df = get_all_draws()

# Calculate gap analysis (days since last appearance)
gaps = compute_gap_analysis(df)
print(f"Number 7 last appeared {gaps['white_balls'][7]} days ago")

# Calculate temporal frequencies (with exponential decay)
freqs = compute_temporal_frequencies(df, decay_rate=0.05)
print(f"Number 7 frequency: {freqs['white_balls'][6]:.4f}")

# Calculate momentum scores (-1.0 to +1.0)
momentum = compute_momentum_scores(df, window=20)
if momentum['white_balls'][7] > 0.3:
    print("Number 7 has rising momentum!")
```

### 3. Scoring User Tickets

Score tickets on a 0-100 scale:

```python
from src.ticket_scorer import TicketScorer
from src.analytics_engine import get_analytics_overview

# Get analytics context
context = get_analytics_overview()

# Create scorer
scorer = TicketScorer()

# Score a ticket
result = scorer.score_ticket(
    ticket_numbers=[5, 15, 25, 35, 45],
    powerball=10,
    context=context
)

print(f"Total Score: {result['total_score']}/100")
print(f"Diversity: {result['details']['diversity']['quality']}")
print(f"Balance: {result['details']['balance']['quality']}")
print(f"Potential: {result['details']['potential']['quality']}")
print(f"Recommendation: {result['recommendation']}")
```

**Scoring Breakdown:**

- **Diversity** (0.0-1.0): Numbers spread across different decades (1-9, 10-19, etc.)
  - Perfect (1.0): 5 different decades
  - Poor (0.2): All in same decade
  
- **Balance** (0.0-1.0): Sum range and odd/even ratio
  - Optimal sum: 130-220
  - Balanced ratio: 2-3 odd, 2-3 even
  
- **Potential** (0.0-1.0): Alignment with hot numbers and rising momentum
  - Hot numbers: Gap < 30 days
  - Rising momentum: Score > 0.2

### 4. Interactive Ticket Generation

Generate custom tickets based on user preferences:

```python
from src.strategy_generators import CustomInteractiveGenerator
from src.analytics_engine import get_analytics_overview

# Get analytics context (optional, will compute if not provided)
context = get_analytics_overview()

# Create generator
generator = CustomInteractiveGenerator()

# Generate tickets with custom parameters
params = {
    'count': 5,              # Number of tickets
    'risk': 'med',           # 'low', 'med', 'high'
    'temperature': 'hot',    # 'hot', 'cold', 'neutral'
    'exclude': [1, 2, 3]     # Numbers to avoid
}

tickets = generator.generate_custom(params, context)

for i, ticket in enumerate(tickets, 1):
    print(f"Ticket {i}: {ticket['white_balls']} PB:{ticket['powerball']}")
    print(f"  Confidence: {ticket['confidence']:.2f}")
```

**Parameters Explained:**

- **Risk Level**:
  - `low`: Conservative (flatten probability distribution)
  - `med`: Balanced (normal distribution)
  - `high`: Aggressive (sharpen distribution, more outliers)

- **Temperature**:
  - `hot`: Favor frequently appearing numbers (high temporal frequency)
  - `cold`: Favor overdue numbers (high gap values)
  - `neutral`: Uniform distribution

- **Exclude**: List of numbers to avoid (e.g., `[1, 2, 3, 13, 69]`)

## API Integration Examples

### Dashboard Endpoint

```python
from fastapi import APIRouter
from src.analytics_engine import get_analytics_overview

router = APIRouter()

@router.get("/analytics/dashboard")
async def get_dashboard_analytics():
    """Get all analytics for dashboard display"""
    overview = get_analytics_overview()
    
    return {
        "success": True,
        "data": {
            "hot_numbers": [
                num for num, gap in overview['gap_analysis']['white_balls'].items()
                if gap < 30
            ][:10],
            "cold_numbers": [
                num for num, gap in sorted(
                    overview['gap_analysis']['white_balls'].items(),
                    key=lambda x: x[1],
                    reverse=True
                )
            ][:10],
            "rising_momentum": [
                num for num, score in overview['momentum_scores']['white_balls'].items()
                if score > 0.3
            ],
            "data_summary": overview['data_summary']
        }
    }
```

### Ticket Scoring Endpoint

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.ticket_scorer import TicketScorer
from src.analytics_engine import get_analytics_overview

router = APIRouter()

class TicketScoreRequest(BaseModel):
    white_balls: list[int]
    powerball: int

@router.post("/tickets/score")
async def score_user_ticket(request: TicketScoreRequest):
    """Score a user's ticket"""
    try:
        context = get_analytics_overview()
        scorer = TicketScorer()
        
        result = scorer.score_ticket(
            request.white_balls,
            request.powerball,
            context
        )
        
        return {"success": True, "score": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### Custom Generation Endpoint

```python
from fastapi import APIRouter
from pydantic import BaseModel
from src.strategy_generators import CustomInteractiveGenerator
from src.analytics_engine import get_analytics_overview

router = APIRouter()

class GenerateRequest(BaseModel):
    count: int = 5
    risk: str = 'med'
    temperature: str = 'neutral'
    exclude: list[int] = []

@router.post("/tickets/generate")
async def generate_custom_tickets(request: GenerateRequest):
    """Generate custom tickets based on user parameters"""
    context = get_analytics_overview()
    generator = CustomInteractiveGenerator()
    
    params = {
        'count': request.count,
        'risk': request.risk,
        'temperature': request.temperature,
        'exclude': request.exclude
    }
    
    tickets = generator.generate_custom(params, context)
    
    return {"success": True, "tickets": tickets}
```

## Performance Considerations

1. **Cache Analytics**: `get_analytics_overview()` is computationally expensive. Cache results for ~5 minutes.

```python
from functools import lru_cache
from datetime import datetime, timedelta

_cache = {'data': None, 'timestamp': None}

def get_cached_analytics(max_age_minutes=5):
    now = datetime.now()
    
    if (_cache['data'] is None or 
        _cache['timestamp'] is None or
        (now - _cache['timestamp']) > timedelta(minutes=max_age_minutes)):
        
        _cache['data'] = get_analytics_overview()
        _cache['timestamp'] = now
    
    return _cache['data']
```

2. **Generator Caching**: `CustomInteractiveGenerator` caches analytics internally. Reuse the same instance when possible.

```python
# Good: Reuse generator instance
generator = CustomInteractiveGenerator()
for params in user_requests:
    tickets = generator.generate_custom(params)
    
# Bad: Create new instance each time
for params in user_requests:
    generator = CustomInteractiveGenerator()  # Recomputes analytics!
    tickets = generator.generate_custom(params)
```

## Error Handling

All functions handle empty data gracefully:

```python
import pandas as pd
from src.analytics_engine import compute_gap_analysis

# Empty dataframe - returns defaults without crashing
empty_df = pd.DataFrame()
result = compute_gap_analysis(empty_df)
# Returns: {'white_balls': {1: 0, 2: 0, ...}, 'powerball': {1: 0, ...}}
```

## Testing

Run the test suite:

```bash
# All PLP V2 tests
pytest tests/test_plp_v2_analytics.py tests/test_ticket_scorer.py tests/test_custom_interactive_generator.py -v

# Specific test file
pytest tests/test_ticket_scorer.py -v

# With coverage
pytest tests/test_plp_v2_analytics.py --cov=src.analytics_engine
```

## Mathematical Details

### Gap Analysis
- Calculates days between most recent draw and when each number last appeared
- Numbers never seen get gap of 999 (very overdue marker)
- Formula: `gap = (most_recent_date - last_seen_date).days`

### Temporal Frequencies
- Exponential decay weighting: `weight = exp(-decay_rate * days_ago)`
- Default decay rate: 0.05 (half-life ≈ 14 days)
- Normalized to probability distribution (sum = 1.0)

### Momentum Scores
- Compares frequency in recent window vs previous window
- Formula: `(recent_freq - previous_freq) / (recent_freq + previous_freq + ε)`
- Range: -1.0 (falling) to +1.0 (rising)
- Default window: 20 draws (compares last 10 vs previous 10)

### Diversity Score
- Decade ranges: 1-9 (0), 10-19 (1), 20-29 (2), ..., 60-69 (6)
- Score: `unique_decades / 5.0`
- Example: [5, 15, 25, 35, 45] = 5 decades = 1.0 score

### Balance Score
- Sum component: Optimal 130-220 (based on historical patterns)
- Odd/even component: Balanced = 2-3 of each
- Final: Average of sum_score and ratio_score

### Potential Score
- Hot component: Gap < 30 days = hot
- Momentum component: Score > 0.2 = rising
- Weighted: 70% white balls, 30% powerball

## License

Part of SHIOL+ project. See main repository for license details.
