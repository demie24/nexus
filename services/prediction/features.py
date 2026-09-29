"""
Predictive Feature Engineering
Extracts strictly historical time-series features (rolling stats, slopes, degradation indices)
without data leakage.
"""

from collections import deque
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

from services.schemas import TelemetryCreate
from services.prediction.config import (
    FEATURE_NAMES,
    WINDOW_SIZE,
    COLD_START_MIN_SAMPLES,
)


class PredictiveFeatureExtractor:
    def __init__(self, window_size: int = WINDOW_SIZE):
        self.window_size = window_size
        # machine_id -> deque of (TelemetryCreate, health_score: float)
        self._buffers: Dict[str, deque[Tuple[TelemetryCreate, float]]] = {}

    def push(self, telemetry: TelemetryCreate, health_score: float = 100.0) -> None:
        """Pushes a new telemetry observation and its associated health score."""
        m_id = telemetry.machine_id
        if m_id not in self._buffers:
            self._buffers[m_id] = deque(maxlen=self.window_size)
        self._buffers[m_id].append((telemetry, float(health_score)))

    def get_sample_count(self, machine_id: str) -> int:
        """Returns the number of historical samples available for a machine."""
        return len(self._buffers.get(machine_id, []))

    def has_sufficient_history(self, machine_id: str) -> bool:
        """Checks if machine has met the cold start minimum sample threshold."""
        return self.get_sample_count(machine_id) >= COLD_START_MIN_SAMPLES

    def clear(self, machine_id: Optional[str] = None) -> None:
        """Clears memory buffers."""
        if machine_id:
            self._buffers.pop(machine_id, None)
        else:
            self._buffers.clear()

    @staticmethod
    def calculate_slope(values: List[float]) -> float:
        """Calculates ordinary least squares slope over sequential discrete steps."""
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
        machine_id: str,
        current_telemetry: Optional[TelemetryCreate] = None,
        current_health: Optional[float] = None
    ) -> Tuple[Optional[Dict[str, float]], Optional[np.ndarray]]:
        """
        Extracts temporal and physical features from the rolling window.
        Returns:
            Tuple of (feature_dict, feature_vector_numpy) or (None, None) if cold start.
        """
        if current_telemetry is not None:
            health = 100.0 if current_health is None else float(current_health)
            self.push(current_telemetry, health)

        buffer = self._buffers.get(machine_id)
        if not buffer or len(buffer) < COLD_START_MIN_SAMPLES:
            return None, None

        history = list(buffer)
        telemetries = [item[0] for item in history]
        healths = [item[1] for item in history]

        latest_t = telemetries[-1]
        latest_h = healths[-1]

        # 1. Raw current metrics
        temp_current = float(latest_t.temperature)
        vib_current = float(latest_t.vibration)
        pressure_current = float(latest_t.pressure)
        current_a = float(latest_t.current)
        voltage_v = float(latest_t.voltage)
        rpm_val = float(latest_t.rpm)
        power_kw_val = float(latest_t.power_kw)
        load_val = float(latest_t.load)
        eff_val = float(latest_t.efficiency)
        output_rate = float(latest_t.output_rate)

        # 2. Rolling series
        temps = [t.temperature for t in telemetries]
        vibs = [t.vibration for t in telemetries]
        pressures = [t.pressure for t in telemetries]
        currents = [t.current for t in telemetries]
        powers = [t.power_kw for t in telemetries]
        effs = [t.efficiency for t in telemetries]
        loads = [t.load for t in telemetries]

        # 3. Rolling stats & slopes
        temp_mean = float(np.mean(temps))
        temp_std = float(np.std(temps))
        temp_slope = self.calculate_slope(temps)

        vib_mean = float(np.mean(vibs))
        vib_std = float(np.std(vibs))
        vib_slope = self.calculate_slope(vibs)

        pressure_mean = float(np.mean(pressures))
        pressure_slope = self.calculate_slope(pressures)

        current_mean = float(np.mean(currents))
        current_slope = self.calculate_slope(currents)

        power_mean = float(np.mean(powers))
        power_slope = self.calculate_slope(powers)

        eff_mean = float(np.mean(effs))
        eff_slope = self.calculate_slope(effs)

        load_mean = float(np.mean(loads))
        load_slope = self.calculate_slope(loads)

        # 4. Stress and physics indicators
        # Nominal references: temp=65C, vib=2.5 mm/s
        thermal_stress = max(0.0, temp_current - 65.0)
        vib_stress = max(0.0, vib_current - 2.5)
        load_stress = load_val
        energy_intensity = power_kw_val / max(0.1, output_rate)

        # 5. Health trajectory features
        health_current = latest_h
        health_slope = self.calculate_slope(healths)
        health_delta = latest_h - healths[0]

        feature_dict = {
            "temp_current": temp_current,
            "vib_current": vib_current,
            "pressure_current": pressure_current,
            "current_a": current_a,
            "voltage_v": voltage_v,
            "rpm_val": rpm_val,
            "power_kw_val": power_kw_val,
            "load_val": load_val,
            "eff_val": eff_val,
            "temp_mean": temp_mean,
            "temp_std": temp_std,
            "temp_slope": temp_slope,
            "vib_mean": vib_mean,
            "vib_std": vib_std,
            "vib_slope": vib_slope,
            "pressure_mean": pressure_mean,
            "pressure_slope": pressure_slope,
            "current_mean": current_mean,
            "current_slope": current_slope,
            "power_mean": power_mean,
            "power_slope": power_slope,
            "eff_mean": eff_mean,
            "eff_slope": eff_slope,
            "load_mean": load_mean,
            "load_slope": load_slope,
            "thermal_stress": thermal_stress,
            "vib_stress": vib_stress,
            "load_stress": load_stress,
            "energy_intensity": energy_intensity,
            "health_current": health_current,
            "health_slope": health_slope,
            "health_delta": health_delta,
        }

        # Vector in fixed deterministic order
        vector = np.array([feature_dict[name] for name in FEATURE_NAMES], dtype=float)
        return feature_dict, vector
