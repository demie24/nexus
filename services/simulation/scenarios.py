"""
Failure Scenario Engine & Lifecycle Management
Controls deterministic injection, progression, escalation, and recovery of abnormal states.
"""

from enum import Enum
from typing import Dict, Any, Optional
import uuid

from services.schemas import OperatingStatus
from services.simulation.machine import SimulatedMachine


class ScenarioType(str, Enum):
    NORMAL = "normal"
    BEARING_DEGRADATION = "bearing_degradation"
    COOLING_DEGRADATION = "cooling_degradation"
    OVERLOAD = "overload"
    SENSOR_ANOMALY = "sensor_anomaly"


class ScenarioStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    ESCALATING = "ESCALATING"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"


class SimulationScenarioInstance:
    def __init__(
        self,
        scenario_type: ScenarioType,
        machine_id: str,
        severity: float = 0.75,
        duration_sim_seconds: float = 300.0,
        parameters: Optional[Dict[str, Any]] = None,
        scenario_id: Optional[str] = None
    ):
        self.scenario_id = scenario_id or f"SCEN-{machine_id}-{scenario_type.value.upper()[:4]}-{uuid.uuid4().hex[:6]}"
        self.scenario_type = scenario_type
        self.machine_id = machine_id
        self.severity = max(0.1, min(1.0, float(severity)))
        self.duration_sim_seconds = max(10.0, float(duration_sim_seconds))
        self.parameters = parameters or {}

        # Lifecycle tracking
        self.status = ScenarioStatus.PENDING
        self.sim_start_time: Optional[float] = None
        self.elapsed_in_scenario: float = 0.0

    def start(self, machine: SimulatedMachine, current_sim_time: float) -> None:
        """Activates scenario on the target machine."""
        self.status = ScenarioStatus.ACTIVE
        self.sim_start_time = current_sim_time
        self.elapsed_in_scenario = 0.0

        if self.scenario_type == ScenarioType.NORMAL:
            machine.apply_maintenance()
            self.status = ScenarioStatus.COMPLETED

        elif self.scenario_type == ScenarioType.OVERLOAD:
            # Increase machine load factor (e.g. 1.35x nominal)
            target_load = self.parameters.get("target_load", 1.0 + 0.40 * self.severity)
            machine.set_load(target_load)

        elif self.scenario_type == ScenarioType.SENSOR_ANOMALY:
            # Inject sensor spike / bias without damaging physical component
            target_sensor = self.parameters.get("sensor", "vibration")
            bias_val = self.parameters.get("bias", 6.8 * self.severity)
            machine.sensor_bias[target_sensor] = bias_val

    def update(self, machine: SimulatedMachine, dt_seconds: float) -> None:
        """Advances scenario effects and escalation dynamics."""
        if self.status not in [ScenarioStatus.ACTIVE, ScenarioStatus.ESCALATING]:
            return

        self.elapsed_in_scenario += dt_seconds
        progress = min(1.0, self.elapsed_in_scenario / self.duration_sim_seconds)

        if self.scenario_type == ScenarioType.BEARING_DEGRADATION:
            # Bearing degradation progresses non-linearly over time
            target_wear = 0.90 * self.severity
            machine.bearing_degradation = min(1.0, target_wear * (progress ** 1.2))
            if progress > 0.6:
                self.status = ScenarioStatus.ESCALATING

        elif self.scenario_type == ScenarioType.COOLING_DEGRADATION:
            # Radiator/coolant efficiency drops progressively
            target_degrad = 0.85 * self.severity
            machine.cooling_degradation = min(1.0, target_degrad * progress)
            if progress > 0.6:
                self.status = ScenarioStatus.ESCALATING

        elif self.scenario_type == ScenarioType.OVERLOAD:
            # Overload maintained; check for auto-completion after duration
            if self.elapsed_in_scenario >= self.duration_sim_seconds:
                self.recover(machine)

        elif self.scenario_type == ScenarioType.SENSOR_ANOMALY:
            if self.elapsed_in_scenario >= self.duration_sim_seconds:
                self.recover(machine)

    def recover(self, machine: SimulatedMachine) -> None:
        """Initiates recovery or maintenance intervention."""
        self.status = ScenarioStatus.RECOVERING

        if self.scenario_type == ScenarioType.OVERLOAD:
            machine.set_load(machine.spec.rated_load)
            self.status = ScenarioStatus.COMPLETED

        elif self.scenario_type == ScenarioType.SENSOR_ANOMALY:
            for k in machine.sensor_bias:
                machine.sensor_bias[k] = 0.0
            self.status = ScenarioStatus.COMPLETED

        elif self.scenario_type in [ScenarioType.BEARING_DEGRADATION, ScenarioType.COOLING_DEGRADATION]:
            # Apply maintenance to restore machine health
            machine.apply_maintenance()
            self.status = ScenarioStatus.COMPLETED

    def stop(self, machine: SimulatedMachine) -> None:
        """Forces immediate cessation of scenario."""
        self.recover(machine)
        self.status = ScenarioStatus.COMPLETED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "machine_id": self.machine_id,
            "scenario_type": self.scenario_type.value,
            "severity": self.severity,
            "duration_sim_seconds": self.duration_sim_seconds,
            "elapsed_in_scenario": round(self.elapsed_in_scenario, 1),
            "status": self.status.value,
            "parameters": self.parameters
        }
