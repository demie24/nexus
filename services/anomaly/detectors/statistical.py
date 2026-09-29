"""
Detector A — Statistical Anomaly Detection (Z-Score & Rolling Distribution)
Evaluates deviation from baseline/rolling distributions across physical signals.
"""

from typing import Dict, List, Any, Optional
from services.schemas import TelemetryCreate
from services.anomaly.baseline import MachineBaseline
from services.anomaly.config import get_anomaly_config


class StatisticalAnomalyDetector:
    def __init__(self):
        self.config = get_anomaly_config()

    def detect(
        self,
        telemetry: TelemetryCreate,
        features: Dict[str, Any],
        baseline: Optional[MachineBaseline] = None
    ) -> Dict[str, Any]:
        """
        Calculates Z-scores for monitored signals and produces structured detector evidence.
        """
        z_scores: Dict[str, float] = {}
        triggered_signals: List[str] = []
        raw = features["raw"]

        for sig in self.config.signals:
            curr_val = raw.get(sig)
            if curr_val is None:
                continue

            # Obtain mean and standard deviation
            if baseline and baseline.is_established(min_samples=self.config.min_baseline_samples_required):
                mean = baseline.get_mean(sig)
                std = baseline.get_std(sig)
            else:
                mean = features["rolling_means"].get(sig, curr_val)
                std = max(1e-3, features["rolling_stds"].get(sig, 1.0))

            z = abs(curr_val - mean) / max(std, 1e-4)
            z_scores[sig] = round(float(z), 2)

            if z >= self.config.z_score_warning_threshold:
                triggered_signals.append(sig)

        if not z_scores:
            return {
                "detector": "statistical_zscore",
                "score": 0.0,
                "primary_metric": "none",
                "max_z_score": 0.0,
                "z_scores": {},
                "triggered_signals": [],
            }

        # Primary metric is the signal with the highest deviation
        primary_metric = max(z_scores.items(), key=lambda kv: kv[1])[0]
        max_z = z_scores[primary_metric]

        # Normalized detector score mapped to [0.0, 1.0]
        # Z <= 1.0 -> ~0.10, Z=2.5 -> 0.50, Z=4.0 -> 0.80, Z>=5.0 -> 1.0
        if max_z <= 1.0:
            score = 0.10 * max_z
        elif max_z <= self.config.z_score_warning_threshold:
            # 1.0 to 2.5 maps to 0.10 to 0.50
            t = (max_z - 1.0) / (self.config.z_score_warning_threshold - 1.0)
            score = 0.10 + 0.40 * t
        elif max_z <= self.config.z_score_critical_threshold:
            # 2.5 to 4.0 maps to 0.50 to 0.85
            t = (max_z - self.config.z_score_warning_threshold) / (self.config.z_score_critical_threshold - self.config.z_score_warning_threshold)
            score = 0.50 + 0.35 * t
        else:
            # Above 4.0 maps to 0.85 to 1.00
            score = min(1.0, 0.85 + 0.05 * (max_z - self.config.z_score_critical_threshold))

        # Multi-signal trigger modifier: if >= 3 signals deviate simultaneously, reinforce score
        if len(triggered_signals) >= 3:
            score = min(1.0, score * 1.15)

        return {
            "detector": "statistical_zscore",
            "score": round(score, 3),
            "primary_metric": primary_metric,
            "max_z_score": max_z,
            "z_scores": z_scores,
            "triggered_signals": triggered_signals,
        }
