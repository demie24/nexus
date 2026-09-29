"""
Multi-Horizon Failure Classifier
Trained gradient boosting models for predicting calibrated failure probabilities across multiple horizons.
"""

from typing import Dict, List, Tuple, Any, Optional
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV

from services.prediction.config import (
    DEFAULT_HORIZONS_MINUTES,
    FEATURE_NAMES,
)


class MultiHorizonFailureClassifier:
    """
    Predicts calibrated failure probabilities for each horizon [60, 120, 240, 360] minutes.
    Enforces monotonic risk consistency (longer horizons have >= risk than shorter horizons).
    """
    def __init__(self, horizons_minutes: List[int] = DEFAULT_HORIZONS_MINUTES):
        self.horizons_minutes = sorted(horizons_minutes)
        self.models: Dict[int, Any] = {}
        self.feature_names = FEATURE_NAMES

    def fit(self, X: np.ndarray, y_failure: Dict[int, np.ndarray]) -> "MultiHorizonFailureClassifier":
        """Fits calibrated classifiers for each horizon."""
        for h in self.horizons_minutes:
            y_h = y_failure[h]
            unique_classes = np.unique(y_h)

            if len(unique_classes) <= 1:
                # Edge case: all 0s or all 1s
                self.models[h] = float(unique_classes[0]) if len(unique_classes) == 1 else 0.0
                continue

            base_clf = HistGradientBoostingClassifier(
                max_iter=100,
                max_depth=5,
                learning_rate=0.08,
                l2_regularization=1.0,
                random_state=42 + h
            )
            # Calibrated with sigmoid/isotonic via CV for strictly calibrated probabilities
            calibrated_clf = CalibratedClassifierCV(
                estimator=base_clf,
                method="sigmoid",
                cv=3
            )
            calibrated_clf.fit(X, y_h)
            self.models[h] = calibrated_clf

        return self

    def predict_proba(self, X: np.ndarray) -> Dict[int, np.ndarray]:
        """
        Predicts calibrated failure probabilities for each horizon.
        Enforces monotonic risk consistency: P(fail within H2) >= P(fail within H1) for H2 > H1.
        """
        raw_probs: Dict[int, np.ndarray] = {}
        n_samples = len(X)

        for h in self.horizons_minutes:
            model = self.models.get(h)
            if model is None:
                raw_probs[h] = np.zeros(n_samples)
            elif isinstance(model, float):
                raw_probs[h] = np.full(n_samples, model)
            else:
                probs = model.predict_proba(X)
                # Class 1 is failure
                if probs.shape[1] > 1:
                    raw_probs[h] = probs[:, 1]
                else:
                    raw_probs[h] = np.zeros(n_samples)

        # Enforce cumulative monotonicity: P(h_i) <= P(h_{i+1})
        monotonic_probs: Dict[int, np.ndarray] = {}
        running_max = np.zeros(n_samples)

        for h in self.horizons_minutes:
            p = np.clip(raw_probs[h], 0.0, 1.0)
            running_max = np.maximum(running_max, p)
            monotonic_probs[h] = running_max.copy()

        return monotonic_probs

    def explain_factors(self, x_vector: np.ndarray, top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Identifies top contributing factors for a single prediction vector.
        Uses directional deviations from nominal references and model weights.
        """
        factors = []
        # Index lookup
        for idx, feat_name in enumerate(self.feature_names):
            val = float(x_vector[idx])
            importance = 0.0
            impact = "stable"
            desc = ""

            if feat_name == "vib_current":
                if val > 3.0:
                    importance = min(1.0, (val - 2.5) / 5.0)
                    impact = "increases_risk"
                    desc = f"High vibration velocity ({val:.2f} mm/s) indicates mechanical wear"
            elif feat_name == "temp_current":
                if val > 75.0:
                    importance = min(1.0, (val - 65.0) / 25.0)
                    impact = "increases_risk"
                    desc = f"Elevated temperature ({val:.1f}°C) suggests thermal dissipation issues"
            elif feat_name == "vib_slope":
                if val > 0.02:
                    importance = min(1.0, val * 15.0)
                    impact = "increases_risk"
                    desc = f"Rapidly escalating vibration trend (+{val:.3f} mm/s per tick)"
            elif feat_name == "temp_slope":
                if val > 0.10:
                    importance = min(1.0, val * 5.0)
                    impact = "increases_risk"
                    desc = f"Continuous temperature ramp (+{val:.2f}°C per tick)"
            elif feat_name == "thermal_stress":
                if val > 5.0:
                    importance = min(1.0, val / 20.0)
                    impact = "increases_risk"
                    desc = f"Persistent thermal stress index ({val:.1f})"
            elif feat_name == "load_stress":
                if val > 1.15:
                    importance = min(1.0, (val - 1.0) / 0.5)
                    impact = "increases_risk"
                    desc = f"Machine operating above rated load ({val*100:.0f}%)"
            elif feat_name == "health_slope":
                if val < -0.05:
                    importance = min(1.0, abs(val) * 8.0)
                    impact = "increases_risk"
                    desc = f"Negative health score trajectory ({val:.2f}% per tick)"
            elif feat_name == "eff_slope":
                if val < -0.05:
                    importance = min(1.0, abs(val) * 6.0)
                    impact = "increases_risk"
                    desc = f"Declining operational efficiency ({val:.2f}% per tick)"

            if importance > 0.05:
                factors.append({
                    "factor_name": feat_name,
                    "metric_name": feat_name.split("_")[0],
                    "importance": round(float(importance), 4),
                    "impact_direction": impact,
                    "description": desc
                })

        # Sort by importance descending
        factors.sort(key=lambda x: x["importance"], reverse=True)
        if not factors:
            factors.append({
                "factor_name": "nominal_operation",
                "metric_name": "system",
                "importance": 0.1,
                "impact_direction": "stable",
                "description": "Operating within nominal parameters with stable trends"
            })
        return factors[:top_n]
