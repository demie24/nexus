"""
NEXUS Diagnostics Temporal Reasoning Engine
Extracts temporal dynamics, onset detection, signal trend slopes (dM/dt),
persistence metrics, and deterioration sequences.

CRITICAL INTEGRITY REQUIREMENT:
No future information may be utilized during retrospective or runtime diagnosis.
All observations strictly adhere to t <= analysis_timestamp.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

from services.schemas import SignalDirection, TelemetryCreate


class TemporalReasoningEngine:
    """
    Evaluates temporal order of events, persistence of deviations, and rate of drift.
    """

    @staticmethod
    def enforce_no_future_leakage(
        telemetry_records: List[TelemetryCreate],
        analysis_timestamp: datetime
    ) -> List[TelemetryCreate]:
        """
        Strictly truncates and sorts telemetry records to ensure no record beyond
        analysis_timestamp enters the diagnostic pipeline.
        Handles both timezone-aware and timezone-naive comparisons safely.
        """
        def _to_utc_naive(dt: datetime) -> datetime:
            if dt.tzinfo is not None:
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt

        target_dt = _to_utc_naive(analysis_timestamp)
        valid_records = [
            r for r in telemetry_records
            if _to_utc_naive(r.timestamp) <= target_dt
        ]
        valid_records.sort(key=lambda r: _to_utc_naive(r.timestamp))
        return valid_records

    @staticmethod
    def calculate_trend_slope(values: List[float]) -> float:
        """
        Computes the Ordinary Least Squares (OLS) linear slope over sequential discrete ticks.
        Returns normalized change per tick.
        """
        n = len(values)
        if n < 3:
            return 0.0
        x = np.arange(n, dtype=float)
        y = np.array(values, dtype=float)
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        denom = np.sum((x - x_mean) ** 2)
        if denom == 0:
            return 0.0
        return float(np.sum((x - x_mean) * (y - y_mean)) / denom)

    @classmethod
    def evaluate_signal_dynamics(
        cls,
        series: List[float],
        baseline_mean: float,
        baseline_std: float,
        threshold_std: float = 2.0
    ) -> Dict[str, Any]:
        """
        Evaluates onset index, direction, persistence, and slope for a single signal stream.
        """
        n = len(series)
        if n == 0:
            return {
                "direction": SignalDirection.STABLE,
                "slope": 0.0,
                "persistence": 0.0,
                "onset_idx": -1,
                "is_persistent": False,
                "is_spike": False,
            }

        std_eff = max(0.001, baseline_std)
        z_scores = [(v - baseline_mean) / std_eff for v in series]
        deviating_indices = [i for i, z in enumerate(z_scores) if abs(z) >= threshold_std]

        # Onset index: first tick where deviation crossed threshold
        onset_idx = deviating_indices[0] if deviating_indices else -1
        persistence = len(deviating_indices) / float(n)

        slope = cls.calculate_trend_slope(series)

        # Distinguish sudden isolated spike vs persistent drift vs step change
        is_spike = len(deviating_indices) <= 2 and persistence < 0.20 and len(deviating_indices) > 0
        is_persistent = persistence >= 0.40 or (len(deviating_indices) >= 3 and abs(z_scores[-1]) >= threshold_std)

        # Determine directional movement
        recent_val = np.mean(series[-max(1, int(n * 0.3)):])
        net_dev = (recent_val - baseline_mean) / std_eff

        if is_spike:
            direction = SignalDirection.SPIKE
        elif net_dev >= 1.5 or slope > 0.05 * std_eff:
            direction = SignalDirection.INCREASING
        elif net_dev <= -1.5 or slope < -0.05 * std_eff:
            direction = SignalDirection.DECREASING
        else:
            direction = SignalDirection.STABLE

        return {
            "direction": direction,
            "slope": round(float(slope), 4),
            "persistence": round(float(persistence), 3),
            "onset_idx": onset_idx,
            "is_persistent": is_persistent,
            "is_spike": is_spike,
            "net_dev_z": round(float(net_dev), 2)
        }

    @classmethod
    def analyze_sequence_order(
        cls,
        series_map: Dict[str, List[float]],
        baselines: Dict[str, Tuple[float, float]]
    ) -> List[Tuple[str, int]]:
        """
        Determines the chronological order in which signals started deviating.
        Returns sorted list of (signal_name, onset_tick_index).
        """
        onset_list = []
        for sig, series in series_map.items():
            if sig in baselines:
                b_mean, b_std = baselines[sig]
                dyn = cls.evaluate_signal_dynamics(series, b_mean, b_std)
                if dyn["onset_idx"] >= 0:
                    onset_list.append((sig, dyn["onset_idx"]))

        onset_list.sort(key=lambda item: item[1])
        return onset_list
