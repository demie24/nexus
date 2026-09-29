"""
Predictive Models Package
Exports Baselines, Multi-Horizon Failure Classifier, RUL Regressor, and Health Forecaster.
"""

from services.prediction.models.baselines import (
    PersistenceBaseline,
    LinearDegradationBaseline,
)
from services.prediction.models.failure_classifier import MultiHorizonFailureClassifier
from services.prediction.models.rul_regressor import RULRegressor
from services.prediction.models.health_forecaster import HealthTrajectoryForecaster

__all__ = [
    "PersistenceBaseline",
    "LinearDegradationBaseline",
    "MultiHorizonFailureClassifier",
    "RULRegressor",
    "HealthTrajectoryForecaster",
]
