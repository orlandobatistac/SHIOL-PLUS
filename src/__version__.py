"""
SHIOL+ Version Information

Version History:
- v5.0.0 (Oct 2025): Enhanced Pipeline v2.0 with era-aware system
- v4.0.0 (Sep 2025): Freemium model + PWA
- v3.0.0 (Aug 2025): Ticket verification with Gemini AI
- v2.0.0 (Jul 2025): ML predictions with XGBoost
- v1.0.0 (Jun 2025): Initial release
"""

__version__ = "5.0.0"
__version_info__ = (5, 0, 0)

# Component versions
PIPELINE_VERSION = "2.0"  # Enhanced Pipeline with 6 strategies
API_VERSION = "1.0"
DATABASE_SCHEMA_VERSION = "3.0"  # With era-aware triggers

# Release info
RELEASE_DATE = "2025-10-19"
RELEASE_NAME = "Enhanced Pipeline with Era-Aware System"

# Features in this version
FEATURES = [
    "6 parallel ML strategies with adaptive learning",
    "Era-aware data classification (2009-2015 historical preserved)",
    "Co-occurrence analysis with 1,490+ significant patterns",
    "Bayesian weight optimization",
    "Database triggers for automatic era classification",
    "REST API for predictions and performance metrics"
]
