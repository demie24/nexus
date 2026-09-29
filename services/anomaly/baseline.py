"""
NEXUS Machine Baseline Manager
Maintains running normal statistical profiles (mean, std, min, max) for every machine and sensor.
Provides cold-start detection to prevent false positives when historical telemetry is insufficient.
"""

from collections import defaultdict
import math
from typing import Dict, List, Optional, Any
from services.schemas import TelemetryCreate
from services.simulation.config import get_default_factory_spec


class RunningSignalStats:
    """Welford's algorithm for numerically stable online mean and standard deviation."""
    def __init__(self, default_mean: float = 0.0, default_std: float = 1.0):
        self.count: int = 0
        self.mean: float = default_mean
        self.m2: float = (default_std ** 2) if default_std > 0 else 1.0
        self.min_val: float = float("inf")
        self.max_val: float = float("-inf")

    def update(self, val: float) -> None:
        self.count += 1
        delta = val - self.mean
        self.mean += delta / self.count
        delta2 = val - self.mean
        self.m2 += delta * delta2
        if val < self.min_val:
            self.min_val = val
        if val > self.max_val:
            self.max_val = val

    @property
    def variance(self) -> float:
        return self.m2 / self.count if self.count > 1 else (self.m2 if self.count == 1 else 1.0)

    @property
    def std(self) -> float:
        return max(1e-4, math.sqrt(self.variance))


class MachineBaseline:
    def __init__(self, machine_id: str, default_specs: Optional[Dict[str, Any]] = None):
        self.machine_id = machine_id
        self.sample_count: int = 0
        self.signals: Dict[str, RunningSignalStats] = {}

        # Look up machine specifications from factory spec if available
        factory_spec = get_default_factory_spec()
        m_spec = factory_spec.get_machine(machine_id) if factory_spec else None

        if m_spec:
            nom_temp = m_spec.nominal_temp_c
            nom_vib = m_spec.nominal_vib_mms
            nom_press = m_spec.nominal_pressure_bar
            nom_curr = m_spec.nominal_current_a
            nom_volt = m_spec.nominal_voltage_v
            nom_rpm = m_spec.nominal_rpm
            nom_pwr = m_spec.nominal_power_kw
            nom_out = m_spec.nominal_output_rate
        else:
            specs = default_specs or {}
            nom_temp = float(specs.get("nominal_temp_c", 65.0))
            nom_vib = float(specs.get("nominal_vib_mms", 2.2))
            nom_press = float(specs.get("nominal_pressure_bar", 2.5))
            nom_curr = float(specs.get("nominal_current_a", 15.0))
            nom_volt = float(specs.get("nominal_voltage_v", 400.0))
            nom_rpm = float(specs.get("nominal_rpm", 1500.0))
            nom_pwr = float(specs.get("nominal_power_kw", 15.0))
            nom_out = float(specs.get("nominal_output_rate", 80.0))

        defaults = {
            "temperature": (nom_temp, 3.5),
            "vibration": (nom_vib, 0.4),
            "pressure": (nom_press, 0.25),
            "current": (nom_curr, 1.8),
            "voltage": (nom_volt, 5.0),
            "rpm": (nom_rpm, 25.0 if nom_rpm > 0 else 1.0),
            "power_kw": (nom_pwr, 1.8),
            "efficiency": (96.0, 1.8),
            "output_rate": (nom_out, 6.0),
            "load": (1.0, 0.1),
        }

        for sig, (mean_v, std_v) in defaults.items():
            self.signals[sig] = RunningSignalStats(mean_v, std_v)

    def update(self, telemetry: TelemetryCreate) -> None:
        self.sample_count += 1
        data = telemetry.model_dump()
        for sig, stat in self.signals.items():
            if sig in data and data[sig] is not None:
                stat.update(float(data[sig]))

    def get_mean(self, signal: str) -> float:
        stat = self.signals.get(signal)
        return stat.mean if stat else 0.0

    def get_std(self, signal: str) -> float:
        stat = self.signals.get(signal)
        return stat.std if stat else 1.0

    def is_established(self, min_samples: int = 10) -> bool:
        """Determines if the machine has accumulated enough telemetry to clear cold start."""
        return self.sample_count >= min_samples


class MachineBaselineManager:
    def __init__(self):
        self._baselines: Dict[str, MachineBaseline] = {}

    def get_baseline(self, machine_id: str, default_specs: Optional[Dict[str, Any]] = None) -> MachineBaseline:
        if machine_id not in self._baselines:
            self._baselines[machine_id] = MachineBaseline(machine_id, default_specs)
        return self._baselines[machine_id]

    def update_baseline(self, telemetry: TelemetryCreate, default_specs: Optional[Dict[str, Any]] = None) -> None:
        baseline = self.get_baseline(telemetry.machine_id, default_specs)
        baseline.update(telemetry)

    def reset(self, machine_id: Optional[str] = None) -> None:
        if machine_id:
            self._baselines.pop(machine_id, None)
        else:
            self._baselines.clear()


_baseline_manager = MachineBaselineManager()


def get_baseline_manager() -> MachineBaselineManager:
    return _baseline_manager
