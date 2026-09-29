"""
Health Trajectory Forecaster
Projects machine health scores across future horizons [60, 120, 240, 360] minutes.
"""

from typing import Dict, List
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from services.prediction.config import (
    DEFAULT_HORIZONS_MINUTES,
    CRITICAL_HEALTH_THRESHOLD,
    FEATURE_NAMES,
)

HEALTH_CURRENT_IDX = FEATURE_NAMES.index("health_current")


class HealthTrajectoryForecaster:
    """
    Multi-horizon health degradation forecaster.
    Projects future health scores (0-100%) for each future horizon.
    """
    def __init__(self, horizons_minutes: List[int] = DEFAULT_HORIZONS_MINUTES):
        self.horizons_minutes = sorted(horizons_minutes)
        self.models: Dict[int, HistGradientBoostingRegressor] = {
            h: HistGradientBoostingRegressor(
                loss="squared_error",
                max_iter=100,
                max_depth=5,
                learning_rate=0.08,
                random_state=42 + h
            )
            for h in self.horizons_minutes
        }

    def fit(self, X: np.ndarray, y_health: Dict[int, np.ndarray]) -> "HealthTrajectoryForecaster":
        """Fits health regression models for each horizon."""
        for h in self.horizons_minutes:
            self.models[h].fit(X, y_health[h])
        return self

    def predict(self, X: np.ndarray) -> Dict[int, np.ndarray]:
        """
        Predicts future health scores for each horizon.
        Bounds predictions between [0.0, 100.0] and enforces physical constraints.
        """
        n = len(X)
        current_health = X[:, HEALTH_CURRENT_IDX]
        results: Dict[int, np.ndarray] = {}

        for h in self.horizons_minutes:
            raw_pred = self.models[h].predict(X)
            bounded = np.clip(raw_pred, 0.0, 100.0)

            # Machines already failed stay at 0.0 health
            for i in range(n):
                if current_health[i] <= CRITICAL_HEALTH_THRESHOLD:
                    bounded[i] = 0.0

            results[h] = bounded

        return results
