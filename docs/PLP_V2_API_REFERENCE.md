# PLP V2 API Reference - Quick Start Guide

**Base URL**: `https://shiolplus.com` (Production) | `http://localhost:8000` (Development)
**API Version**: v2.3.0
**Authentication**: Bearer token in `Authorization` header
**Last Updated**: 2025-12-03

---

## 🚀 RECOMMENDED: Single Endpoint for Dashboard

> **⚡ USE THIS ENDPOINT**: Instead of making multiple API calls, use `/api/v2/plp-dashboard` to get ALL dashboard data in a single request. This saves ~112ms of network latency and simplifies your code.

```bash
# ONE call instead of 3-5 calls
curl -X GET "https://shiolplus.com/api/v2/plp-dashboard" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Benefits:**
- ✅ **All data in one response**: draw stats + hot/cold + strategies + predictions
- ✅ **~112ms faster** than multiple endpoint calls (with network latency)
- ✅ **5-minute cache**: subsequent requests return in <2ms
- ✅ **Simpler code**: one fetch, one response to parse

---

## 🔐 Authentication

All endpoints require API key authentication:

```bash
Authorization: Bearer YOUR_PLP_API_KEY
```

**Environment Variable**: `PREDICTLOTTOPRO_API_KEY`

**Response Codes**:

- `401`: Missing or malformed Authorization header
- `403`: Invalid API key
- `200`: Success

**Rate Limiting**: 100 requests/minute per API key

---

## 📊 Endpoints Overview

| Endpoint                           | Method | Purpose                              | Avg Response Time   |
| ---------------------------------- | ------ | ------------------------------------ | ------------------- |
| **`/api/v2/plp-dashboard`** ⭐     | GET    | **ALL dashboard data (RECOMMENDED)** | **<2ms** (cached)   |
| `/api/v2/analytics/context`        | GET    | Dashboard analytics (legacy)         | <5ms (cached)       |
| `/api/v2/hot-cold-numbers`         | GET    | Hot/cold numbers only                | <1ms (cached)       |
| `/api/v2/draw-stats`               | GET    | Draw statistics summary              | <5ms                |
| `/api/v2/overview-enhanced`        | GET    | Enhanced overview                    | <15ms               |
| `/api/v2/analytics/analyze-ticket` | POST   | Score user tickets                   | <10ms               |
| `/api/v2/generator/interactive`    | POST   | Generate custom tickets              | <10ms               |

> **⚡ Performance Note**: All analytics endpoints include 5-minute caching. First request calculates data (~20ms), subsequent requests return cached data (<2ms).

---

## ⭐ 1. GET /api/v2/plp-dashboard (RECOMMENDED)

**Purpose**: Get ALL dashboard data in a single call - draw stats, hot/cold numbers, top strategies, AND predictions for next draw.

**⚡ Performance**:
- First request: ~20ms (4 DB queries)
- Cached requests: **<2ms** (cache TTL: 5 minutes)

### Request

```bash
curl -X GET "https://shiolplus.com/api/v2/plp-dashboard" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "draw_stats": {
      "total_draws": 2260,
      "most_recent": "2025-12-01",
      "current_era": 1980
    },
    "hot_cold": {
      "hot_numbers": {
        "white_balls": [28, 43, 7, 29, 3, 62, 52, 32, 8, 15],
        "powerballs": [25, 1, 2, 19, 20]
      },
      "cold_numbers": {
        "white_balls": [11, 63, 36, 20, 46, 21, 41, 38, 55, 56],
        "powerballs": [8, 13, 26, 16, 6]
      },
      "draws_analyzed": 100
    },
    "top_strategies": [
      {
        "name": "frequency_weighted",
        "weight": 0.1751,
        "total_plays": 432,
        "win_rate": 0.0185
      },
      {
        "name": "cooccurrence",
        "weight": 0.1523,
        "total_plays": 398,
        "win_rate": 0.0156
      }
    ],
    "predictions": {
      "next_draw_date": "2025-12-04",
      "total_tickets": 25,
      "sets": [
        {
          "strategy": "frequency_weighted",
          "tickets": [
            {"white_balls": [5, 12, 28, 43, 62], "powerball": 7, "confidence": 0.85},
            {"white_balls": [3, 17, 29, 52, 68], "powerball": 19, "confidence": 0.82},
            {"white_balls": [8, 22, 35, 48, 61], "powerball": 4, "confidence": 0.79},
            {"white_balls": [11, 26, 39, 55, 67], "powerball": 12, "confidence": 0.76},
            {"white_balls": [2, 19, 33, 46, 59], "powerball": 23, "confidence": 0.74}
          ]
        },
        {
          "strategy": "cooccurrence",
          "tickets": [
            {"white_balls": [7, 14, 28, 41, 56], "powerball": 9, "confidence": 0.81},
            {"white_balls": [4, 18, 32, 45, 63], "powerball": 15, "confidence": 0.78}
          ]
        }
      ]
    },
    "calculation_time_ms": 18.5
  },
  "from_cache": true,
  "cache_age_seconds": 45.2,
  "timestamp": "2025-12-03T10:30:00Z"
}
```

### Data Structure

- **draw_stats**: Draw statistics
  - `total_draws`: Total number of draws in database (all eras)
  - `most_recent`: Date of most recent draw (YYYY-MM-DD)
  - `current_era`: Number of draws in current era (Powerball 1-26)

- **hot_cold**: Hot and cold numbers analysis (last 100 draws)
  - `hot_numbers.white_balls`: Top 10 most frequent white balls
  - `hot_numbers.powerballs`: Top 5 most frequent powerballs
  - `cold_numbers.white_balls`: Top 10 least frequent white balls
  - `cold_numbers.powerballs`: Top 5 least frequent powerballs
  - `draws_analyzed`: Number of draws analyzed (100)

- **top_strategies**: Top 5 performing strategies
  - `name`: Strategy name
  - `weight`: Current adaptive weight (0-1)
  - `total_plays`: Total predictions generated
  - `win_rate`: Historical win rate

- **predictions**: Predictions for next draw
  - `next_draw_date`: Target draw date (YYYY-MM-DD)
  - `total_tickets`: Total tickets returned
  - `sets`: Array of prediction sets grouped by strategy
    - `strategy`: Strategy name
    - `tickets`: Array of tickets (max 5 per strategy)
      - `white_balls`: Array of 5 white ball numbers (1-69)
      - `powerball`: Powerball number (1-26)
      - `confidence`: Confidence score (0-1)

### Cache Metadata

- **from_cache** (boolean): `true` if response was served from cache
- **cache_age_seconds** (float): Age of cached data in seconds
- **calculation_time_ms** (float): Time to calculate data in ms (only when `from_cache: false`)

### Migration from Multiple Endpoints

**Before (3+ API calls):**
```javascript
// ❌ OLD WAY - Multiple calls, ~163ms with network latency
const [stats, hotCold, predictions] = await Promise.all([
  fetch('/api/v2/draw-stats'),
  fetch('/api/v2/hot-cold-numbers'),
  fetch('/api/v2/analytics/context')
]);
```

**After (1 API call):**
```javascript
// ✅ NEW WAY - Single call, ~51ms with network latency
const dashboard = await fetch('/api/v2/plp-dashboard');
const { draw_stats, hot_cold, top_strategies, predictions } = dashboard.data;
```

---

## 2. GET /api/v2/analytics/context ⚡ CACHED (Legacy)

> **Note**: Consider using `/api/v2/plp-dashboard` instead for a more complete response.

**Purpose**: Get pre-computed analytics data for dashboard (hot/cold numbers, momentum trends, gap patterns).

**⚡ Performance**:
- First request: ~600-800ms (full calculation)
- Cached requests: **<5ms** (cache TTL: 5 minutes)

### Request

```bash
curl -X GET "https://shiolplus.com/api/v2/analytics/context" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "hot_numbers": {
      "white_balls": [5, 18, 26, 47, 59, 7, 33, 50, 57, 66],
      "powerball": [
        [23, 0],
        [21, 2],
        [11, 9],
        [26, 12],
        [18, 14]
      ]
    },
    "cold_numbers": {
      "white_balls": [45, 42, 46, 41, 23, 1, 4, 34, 37, 43],
      "powerball": [
        [1, 45],
        [2, 42],
        [3, 40],
        [4, 38],
        [5, 35]
      ]
    },
    "momentum_trends": {
      "rising_numbers": [
        { "number": 5, "score": 0.95 },
        { "number": 10, "score": 0.82 }
      ],
      "falling_numbers": [
        { "number": 60, "score": -0.5 },
        { "number": 55, "score": -0.3 }
      ]
    },
    "gap_patterns": {
      "white_balls": {
        "1": 5,
        "2": 10,
        "3": 15
      },
      "powerball": {
        "1": 2,
        "2": 4,
        "3": 6
      }
    },
    "data_summary": {
      "total_draws": 2260,
      "most_recent_date": "2025-12-01",
      "current_era_draws": 1980
    }
  },
  "timestamp": "2025-12-03T10:30:00Z",
  "error": null,
  "from_cache": true,
  "cache_age_seconds": 45.2
}
```

### Cache Metadata Fields (NEW)

- **from_cache** (boolean): `true` if response was served from cache
- **cache_age_seconds** (float): Age of cached data in seconds (only when `from_cache: true`)
- **calculation_time_ms** (float): Time to calculate analytics in ms (only when `from_cache: false`)

### Data Structure

- **hot_numbers**: Most frequently drawn numbers recently (low gap)

  - `white_balls`: Top 10 hot white ball numbers (1-69)
  - `powerball`: Top 5 hot powerball numbers with gap values `[number, gap]`

- **cold_numbers**: Overdue numbers (high gap)

  - `white_balls`: Top 10 cold white ball numbers
  - `powerball`: Top 5 cold powerball numbers with gap values

- **momentum_trends**: Numbers with rising/falling frequency trends

  - `rising_numbers`: Numbers gaining momentum (positive scores)
  - `falling_numbers`: Numbers losing momentum (negative scores)

- **gap_patterns**: Days since last appearance for each number

  - `white_balls`: Object with number → days mapping
  - `powerball`: Object with number → days mapping

- **data_summary**: Overall statistics
  - `total_draws`: Total draws in database
  - `most_recent_date`: Most recent draw date (YYYY-MM-DD)
  - `current_era_draws`: Draws in current format (Powerball 1-26)

---

## 2. GET /api/v2/hot-cold-numbers ⚡ CACHED (NEW)

**Purpose**: Get hot and cold numbers based on the last 100 draws. Lightweight alternative to `/analytics/context`.

**⚡ Performance**:
- First request: ~4ms
- Cached requests: **<0.01ms** (cache TTL: 5 minutes)

### Request

```bash
curl -X GET "https://shiolplus.com/api/v2/hot-cold-numbers" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Response (200 OK)

