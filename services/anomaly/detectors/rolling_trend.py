"""
Detector B — Rolling Trend & Drift Detection
Identifies behavioral drift over time by analyzing slope, rate of change, and monotonic persistence.
"""

from typing import Dict, List, Any
from services.schemas import TelemetryCreate
from services.anomaly.config import get_anomaly_config


class RollingTrendDetector:
    def __init__(self):
        self.config = get_anomaly_config()

    def detect(
        self,
        telemetry: TelemetryCreate,
        features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluates linear regression slopes and monotonic streaks across the recent window.
        """
        history_depth = features.get("history_depth", 1)
        if history_depth < self.config.trend_min_samples:
            # Insufficient temporal window to compute meaningful slope
            return {
                "detector": "rolling_trend",
                "score": 0.0,
                "trending_signals": [],
                "slopes": {},
                "streaks": {},
                "explanation": "Insufficient history window for trend estimation"
            }

        slopes = features["slopes"]
        streaks = features["streaks"]
        trending_signals: List[str] = []
        signal_scores: List[float] = []

        for sig, threshold in self.config.slope_thresholds.items():
            curr_slope = slopes.get(sig, 0.0)
            curr_streak = streaks.get(sig, 0)

            # Check if slope exceeds threshold in the dangerous direction
            is_trending = False
            ratio = 0.0

            if threshold > 0:
                # Upward trending is dangerous (temperature, vibration, power, current)
                if curr_slope > 0:
                    ratio = curr_slope / threshold
                    if curr_slope >= threshold or curr_streak >= self.config.monotonic_streak_threshold:
                        is_trending = True
            else:
                # Downward trending is dangerous (efficiency)
                if curr_slope < 0:
                    ratio = abs(curr_slope) / abs(threshold)
                    if curr_slope <= threshold or curr_streak <= -self.config.monotonic_streak_threshold:
                        is_trending = True

            if is_trending:
                trending_signals.append(sig)

            # Map ratio to sub-score
            sub_score = min(1.0, max(0.0, ratio * 0.50))
            if abs(curr_streak) >= self.config.monotonic_streak_threshold:
                sub_score = min(1.0, sub_score + 0.25)
            signal_scores.append(sub_score)

        if not signal_scores:
            base_score = 0.0
        else:
            # Base score is weighted by the top trending signal plus breadth
            max_sig_score = max(signal_scores)
            breadth_factor = min(0.3, len(trending_signals) * 0.10)
            base_score = min(1.0, max_sig_score + breadth_factor)

        return {
            "detector": "rolling_trend",
            "score": round(base_score, 3),
            "trending_signals": trending_signals,
            "slopes": {k: round(v, 4) for k, v in slopes.items() if k in self.config.slope_thresholds},
            "streaks": {k: v for k, v in streaks.items() if k in self.config.slope_thresholds},
        }
