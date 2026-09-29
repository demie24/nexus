"""
NEXUS Feature Engineering Pipeline for Anomaly Detection
Extracts raw, rolling statistical, trend slopes, and load-normalized features
without data leakage (strictly historical).
"""

from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Any
import numpy as np

from services.schemas import TelemetryCreate
from services.anomaly.baseline import MachineBaseline


class AnomalyFeatureExtractor:
    def __init__(self, window_size: int = 15):
        self.window_size = window_size
        # Rolling buffer per machine: machine_id -> deque of TelemetryCreate
        self._history_buffers: Dict[str, deque[TelemetryCreate]] = {}

    def push_telemetry(self, telemetry: TelemetryCreate) -> None:
        m_id = telemetry.machine_id
        if m_id not in self._history_buffers:
            self._history_buffers[m_id] = deque(maxlen=self.window_size)
        self._history_buffers[m_id].append(telemetry)

    def get_history(self, machine_id: str) -> List[TelemetryCreate]:
        return list(self._history_buffers.get(machine_id, []))

    def clear(self, machine_id: Optional[str] = None) -> None:
        if machine_id:
            self._history_buffers.pop(machine_id, None)
        else:
            self._history_buffers.clear()

    @staticmethod
    def calculate_slope(values: List[float]) -> float:
        """Computes ordinary least squares slope over discrete sequential ticks."""
        n = len(values)
        if n < 2:
            return 0.0
        x = np.arange(n, dtype=float)
        y = np.array(values, dtype=float)
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        denom = np.sum((x - x_mean) ** 2)
        if denom == 0:
            return 0.0
        return float(np.sum((x - x_mean) * (y - y_mean)) / denom)

    def extract_features(
        self,
        current: TelemetryCreate,
        baseline: Optional[MachineBaseline] = None
    ) -> Dict[str, Any]:
        """
        Extracts a structured feature dictionary containing raw values, rolling stats,
        slopes, percentage deviations, and load-normalized features.
        """
        m_id = current.machine_id
        history = list(self._history_buffers.get(m_id, []))
        if not history or history[-1] != current:
            history = history + [current]

        # 1. Raw signals
        signals = [
            "temperature", "vibration", "pressure", "current",
            "voltage", "rpm", "power_kw", "efficiency", "output_rate", "load"
        ]
        raw_values = {sig: getattr(current, sig, 0.0) for sig in signals}

        # 2. Rolling statistics across the window
        rolling_means: Dict[str, float] = {}
        rolling_stds: Dict[str, float] = {}
        slopes: Dict[str, float] = {}
        streak_directions: Dict[str, int] = {}

        for sig in signals:
            series = [getattr(t, sig, 0.0) for t in history]
            rolling_means[sig] = float(np.mean(series))
            rolling_stds[sig] = float(np.std(series)) if len(series) > 1 else 0.0
            slopes[sig] = self.calculate_slope(series)

            # Monotonic streak: consecutive increments (+) or decrements (-)
            streak = 0
            if len(series) >= 2:
                for i in range(len(series) - 1, 0, -1):
                    diff = series[i] - series[i - 1]
                    if diff > 1e-4:
                        if streak >= 0:
                            streak += 1
                        else:
                            break
                    elif diff < -1e-4:
                        if streak <= 0:
                            streak -= 1
                        else:
                            break
                    else:
                        break
            streak_directions[sig] = streak

        # 3. Deviations from baseline
        pct_deviations: Dict[str, float] = {}
        if baseline:
            for sig in signals:
                b_mean = baseline.get_mean(sig)
                curr_val = raw_values[sig]
                if abs(b_mean) > 1e-4:
                    pct_deviations[sig] = round((curr_val - b_mean) / b_mean * 100.0, 2)
                else:
                    pct_deviations[sig] = 0.0

        # 4. Load-normalized features
        load_factor = max(0.05, current.load)
        load_normalized = {
            "power_per_load": round(current.power_kw / load_factor, 2),
            "current_per_load": round(current.current / load_factor, 2),
            "temp_per_load": round(current.temperature / load_factor, 2),
        }

        # 5. ML Feature Vector (for Isolation Forest)
        ml_vector = [
            current.temperature,
            current.vibration,
            current.pressure,
            current.current,
            current.voltage,
            current.rpm,
            current.power_kw,
            current.load,
            current.efficiency,
            current.output_rate,
        ]

        return {
            "machine_id": m_id,
            "timestamp": current.timestamp,
            "raw": raw_values,
            "rolling_means": rolling_means,
            "rolling_stds": rolling_stds,
            "slopes": slopes,
            "streaks": streak_directions,
            "pct_deviations": pct_deviations,
            "load_normalized": load_normalized,
            "ml_vector": ml_vector,
            "history_depth": len(history),
        }


_feature_extractor = AnomalyFeatureExtractor()


def get_feature_extractor() -> AnomalyFeatureExtractor:
    return _feature_extractor