```json
{
  "hot_numbers": {
    "white_balls": [28, 43, 7, 29, 3, 62, 52, 32, 8, 15],
    "powerballs": [25, 1, 2, 19, 20]
  },
  "cold_numbers": {
    "white_balls": [11, 63, 36, 20, 46, 21, 41, 38, 55, 56],
    "powerballs": [8, 13, 26, 16, 6]
  },
  "draws_analyzed": 100,
  "from_cache": true,
  "cache_age_seconds": 45.2
}
```

### Data Structure

- **hot_numbers**: Most frequently drawn in last 100 draws
  - `white_balls`: Top 10 hot white ball numbers (1-69)
  - `powerballs`: Top 5 hot powerball numbers (1-26)

- **cold_numbers**: Least frequently drawn in last 100 draws
  - `white_balls`: Bottom 10 cold white ball numbers
  - `powerballs`: Bottom 5 cold powerball numbers

- **draws_analyzed**: Number of draws used in calculation (always 100)
- **from_cache**: Whether response came from cache
- **cache_age_seconds**: Age of cache in seconds

---

## 3. GET /api/v2/draw-stats (NEW)

**Purpose**: Get draw statistics summary (total draws, most recent date, current era count).

### Request

```bash
curl -X GET "https://shiolplus.com/api/v2/draw-stats" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Response (200 OK)

```json
{
  "total_draws": 2260,
  "most_recent": "2025-12-01",
  "current_era": 1980,
  "timestamp": "2025-12-03T10:30:00Z"
}
```

### Data Structure

- **total_draws**: Total number of draws in database (all eras)
- **most_recent**: Date of the most recent draw (YYYY-MM-DD)
- **current_era**: Number of draws in current era (Powerball 1-26, since October 2015)

---

## 4. GET /api/v2/overview-enhanced ⚡ CACHED (NEW)

**Purpose**: Get comprehensive overview combining hot/cold numbers with strategy performance.

**⚡ Performance**: ~15ms (uses hot/cold cache internally)

### Request

```bash
curl -X GET "https://shiolplus.com/api/v2/overview-enhanced" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Response (200 OK)

