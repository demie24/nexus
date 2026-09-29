"""
NEXUS Predictive Intelligence Package
Exports PredictiveIntelligenceEngine, FeatureExtractor, and Training facilities.
"""

from services.prediction.config import (
    DEFAULT_HORIZONS_MINUTES,
    PRIMARY_HORIZON_MINUTES,
    CRITICAL_HEALTH_THRESHOLD,
    MAX_RUL_HOURS,
    MODEL_VERSION,
    FEATURE_VERSION,
)
from services.prediction.features import PredictiveFeatureExtractor
from services.prediction.engine import PredictiveIntelligenceEngine, get_prediction_engine
from services.prediction.training import PredictiveSuite, train_predictive_suite

__all__ = [
    "PredictiveIntelligenceEngine",
    "get_prediction_engine",
    "PredictiveFeatureExtractor",
    "PredictiveSuite",
    "train_predictive_suite",
    "DEFAULT_HORIZONS_MINUTES",
    "PRIMARY_HORIZON_MINUTES",
    "CRITICAL_HEALTH_THRESHOLD",
    "MAX_RUL_HOURS",
    "MODEL_VERSION",
    "FEATURE_VERSION",
]
