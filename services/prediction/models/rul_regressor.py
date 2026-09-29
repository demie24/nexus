"""
Remaining Useful Life (RUL) Regressor
Predicts continuous RUL in operating hours along with calibrated uncertainty bounds [rul_lower, rul_upper].
"""

from typing import Tuple, Optional
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from services.prediction.config import (
    CRITICAL_HEALTH_THRESHOLD,
    MAX_RUL_HOURS,
    CONFIDENCE_LEVEL,
    FEATURE_NAMES,
)

HEALTH_CURRENT_IDX = FEATURE_NAMES.index("health_current")


class RULRegressor:
    """
    RUL estimator utilizing Gradient Boosting with quantile regression for uncertainty intervals.
    Outputs:
        point_estimate, rul_lower (10th percentile), rul_upper (90th percentile).
    """
    def __init__(self, max_rul_hours: float = MAX_RUL_HOURS):
        self.max_rul_hours = max_rul_hours
        self.point_model = HistGradientBoostingRegressor(
            loss="squared_error",
            max_iter=120,
            max_depth=5,
            learning_rate=0.08,
            random_state=42
        )
        self.lower_model = HistGradientBoostingRegressor(
            loss="quantile",
            quantile=0.10,
            max_iter=100,
            max_depth=4,
            learning_rate=0.08,
            random_state=43
        )
        self.upper_model = HistGradientBoostingRegressor(
            loss="quantile",
            quantile=0.90,
            max_iter=100,
            max_depth=4,
            learning_rate=0.08,
            random_state=44
        )

    def fit(self, X: np.ndarray, y_rul: np.ndarray) -> "RULRegressor":
        """Fits point and quantile models."""
        self.point_model.fit(X, y_rul)
        self.lower_model.fit(X, y_rul)
        self.upper_model.fit(X, y_rul)
        return self

    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Predicts RUL point estimate, lower bound, and upper bound in hours.
        Enforces physical bounds: 0.0 <= rul_lower <= rul <= rul_upper.
        """
        raw_point = self.point_model.predict(X)
        raw_low = self.lower_model.predict(X)
        raw_high = self.upper_model.predict(X)

        n = len(X)
        point_out = np.zeros(n, dtype=float)
        low_out = np.zeros(n, dtype=float)
        high_out = np.zeros(n, dtype=float)

        healths = X[:, HEALTH_CURRENT_IDX]

        for i in range(n):
            if healths[i] <= CRITICAL_HEALTH_THRESHOLD:
                point_out[i] = 0.0
                low_out[i] = 0.0
                high_out[i] = 0.0
            else:
                pt = float(np.clip(raw_point[i], 0.0, self.max_rul_hours))
                low = float(np.clip(raw_low[i], 0.0, pt))
                high = float(np.clip(max(pt, raw_high[i]), pt, self.max_rul_hours * 1.25))

                point_out[i] = pt
                low_out[i] = low
                high_out[i] = high

        return point_out, low_out, high_out
