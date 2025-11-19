# Advanced ML Models for SHIOL+

This directory contains advanced machine learning models for lottery prediction:

## Models

### 1. LSTM Model (`lstm_model.py`)
Long Short-Term Memory neural network for temporal pattern analysis.

**Features:**
- Sequence-based learning from historical draw patterns
- Separate LSTM models for white balls and powerball
- Configurable sequence length, units, and dropout
- Early stopping to prevent overfitting
- Model checkpointing for best performance

**Requirements:**
- TensorFlow/Keras (optional dependency)
- Install with: `pip install tensorflow`

**Usage:**
```python
from src.ml_models.lstm_model import LSTMModel

# Initialize
model = LSTMModel(
    sequence_length=20,
    lstm_units=128,
    dropout_rate=0.3
)

# Train on historical data
metrics = model.train(draws_df, epochs=50)

# Generate predictions
tickets = model.generate_tickets(draws_df, count=5)
```

**Architecture:**
- Input: Sequence of historical draws (default: 20 draws)
- LSTM Layer 1: 128 units with return sequences
- LSTM Layer 2: 64 units
- Dense layers with dropout (0.3)
- Output: Softmax probabilities for 69 white balls and 26 powerballs

### 2. Random Forest Model (`random_forest_model.py`)
Ensemble method using multiple decision trees for robust predictions.

**Features:**
- **Optimized feature engineering** (v7.0 - Nov 2025):
  - **39 features** (reduced from 354 for 89% improvement)
  - Vectorized pandas operations (no O(n²) loops)
  - Frequency analysis (10/20/50 draw windows)
  - Simplified gap analysis (last 3 draws only)
  - Temporal features (day of week, month)
  - Statistical features (sum, mean, std, range)
- Separate models for each white ball position + powerball
- Feature scaling for improved performance
- No external dependencies beyond scikit-learn
- **Performance**: Generates 100 tickets in 2.3 seconds

**Usage:**
```python
from src.ml_models.random_forest_model import RandomForestModel

# Initialize
model = RandomForestModel(
    n_estimators=200,
    max_depth=20
)

# Train on historical data
metrics = model.train(draws_df, test_size=0.2)

# Generate predictions (with timeout)
tickets = model.generate_tickets(draws_df, count=5, timeout=120)
```

**Architecture:**
- Feature engineering: **39 optimized features** (v7.0)
- 5 Random Forest classifiers for white ball positions
- 1 Random Forest classifier for powerball
- 200 trees per forest with max depth 20

**Optimization Details**: See `docs/RANDOM_FOREST_OPTIMIZATION.md` for complete performance analysis.

## Model Registry

The `__init__.py` file provides a model registry for easy model access:

```python
from src.ml_models import get_model

# Get Random Forest model
rf_model = get_model('random_forest')

# Get LSTM model
lstm_model = get_model('lstm')
```

## Training Pipeline

Use `src/train_models.py` to train models on historical data:

```bash
# Train all models
python src/train_models.py --model all

# Train only Random Forest
python src/train_models.py --model random_forest --n-estimators 200

# Train only LSTM
python src/train_models.py --model lstm --epochs 50 --batch-size 32
```

## Integration with Prediction Engine

The models integrate seamlessly with the UnifiedPredictionEngine:

```python
from src.prediction_engine import UnifiedPredictionEngine

# Use Random Forest mode
engine = UnifiedPredictionEngine(mode='random_forest')
tickets = engine.generate_tickets(count=5)

# Use LSTM mode
engine = UnifiedPredictionEngine(mode='lstm')
tickets = engine.generate_tickets(count=5)
```

Or via environment variable:
```bash
PREDICTION_MODE=random_forest python main.py
PREDICTION_MODE=lstm python main.py
```

## Model Comparison

| Model | Strengths | Requirements | Speed |
|-------|-----------|--------------|-------|
| Random Forest | Robust, interpretable, fast | scikit-learn (included) | Fast |
| LSTM | Captures temporal patterns | TensorFlow (optional) | Slower |
| XGBoost (v2) | High accuracy, boosting | XGBoost (included) | Fast |
| Strategies (v1) | Diverse, adaptive | None | Very Fast |

## Testing

Run tests with:
```bash
pytest tests/test_advanced_models.py -v
```

## Demo

See the models in action:
```bash
python scripts/demo_advanced_models.py
```

## Performance Notes

- **Random Forest**: Best for production use (fast, no extra dependencies)
- **LSTM**: Best for research and temporal pattern analysis (requires TensorFlow)
- Both models support graceful fallback to v1 mode if unavailable

## Model Storage

Trained models are saved to:
- Random Forest: `models/random_forest/`
- LSTM: `models/lstm/`

Models are automatically loaded if available, otherwise you can train new ones.
