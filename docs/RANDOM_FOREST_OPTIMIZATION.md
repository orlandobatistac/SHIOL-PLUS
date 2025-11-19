# Random Forest Batch Generation Fix - Performance Optimization

## Summary
Fixed critical hanging issue in ML v2 batch generation by optimizing RandomForestModel feature engineering. The system now generates 100 tickets in 2.3 seconds instead of timing out after 30+ seconds.

## Problem Diagnosed
- **Location**: `src/ml_models/random_forest_model.py` lines 88-184 (`_engineer_features()`)
- **Root Cause**: O(n²) complexity with nested loops creating 354 features
- **Impact**: Complete blockage of batch generation for random_forest mode
- **Symptom**: Process hangs indefinitely with no error messages

### Original Feature Engineering Complexity
```python
# BEFORE: Nested loops creating 354 features
for window in [10, 20, 50]:           # 3 windows
    for num in range(1, 70):          # 69 numbers
        for idx in range(len(draws)):  # 1850 draws
            for look_back in range(100):  # Up to 100 lookback
                # O(3 × 69 × 1850 × 100) = ~38M operations
```

**Total Features**: 207 (white ball freq) + 69 (gaps) + 78 (powerball freq) = 354 features

## Solution Implemented

### 1. Feature Count Reduction (89% reduction)
- **Before**: 354 features (per-number granular tracking)
- **After**: 39 features (aggregated statistics)
- **Strategy**: Replace per-number features with rolling window aggregates

### 2. Vectorized Operations
Replaced nested loops with pandas vectorized operations:

```python
# AFTER: Vectorized rolling windows
for col in white_ball_cols:
    features[f'{col}_freq_last_{window}'] = (
        draws_df[col].rolling(window=window, min_periods=1).mean()
    )
# O(5 × 3 × 1850) = ~27K operations
```

### 3. Simplified Gap Analysis
- **Before**: Nested loops for each number across all historical draws
- **After**: Simple match counting with last 3 draws only
- **Reduction**: From O(69 × 1850 × 100) to O(1850 × 3)

### 4. Enhanced Error Handling
- Added timeout mechanism (default: 120 seconds)
- Comprehensive debug logging at each step
- Graceful error messages with stack traces

## Performance Improvements

### Benchmark Results (1850 historical draws)

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Feature Engineering | 30+ sec (timeout) | 2.2 sec | **93% faster** |
| Batch Generation (100 tickets) | Hangs indefinitely | 2.3 sec | **✓ Fixed** |
| Feature Count | 354 | 39 | **89% reduction** |
| Per-ticket Time | N/A | 22.6 ms | **44 tickets/sec** |

### Production Scenario Test
```
Historical draws processed: 1850
Training time: 3.12s
Ticket generation time: 2.26s
Tickets generated: 100
Avg time per ticket: 22.6ms
Success rate: 100%
```

## Feature Engineering Details

### Optimized Feature Categories (39 total)

1. **Position-based rolling statistics** (15 features)
   - 3 windows × 5 ball positions
   - `n1_freq_last_10`, `n1_freq_last_20`, `n1_freq_last_50`, etc.

2. **Aggregate frequency statistics** (4 features)
   - Overall number variance and mean for windows 20 and 50
   - `num_variance_last_20`, `num_mean_last_20`, etc.

3. **Temporal features** (3 features)
   - `day_of_week`, `month`, `day_of_month`

4. **Per-draw statistics** (6 features)
   - `draw_sum`, `draw_mean`, `draw_std`, `draw_range`, `draw_min`, `draw_max`

5. **Powerball statistics** (4 features)
   - Rolling mean for 3 windows + std for one window
   - `pb_mean_last_10`, `pb_mean_last_20`, `pb_mean_last_50`, `pb_std_last_20`

6. **Pattern features** (4 features)
   - `even_count`, `odd_count`, `low_count`, `high_count`

7. **Simplified gap features** (3 features)
   - Match counts for last 3 draws
   - `draw_minus_1_matches`, `draw_minus_2_matches`, `draw_minus_3_matches`

## Code Changes