```json
{
  "hot_cold_analysis": {
    "hot_numbers": {
      "white_balls": [28, 43, 7, 29, 3, 62, 52, 32, 8, 15],
      "powerballs": [25, 1, 2, 19, 20]
    },
    "cold_numbers": {
      "white_balls": [11, 63, 36, 20, 46, 21, 41, 38, 55, 56],
      "powerballs": [8, 13, 26, 16, 6]
    },
    "draws_analyzed": 100,
    "from_cache": true
  },
  "draw_stats": {
    "total_draws_current_era": 1980,
    "latest_draw_date": "2025-12-01"
  },
  "top_strategies": [
    {
      "name": "frequency_weighted",
      "weight": 0.0909,
      "predictions": 432,
      "win_rate": 0.0185
    }
  ],
  "response_time_ms": 12.5,
  "timestamp": "2025-12-03T10:30:00Z"
}
```

---

## 5. POST /api/v2/analytics/analyze-ticket

**Purpose**: Score a user's ticket (0-100) based on statistical quality (diversity, balance, potential).

### Request

```bash
curl -X POST "https://shiolplus.com/api/v2/analytics/analyze-ticket" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "white_balls": [7, 23, 34, 47, 62],
    "powerball": 15
  }'
```

**Request Body**:

```json
{
  "white_balls": [7, 23, 34, 47, 62],
  "powerball": 15
}
```

