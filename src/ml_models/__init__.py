"""
SHIOL+ Advanced ML Models
=========================
Advanced machine learning models for lottery prediction including:
- LSTM: Temporal pattern analysis using sequence modeling
- Random Forest: Ensemble predictions using multiple decision trees

Model Registry for easy access and management.
"""

from typing import Dict, Any, Optional
from loguru import logger

# Model registry for dynamic model loading
MODEL_REGISTRY = {
    'lstm': 'src.ml_models.lstm_model.LSTMModel',
    'random_forest': 'src.ml_models.random_forest_model.RandomForestModel',
}


def get_model(model_name: str, **kwargs) -> Optional[Any]:
    """
    Factory function to get a model instance by name.
    
    Args:
        model_name: Name of the model ('lstm' or 'random_forest')
        **kwargs: Additional arguments to pass to model constructor
        
    Returns:
        Model instance or None if model not found
    """
    if model_name not in MODEL_REGISTRY:
        logger.error(f"Model '{model_name}' not found in registry. Available: {list(MODEL_REGISTRY.keys())}")
        return None
    
    try:
        # Import model class dynamically
        module_path, class_name = MODEL_REGISTRY[model_name].rsplit('.', 1)
        module = __import__(module_path, fromlist=[class_name])
        model_class = getattr(module, class_name)
        
        # Instantiate and return
        return model_class(**kwargs)
    except Exception as e:
        logger.error(f"Failed to load model '{model_name}': {e}")
        return None


__all__ = ['get_model', 'MODEL_REGISTRY']