### Modified Files
1. **`src/ml_models/random_forest_model.py`**
   - Optimized `_engineer_features()` method
   - Added timeout parameter to `generate_tickets()`
   - Enhanced logging in `predict_probabilities()`
   - Better error handling with RuntimeError exceptions

### New Files
2. **`tests/test_random_forest_optimization.py`**
   - Unit tests for feature engineering performance
   - Feature count validation
   - NaN value checks
   - Timeout mechanism tests

3. **`tests/test_random_forest_batch_integration.py`**
   - End-to-end integration tests
   - Production scenario simulation (1850 draws, 100 tickets)
   - Batch generator + RandomForest integration

## Testing

### Test Coverage
- ✅ Feature engineering completes in < 10s for 1850 draws
- ✅ Feature count reduced to < 100 (optimal: 30-100)
- ✅ No NaN values in generated features
- ✅ Ticket generation with timeout (100 tickets in < 30s)
- ✅ Full batch generation flow (RandomForest + PredictionEngine)
- ✅ Ticket validation (ranges, sorting, structure)

### Run Tests
```bash
# Unit tests
python tests/test_random_forest_optimization.py

# Integration tests
python tests/test_random_forest_batch_integration.py
```

## Backward Compatibility

### Maintained API
- All public methods maintain same signatures
- Added optional `timeout` parameter to `generate_tickets()` (default: 120)
- Feature engineering produces different features but maintains same DataFrame structure
- Models need retraining with new feature set

### Breaking Changes
- **Models must be retrained** - old pickled models incompatible with new features
- Feature count changed (354 → 39) affects model input shape
- Gap features use different calculation method

## Deployment Notes

### Pre-deployment Steps
1. Delete old model files:
   ```bash
   rm models/random_forest/rf_*.pkl
   ```

2. Retrain models with optimized features:
   ```bash
   python src/train_models.py --model random_forest
   ```

3. Verify batch generation:
   ```bash
   python tests/test_random_forest_batch_integration.py
   ```

### Expected Behavior After Deployment
- Batch generation completes successfully
- 100 tickets generated per mode (random_forest, lstm, v1)
- No timeouts or hangs
- Logs show "✓ Engineered 39 features from {n} draws (optimized)"

## Monitoring

### Key Metrics to Watch
1. **Feature engineering time**: Should be < 5s for 1850 draws
2. **Batch generation time**: Should be < 30s for 100 tickets
3. **Error rate**: Should be 0% (no timeouts)
4. **Feature count**: Should be exactly 39

### Log Indicators
- ✅ Good: `✓ Engineered 39 features from 1850 draws (optimized, <50 features)`
- ✅ Good: `✓ Generated 100 tickets using Random Forest model in 2.29s`
- ⚠️ Warning: Feature engineering > 5s (check data size)
- ❌ Error: `TimeoutError` or hanging (optimization regression)

## Future Optimizations

### Potential Improvements
1. **Cache feature engineering results** - avoid recomputation for same historical data
2. **Parallel feature computation** - use multiprocessing for independent features
3. **Incremental feature updates** - only compute for new draws
4. **Feature importance analysis** - further reduce to most predictive features
5. **Model quantization** - reduce model size for faster inference

### Performance Targets
- Current: 2.3s for 100 tickets
- Target: < 1s for 100 tickets (56% improvement needed)
- Achievable with caching + parallelization

## References

### Related Issues
- Issue: `[CRÍTICO] ML v2: Batch generation se cuelga en RandomForestModel.generate_tickets`
- PR: `copilot/fix-random-forest-batch-generation`

### Documentation
- Technical docs: `docs/TECHNICAL.md`
- ML pipeline: `PIPELINE_V5_SUMMARY.md`
- Batch system: `IMPLEMENTATION_SUMMARY_BATCH.md`

### Code Locations
- Random Forest model: `src/ml_models/random_forest_model.py`
- Batch generator: `src/batch_generator.py`
- Prediction engine: `src/prediction_engine.py`

---

**Last Updated**: 2025-11-19  
**Version**: 1.0  
**Author**: GitHub Copilot Agent