**Validation Rules**:

- `white_balls`: Array of exactly 5 unique integers (1-69)
- `powerball`: Integer (1-26)

### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "total_score": 79,
    "details": {
      "diversity": {
        "score": 0.8,
        "unique_decades": 4,
        "quality": "Good",
        "explanation": "Numbers spread across 4 of 7 possible ranges"
      },
      "balance": {
        "score": 0.75,
        "sum": 173,
        "sum_quality": "Optimal",
        "odd_count": 3,
        "even_count": 2,
        "ratio_quality": "Balanced",
        "explanation": "Sum=173 (Optimal), Odd/Even=3/2 (Balanced)"
      },
      "potential": {
        "score": 0.82,
        "hot_count": 3,
        "rising_count": 3,
        "quality": "Good",
        "explanation": "3 hot numbers, 3 with rising momentum (Good)"
      }
    },
    "recommendation": "Good ticket with solid fundamentals. POTENTIAL: Consider including more hot numbers or numbers with rising momentum (currently 3 hot, 3 rising)."
  },
  "timestamp": "2025-11-21T10:30:00Z",
  "error": null
}
```

### Scoring Components

- **Diversity Score (0.0-1.0)**: Spread across number ranges

  - 7 ranges: 1-9, 10-19, 20-29, 30-39, 40-49, 50-59, 60-69
  - Best: 5 unique ranges (score 1.0)
  - Good: 4 ranges (score 0.8)
  - Poor: 1-2 ranges (score <0.5)

- **Balance Score (0.0-1.0)**: Sum and odd/even ratio

  - Optimal sum range: 130-220
  - Optimal odd/even ratio: 2:3 or 3:2
  - Combined score based on both factors

- **Potential Score (0.0-1.0)**: Alignment with analytics

  - Hot numbers: Recently drawn (gap <30)
  - Rising momentum: Numbers with positive trends (score >0.2)
  - Higher score = more alignment with current trends

- **Total Score**: Average of 3 components × 100 (0-100 scale)

### Error Responses

**400 Bad Request** - Validation errors:

```json
{
  "success": false,
  "data": null,
  "timestamp": "2025-11-21T10:30:00Z",
  "error": "White ball numbers must be unique"
}
```

Common validation errors:

- "Must provide exactly 5 white ball numbers"
- "White ball numbers must be unique"
- "White ball numbers must be between 1 and 69"
- "Powerball must be between 1 and 26"

---

## 3. POST /api/v2/generator/interactive

**Purpose**: Generate custom lottery tickets based on user preferences (risk level, temperature, exclusions).

### Request

```bash
curl -X POST "https://shiolplus.com/api/v2/generator/interactive" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "risk": "high",
    "temperature": "hot",
    "exclude_numbers": [13, 7, 21],
    "count": 5
  }'
