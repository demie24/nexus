"""
Predictive Baseline Models
Implements Persistence and Linear Degradation baseline models for benchmark comparison.
"""

from typing import Dict, List, Tuple
import numpy as np

from services.prediction.config import (
    DEFAULT_HORIZONS_MINUTES,
    CRITICAL_HEALTH_THRESHOLD,
    MAX_RUL_HOURS,
    FEATURE_NAMES,
)


HEALTH_CURRENT_IDX = FEATURE_NAMES.index("health_current")
HEALTH_SLOPE_IDX = FEATURE_NAMES.index("health_slope")


class PersistenceBaseline:
    """
    Persistence Baseline:
    Assumes current state persists indefinitely into future horizons.
    """
    def __init__(self, horizons_minutes: List[int] = DEFAULT_HORIZONS_MINUTES):
        self.horizons_minutes = horizons_minutes

    def predict_failure_probabilities(self, X: np.ndarray) -> Dict[int, np.ndarray]:
        """Returns 1.0 if current health <= 20.0 else 0.0."""
        health = X[:, HEALTH_CURRENT_IDX]
        probs = np.where(health <= CRITICAL_HEALTH_THRESHOLD, 1.0, 0.0)
        return {h: probs.copy() for h in self.horizons_minutes}

    def predict_health(self, X: np.ndarray) -> Dict[int, np.ndarray]:
        """Future health equals current health."""
        health = X[:, HEALTH_CURRENT_IDX]
        return {h: health.copy() for h in self.horizons_minutes}

    def predict_rul(self, X: np.ndarray) -> np.ndarray:
        """RUL is 0.0 if failed, else MAX_RUL_HOURS."""
        health = X[:, HEALTH_CURRENT_IDX]
        return np.where(health <= CRITICAL_HEALTH_THRESHOLD, 0.0, MAX_RUL_HOURS)


class LinearDegradationBaseline:
    """
    Linear Degradation Baseline:
    Extrapolates recent health trend slope forward in time.
    """
    def __init__(self, horizons_minutes: List[int] = DEFAULT_HORIZONS_MINUTES):
        self.horizons_minutes = horizons_minutes

    def predict_health(self, X: np.ndarray) -> Dict[int, np.ndarray]:
        """Extrapolates health linearly based on health_slope."""
        health = X[:, HEALTH_CURRENT_IDX]
        slope = X[:, HEALTH_SLOPE_IDX]  # slope per step (0.1 hours = 6 min)

        predictions = {}
        for h in self.horizons_minutes:
            steps_ahead = h / 6.0
            proj = health + slope * steps_ahead
            predictions[h] = np.clip(proj, 0.0, 100.0)
        return predictions

    def predict_rul(self, X: np.ndarray) -> np.ndarray:
        """Projects linear steps until health reaches CRITICAL_HEALTH_THRESHOLD."""
        health = X[:, HEALTH_CURRENT_IDX]
        slope = X[:, HEALTH_SLOPE_IDX]
        ruls = np.full(len(X), MAX_RUL_HOURS, dtype=float)

        for i in range(len(X)):
            if health[i] <= CRITICAL_HEALTH_THRESHOLD:
                ruls[i] = 0.0
            elif slope[i] < -0.01:
                steps_remaining = (health[i] - CRITICAL_HEALTH_THRESHOLD) / abs(slope[i])
                rul_hours = steps_remaining * 0.10  # 1 step = 0.10 hours
                ruls[i] = float(np.clip(rul_hours, 0.0, MAX_RUL_HOURS))
            else:
                ruls[i] = MAX_RUL_HOURS

        return ruls

    def predict_failure_probabilities(self, X: np.ndarray) -> Dict[int, np.ndarray]:
        """Estimates failure risk from linear projected RUL."""
        ruls = self.predict_rul(X)
        probs = {}
        for h in self.horizons_minutes:
            h_hours = h / 60.0
            # Smooth sigmoid around horizon boundary
            margin = ruls - h_hours
            p = 1.0 / (1.0 + np.exp(np.clip(margin * 1.5, -15.0, 15.0)))
            probs[h] = p
        return probs
