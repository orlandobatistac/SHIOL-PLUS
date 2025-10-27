"""
SHIOL+ Simple Utilities
=======================

Simple utility functions to replace complex modules.
"""

import numpy as np
from typing import Any, Dict

def convert_numpy_types(obj):
    """Convert numpy types to native Python types for JSON serialization"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    return obj

def format_prediction_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Format prediction response for API"""
    return convert_numpy_types(data)