```

**Request Body**:

```json
{
  "risk": "high",
  "temperature": "hot",
  "exclude_numbers": [13, 7, 21],
  "count": 5
}
```

**Parameters**:

- `risk` (string, optional): Risk level for generation

  - `"low"`: Conservative (flatten probability distribution)
  - `"med"`: Balanced (default)
  - `"high"`: Aggressive (sharpen probability distribution)

- `temperature` (string, optional): Number preference

  - `"hot"`: Favor recently drawn numbers
  - `"neutral"`: Uniform distribution (default)
  - `"cold"`: Favor overdue numbers

- `exclude_numbers` (array, optional): Numbers to avoid

  - Max 20 numbers
  - Must be 1-69
  - Default: `[]` (no exclusions)

- `count` (integer, optional): Number of tickets to generate
  - Min: 1
  - Max: 10
  - Default: 5

### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "tickets": [
      {
        "rank": 1,
        "white_balls": [6, 11, 16, 22, 54],
        "powerball": 25,
        "strategy": "custom_interactive",
        "confidence": 0.8
      },
      {
        "rank": 2,
        "white_balls": [10, 29, 45, 53, 66],
        "powerball": 5,
        "strategy": "custom_interactive",
        "confidence": 0.78
      },
      {
        "rank": 3,
        "white_balls": [5, 33, 50, 57, 21],
        "powerball": 18,
        "strategy": "custom_interactive",
        "confidence": 0.75
      }
    ],
    "parameters": {
      "risk": "high",
      "temperature": "hot",
      "excluded_count": 3,
      "requested_count": 5,
      "generated_count": 3
    }
  },
  "timestamp": "2025-11-21T10:30:00Z",
  "error": null
}
```

### Response Fields

- **tickets**: Array of generated tickets

  - `rank`: Ticket ranking (1-based)
  - `white_balls`: 5 sorted white ball numbers (1-69)
  - `powerball`: Powerball number (1-26)
  - `strategy`: Always `"custom_interactive"`
  - `confidence`: Generation confidence (0.0-1.0)

- **parameters**: Echo of request parameters
  - Confirms what was processed
  - Shows actual counts (requested vs generated)

### Error Responses

**400 Bad Request** - Invalid parameters:

```json
{
  "success": false,
  "data": null,
  "timestamp": "2025-11-21T10:30:00Z",
  "error": "Invalid risk level 'extreme'. Must be 'low', 'med', or 'high'"
}
```

**422 Unprocessable Entity** - Validation errors:

```json
{
  "detail": [
    {
      "loc": ["body", "count"],
      "msg": "ensure this value is less than or equal to 10",
      "type": "value_error.number.not_le"
    }
  ]
}
```

Common validation errors:

- Invalid risk level (must be low/med/high)
- Invalid temperature (must be hot/cold/neutral)
- Count out of range (must be 1-10)
- Too many exclusions (max 20)
- Invalid exclusion numbers (must be 1-69)

---

## 🔧 Integration Examples

### JavaScript/TypeScript (Fetch API)

```typescript
const PLP_API_KEY = process.env.PREDICTLOTTOPRO_API_KEY;
const BASE_URL = "https://shiolplus.com";

// Get analytics context
async function getAnalyticsContext() {
  const response = await fetch(`${BASE_URL}/api/v2/analytics/context`, {
    headers: {
      Authorization: `Bearer ${PLP_API_KEY}`,
    },
  });
  return response.json();
}

// Analyze ticket
async function analyzeTicket(whiteBalls: number[], powerball: number) {
  const response = await fetch(`${BASE_URL}/api/v2/analytics/analyze-ticket`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${PLP_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      white_balls: whiteBalls,
      powerball: powerball,
    }),
  });
  return response.json();
}

// Generate tickets
async function generateTickets(params: {
  risk?: "low" | "med" | "high";
  temperature?: "hot" | "cold" | "neutral";
  exclude_numbers?: number[];
  count?: number;
}) {
  const response = await fetch(`${BASE_URL}/api/v2/generator/interactive`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${PLP_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(params),
  });
  return response.json();
}
```

### Python (requests library)

