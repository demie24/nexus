"""
Virtual Industrial Machine Behaviour & Physics Model
Implements coupled thermo-mechanical dynamics, degradation effects, state transitions,
and deterministic sensor noise injection.
"""

import math
from typing import Dict, Any, Optional
import numpy as np

from services.schemas import OperatingStatus, TelemetryCreate, DataProvenance
from services.simulation.config import MachineSpec


class SimulatedMachine:
    def __init__(self, spec: MachineSpec, rng: np.random.Generator):
        self.spec = spec
        self.rng = rng

        # Dynamic Operational State
        self.operating_status: OperatingStatus = OperatingStatus.OPERATING
        self.maintenance_status: str = "OK"  # "OK", "DUE", "IN_PROGRESS"
        self.current_load: float = self.spec.rated_load

        # Degradation & Fault Internal State (0.0 = pristine, 1.0 = total failure)
        self.bearing_degradation: float = 0.0
        self.cooling_degradation: float = 0.0
        self.electrical_degradation: float = 0.0

        # Sensor Anomaly Biases (for simulating false-positive sensor glitches)
        self.sensor_bias: Dict[str, float] = {
            "temperature": 0.0,
            "vibration": 0.0,
            "current": 0.0,
            "voltage": 0.0,
            "pressure": 0.0,
            "rpm": 0.0,
            "power": 0.0
        }
        self.sensor_noise_enabled: bool = True

        # Thermal state tracking
        self.internal_temperature: float = self.spec.nominal_temp_c

    @property
    def machine_id(self) -> str:
        return self.spec.machine_id

    @property
    def health_score(self) -> float:
        """
        Calculates health score (0-100%) as a function of mechanical, thermal, and electrical degradation.
        """
        if self.operating_status == OperatingStatus.FAILED:
            return 0.0
        penalty = (
            55.0 * self.bearing_degradation +
            30.0 * self.cooling_degradation +
            25.0 * self.electrical_degradation
        )
        return float(max(0.0, min(100.0, 100.0 - penalty)))

    @property
    def failure_probability(self) -> float:
        """
        Non-linear hazard function mapping degradation to failure risk (0.0 to 1.0).
        """
        if self.operating_status == OperatingStatus.FAILED:
            return 1.0
        # Exponential hazard progression
        composite_wear = (
            0.55 * (self.bearing_degradation ** 2) +
            0.30 * (self.cooling_degradation ** 1.8) +
            0.15 * self.electrical_degradation
        )
        prob = 1.0 - math.exp(-3.5 * composite_wear)
        return float(min(1.0, max(0.0, prob)))

    def set_load(self, load: float) -> None:
        """Sets target machine load (0.0 to 1.5)."""
        self.current_load = float(max(0.0, min(1.5, load)))
        if self.current_load == 0.0 and self.operating_status not in [OperatingStatus.MAINTENANCE, OperatingStatus.FAILED]:
            self.operating_status = OperatingStatus.IDLE
        elif self.operating_status == OperatingStatus.IDLE and self.current_load > 0.0:
            self.operating_status = OperatingStatus.OPERATING

    def apply_maintenance(self) -> None:
        """Resets all wear and degradation back to nominal state."""
        self.bearing_degradation = 0.0
        self.cooling_degradation = 0.0
        self.electrical_degradation = 0.0
        self.sensor_bias = {k: 0.0 for k in self.sensor_bias}
        self.internal_temperature = self.spec.nominal_temp_c
        self.operating_status = OperatingStatus.OPERATING
        self.maintenance_status = "OK"

    def step_physics(self, dt_seconds: float) -> None:
        """
        Advances the internal physical model by dt_seconds.
        """
        # Ambient temperature reference
        t_ambient = 24.0

        if self.operating_status in [OperatingStatus.IDLE, OperatingStatus.SHUTDOWN, OperatingStatus.MAINTENANCE]:
            # Cooldown curve towards ambient
            cooling_rate = 0.015 * dt_seconds
            self.internal_temperature += (t_ambient - self.internal_temperature) * min(1.0, cooling_rate)
            return

        if self.operating_status == OperatingStatus.FAILED:
            cooling_rate = 0.02 * dt_seconds
            self.internal_temperature += (t_ambient - self.internal_temperature) * min(1.0, cooling_rate)
            return

        # Active Thermal Equilibrium:
        # Load generates heat; cooling removes heat.
        effective_cooling = max(0.15, 1.0 - 0.75 * self.cooling_degradation)
        load_heat_factor = (self.current_load ** 1.3)
        bearing_heat_factor = 1.0 + 0.35 * self.bearing_degradation

        target_temp = (
            self.spec.nominal_temp_c * load_heat_factor * bearing_heat_factor / effective_cooling
        )
        # First-order thermal lag
        thermal_tau = 120.0  # thermal inertia in seconds
        alpha = min(1.0, dt_seconds / thermal_tau)
        self.internal_temperature += alpha * (target_temp - self.internal_temperature)

        # Update operating status based on health
        if self.health_score < 25.0:
            self.operating_status = OperatingStatus.CRITICAL
        elif self.health_score < 70.0:
            self.operating_status = OperatingStatus.DEGRADED
        else:
            self.operating_status = OperatingStatus.OPERATING

    def generate_telemetry(self, timestamp) -> TelemetryCreate:
        """
        Synthesizes a realistic telemetry frame with coupled physics and sensor noise.
        """
        is_running = self.operating_status in [
            OperatingStatus.OPERATING,
            OperatingStatus.DEGRADED,
            OperatingStatus.CRITICAL,
            OperatingStatus.NORMAL
        ]

        load = self.current_load if is_running else 0.0

        # 1. Vibration:
        # Baseline vibration scales with load. Bearing degradation introduces quadratic harmonic spikes.
        base_vib = self.spec.nominal_vib_mms * (0.85 + 0.30 * load) if is_running else 0.05
        bearing_vib = 8.5 * (self.bearing_degradation ** 2)
        true_vib = base_vib + bearing_vib

        # 2. Temperature:
        true_temp = self.internal_temperature

        # 3. Electrical (Current & Power):
        base_current = self.spec.nominal_current_a * load if is_running else 0.4
        bearing_friction_current = base_current * (0.22 * self.bearing_degradation)
        true_current = base_current + bearing_friction_current

        true_voltage = self.spec.nominal_voltage_v
        # 3-phase active power estimation (kW): P = sqrt(3) * V * I * cos(phi) / 1000
        power_factor = 0.88 if load > 0.5 else 0.70
        true_power = (math.sqrt(3) * true_voltage * true_current * power_factor) / 1000.0

        # 4. RPM:
        # Rotational speed drops slightly under heavy load or bearing friction
        if self.spec.nominal_rpm > 0.0 and is_running:
            rpm_slip = 0.04 * load + 0.12 * self.bearing_degradation
            true_rpm = self.spec.nominal_rpm * (1.0 - min(0.6, rpm_slip))
        else:
            true_rpm = 0.0

        # 5. Pressure:
        # Hydraulic/pneumatic pressure responds to load and mechanical resistance
        base_pressure = self.spec.nominal_pressure_bar * (0.9 + 0.2 * load) if is_running else 0.1
        true_pressure = base_pressure

        # 6. Efficiency & Output Rate:
        # Efficiency decreases with wear and overload
        efficiency_penalties = (
            28.0 * self.bearing_degradation +
            20.0 * self.cooling_degradation +
            max(0.0, (load - 1.0) * 25.0)
        )
        true_efficiency = max(0.0, min(100.0, 100.0 - efficiency_penalties)) if is_running else 0.0
        true_output_rate = self.spec.nominal_output_rate * load * (true_efficiency / 100.0) if is_running else 0.0

        # 7. Apply Sensor Noise & Bias:
        noise_mult = 1.0 if self.sensor_noise_enabled else 0.0

        meas_temp = true_temp + self.sensor_bias["temperature"] + (self.rng.normal(0, self.spec.temp_noise_std) * noise_mult)
        meas_vib = max(0.01, true_vib + self.sensor_bias["vibration"] + (self.rng.normal(0, self.spec.vib_noise_std) * noise_mult))
        meas_current = max(0.0, true_current + self.sensor_bias["current"] + (self.rng.normal(0, self.spec.current_noise_std) * noise_mult))
        meas_voltage = max(0.0, true_voltage + self.sensor_bias["voltage"] + (self.rng.normal(0, self.spec.voltage_noise_std) * noise_mult))
        meas_rpm = max(0.0, true_rpm + self.sensor_bias["rpm"] + (self.rng.normal(0, self.spec.rpm_noise_std) * noise_mult))
        meas_pressure = max(0.0, true_pressure + self.sensor_bias["pressure"] + (self.rng.normal(0, self.spec.pressure_noise_std) * noise_mult))
        meas_power = max(0.0, true_power + self.sensor_bias["power"] + (self.rng.normal(0, self.spec.power_noise_std) * noise_mult))
        meas_efficiency = max(0.0, min(100.0, true_efficiency))

        # Data quality score: drops if extreme sensor anomaly bias is injected
        has_sensor_anomaly = any(abs(v) > 0.001 for v in self.sensor_bias.values())
        quality_score = 0.70 if has_sensor_anomaly else 1.0

        return TelemetryCreate(
            machine_id=self.spec.machine_id,
            timestamp=timestamp,
            temperature=round(float(meas_temp), 2),
            vibration=round(float(meas_vib), 3),
            pressure=round(float(meas_pressure), 2),
            current=round(float(meas_current), 2),
            voltage=round(float(meas_voltage), 1),
            rpm=round(float(meas_rpm), 1),
            power_kw=round(float(meas_power), 2),
            load=round(float(load), 2),
            output_rate=round(float(true_output_rate), 2),
            efficiency=round(float(meas_efficiency), 1),
            quality_indicator=quality_score,
            provenance=DataProvenance.OBSERVED
        )

    def get_state_summary(self) -> Dict[str, Any]:
        """Provides snapshot of machine internal states."""
        return {
            "machine_id": self.spec.machine_id,
            "name": self.spec.name,
            "type": self.spec.machine_type,
            "production_line": self.spec.line_id,
            "rated_load": self.spec.rated_load,
            "current_load": round(self.current_load, 2),
            "health_score": round(self.health_score, 1),
            "failure_probability": round(self.failure_probability, 3),
            "operating_status": self.operating_status.value,
            "maintenance_status": self.maintenance_status,
            "bearing_degradation": round(self.bearing_degradation, 3),
            "cooling_degradation": round(self.cooling_degradation, 3),
            "internal_temperature": round(self.internal_temperature, 2)
        }