```python
import requests
import os

PLP_API_KEY = os.getenv('PREDICTLOTTOPRO_API_KEY')
BASE_URL = 'https://shiolplus.com'

headers = {
    'Authorization': f'Bearer {PLP_API_KEY}'
}

# Get analytics context
def get_analytics_context():
    response = requests.get(
        f'{BASE_URL}/api/v2/analytics/context',
        headers=headers
    )
    return response.json()

# Analyze ticket
def analyze_ticket(white_balls, powerball):
    response = requests.post(
        f'{BASE_URL}/api/v2/analytics/analyze-ticket',
        headers={**headers, 'Content-Type': 'application/json'},
        json={
            'white_balls': white_balls,
            'powerball': powerball
        }
    )
    return response.json()

# Generate tickets
def generate_tickets(risk='med', temperature='neutral', exclude_numbers=None, count=5):
    response = requests.post(
        f'{BASE_URL}/api/v2/generator/interactive',
        headers={**headers, 'Content-Type': 'application/json'},
        json={
            'risk': risk,
            'temperature': temperature,
            'exclude_numbers': exclude_numbers or [],
            'count': count
        }
    )
    return response.json()
```

---

## ⚠️ Rate Limits & Best Practices

**Current Limits**: No rate limiting implemented (subject to change)

**Best Practices**:

1. **Cache analytics context**: Update every 5-10 minutes max (data changes post-draw only)
2. **Batch ticket analysis**: Send multiple tickets in separate requests but throttle to ~10 req/sec
3. **Error handling**: Always check `success` field before using `data`
4. **API key security**: Never expose API key in client-side code
5. **Response time**: Analytics context takes ~605ms, plan UX accordingly

---

## 🐛 Troubleshooting

### Common Issues

**Issue**: `401 Unauthorized`

- **Cause**: Missing or malformed Authorization header
- **Fix**: Ensure header is `Authorization: Bearer YOUR_API_KEY`

**Issue**: `403 Forbidden`

- **Cause**: Invalid API key
- **Fix**: Verify `PREDICTLOTTOPRO_API_KEY` environment variable

**Issue**: `422 Validation Error`

- **Cause**: Request body doesn't match schema
- **Fix**: Check parameter types and ranges in error details

**Issue**: Slow response from `/analytics/context`

- **Cause**: Endpoint computes analytics on-the-fly (~605ms)
- **Fix**: Implement client-side caching, refresh every 5-10 minutes

---

## 📝 Changelog

### v2.3.0 (2025-12-03) - CURRENT

- ⭐ **NEW**: `/plp-dashboard` - **CONSOLIDATED ENDPOINT** (RECOMMENDED)
  - Returns ALL dashboard data in a single call
  - Includes: draw_stats + hot_cold + top_strategies + predictions
  - 5 sets of predictions (5 tickets each) for next draw date
  - **~112ms faster** than multiple endpoint calls (with network latency)
  - Cached for 5 minutes (<2ms on cache hit)
- ✅ **MIGRATION**: Use `/plp-dashboard` instead of multiple calls to `/draw-stats`, `/hot-cold-numbers`, `/analytics/context`

### v2.2.0 (2025-12-03)

- ✅ **NEW**: `/hot-cold-numbers` - Lightweight endpoint for hot/cold analysis (~0.01ms cached)
- ✅ **NEW**: `/draw-stats` - Quick draw statistics (total, recent, current era)
- ✅ **NEW**: `/overview-enhanced` - Comprehensive overview with strategy performance
- ✅ **PERF**: Added 5-minute TTL cache to `/analytics/context` (600ms → 3ms, **170x faster**)
- ✅ **PERF**: Hot/cold calculations cached (484x faster on subsequent requests)
- ✅ **META**: Response now includes `from_cache` and `cache_age_seconds` fields

### v2.1.0 (2025-11-21)

- ✅ Fixed response structure keys: `momentum` → `momentum_trends`, `gaps` → `gap_patterns`
- ✅ Added strict validation: max 10 tickets, max 20 exclusions
- ✅ Improved exclusion filter reliability
- ✅ Updated parameter name: `exclude` → `exclude_numbers`
- ✅ 100% test coverage (33/33 tests passing)

### v2.0.0 (2025-11-20)

- Initial release with 3 endpoints
- Core analytics engines integration
- API key authentication

---

## 📞 Support

**Issues**: Open issue at [github.com/orlandobatistac/SHIOL-PLUS](https://github.com/orlandobatistac/SHIOL-PLUS)
**Contact**: Orlando B. - [LinkedIn](https://www.linkedin.com/in/orlandobatista-ai/)
**Documentation**: See `docs/PLP_V2_ANALYTICS_ENDPOINTS.md` for detailed implementation notes

---

**Production URL**: https://shiolplus.com
**API Version**: v2.3.0
**Status**: ✅ Production Ready
**Last Verified**: 2025-12-03
