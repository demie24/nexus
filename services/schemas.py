"""
NEXUS Domain Schemas (Pydantic v2)
Core data models for telemetry, state estimation, anomalies, predictions,
simulations, decisions, and audit trails.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class OperatingStatus(str, Enum):
    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    SHUTDOWN = "SHUTDOWN"
    MAINTENANCE = "MAINTENANCE"


class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ActionType(str, Enum):
    CONTINUE = "CONTINUE"
    REDUCE_LOAD = "REDUCE_LOAD"
    SHUTDOWN = "SHUTDOWN"
    SCHEDULE_MAINTENANCE = "SCHEDULE_MAINTENANCE"
    RECALIBRATE = "RECALIBRATE"


class ActionApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"


class DataProvenance(str, Enum):
    OBSERVED = "OBSERVED"
    PREDICTED = "PREDICTED"
    SIMULATED = "SIMULATED"
    RECOMMENDED = "RECOMMENDED"


# ---------------------------------------------------------------------------
# Machine Schema
# ---------------------------------------------------------------------------
class MachineBase(BaseModel):
    id: str = Field(..., description="Unique Machine Identifier (e.g. M01, M-042)")
    name: str = Field(..., description="Machine Name/Model (e.g. CNC Milling Unit 1)")
    line_id: str = Field(..., description="Production Line Identifier (e.g. LINE_01)")
    machine_type: str = Field(..., description="Type of machinery (e.g. Milling, Lathe, Welder)")
    nominal_power_kw: float = Field(default=15.0, ge=0.0)
    nominal_rpm: float = Field(default=1500.0, ge=0.0)
    max_temperature_c: float = Field(default=95.0, ge=0.0)
    max_vibration_mms: float = Field(default=8.0, ge=0.0)


class MachineCreate(MachineBase):
    pass


class Machine(MachineBase):
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Telemetry Schema (Observed stream)
# ---------------------------------------------------------------------------
class TelemetryBase(BaseModel):
    machine_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    temperature: float = Field(..., description="Operating temperature in Celsius")
    vibration: float = Field(..., description="Vibration velocity in mm/s")
    current: float = Field(..., description="Electric current in Amperes")
    voltage: float = Field(default=400.0, description="Operating voltage in Volts")
    rpm: float = Field(..., description="Rotations per minute")
    power_kw: float = Field(..., description="Active power consumption in kW")
    output_rate: float = Field(..., description="Production units per hour")
    efficiency: float = Field(default=100.0, ge=0.0, le=100.0, description="Operating efficiency %")
    quality_indicator: float = Field(default=1.0, ge=0.0, le=1.0, description="Data quality score")
    provenance: DataProvenance = DataProvenance.OBSERVED


class TelemetryCreate(TelemetryBase):
    pass


class Telemetry(TelemetryBase):
    id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Machine State Schema (Digital Twin state estimation)
# ---------------------------------------------------------------------------
class MachineStateBase(BaseModel):
    machine_id: str
    status: OperatingStatus = OperatingStatus.NORMAL
    health_score: float = Field(default=100.0, ge=0.0, le=100.0, description="Aggregated health 0-100%")
    failure_probability: float = Field(default=0.0, ge=0.0, le=1.0, description="Current failure probability 0-1")
    load_factor: float = Field(default=1.0, ge=0.0, le=1.5, description="Load factor multiplier")
    temperature_trend: float = Field(default=0.0, description="Rate of temperature change degC/min")
    vibration_trend: float = Field(default=0.0, description="Rate of vibration change mm/s/min")
    provenance: DataProvenance = DataProvenance.OBSERVED


class MachineStateCreate(MachineStateBase):
    pass


class MachineState(MachineStateBase):
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Anomaly Schema
# ---------------------------------------------------------------------------
class AnomalyBase(BaseModel):
    machine_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    anomaly_detected: bool = True
    anomaly_score: float = Field(..., ge=0.0, le=1.0, description="Normalized anomaly score 0-1")
    severity: SeverityLevel = SeverityLevel.LOW
    primary_metric: str = Field(..., description="Metric triggering anomaly (e.g. vibration, temperature)")
    observed_value: float
    expected_value: float
    threshold: float
    provenance: DataProvenance = DataProvenance.OBSERVED


class AnomalyCreate(AnomalyBase):
    pass


class Anomaly(AnomalyBase):
    id: Optional[int] = None
    resolved: bool = False

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Prediction Schema
# ---------------------------------------------------------------------------
class PredictionBase(BaseModel):
    machine_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    horizon_minutes: int = Field(default=120, description="Forecast horizon in minutes")
    predicted_failure_probability: float = Field(..., ge=0.0, le=1.0)
    predicted_health_score: float = Field(..., ge=0.0, le=100.0)
    remaining_useful_life_hours: float = Field(..., ge=0.0, description="Estimated RUL in operating hours")
    risk_level: SeverityLevel = SeverityLevel.LOW
    confidence: float = Field(default=0.90, ge=0.0, le=1.0)
    provenance: DataProvenance = DataProvenance.PREDICTED


class PredictionCreate(PredictionBase):
    pass


class Prediction(PredictionBase):
    id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Simulation Schema ("What-If" Scenario & Counterfactuals)
# ---------------------------------------------------------------------------
class SimulationScenario(BaseModel):
    scenario_name: str
    target_machine_id: str
    action_type: ActionType
    parameter_overrides: Dict[str, Any] = Field(default_factory=dict, description="e.g. {'load_reduction': 0.20}")
    duration_hours: float = Field(default=4.0, ge=0.1)


class SimulationResultBase(BaseModel):
    scenario_name: str
    target_machine_id: str
    action_type: ActionType
    baseline_production_units: float
    simulated_production_units: float
    production_loss_pct: float
    simulated_failure_probability: float
    risk_reduction_pct: float
    affected_cascade_machines: List[str] = Field(default_factory=list)
    recovery_time_hours: float = Field(default=1.0)
    provenance: DataProvenance = DataProvenance.SIMULATED


class SimulationResult(SimulationResultBase):
    id: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Recommendation Schema (Decision Support)
# ---------------------------------------------------------------------------
class RecommendationBase(BaseModel):
    machine_id: str
    title: str = Field(..., description="Concise action recommendation")
    action_type: ActionType
    reasoning: List[str] = Field(default_factory=list, description="Verifiable causal/statistical evidence")
    confidence: float = Field(..., ge=0.0, le=1.0)
    risk_impact: str = Field(..., description="e.g. 'HIGH -> LOW'")
    cost_impact: SeverityLevel = SeverityLevel.LOW
    production_loss_pct: float = Field(..., ge=0.0, le=100.0)
    recommended_deadline_hours: float = Field(default=4.0)
    approval_status: ActionApprovalStatus = ActionApprovalStatus.PENDING
    provenance: DataProvenance = DataProvenance.RECOMMENDED


class RecommendationCreate(RecommendationBase):
    pass


class Recommendation(RecommendationBase):
    id: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Audit Log Schema (Human-in-the-Loop & System Governance)
# ---------------------------------------------------------------------------
class AuditLogBase(BaseModel):
    actor: str = Field(..., description="User or AI Agent identifier")
    action: str = Field(..., description="Action taken or approved")
    resource_type: str = Field(..., description="Machine, Recommendation, Simulation")
    resource_id: str = Field(..., description="Identifier of resource")
    details: Dict[str, Any] = Field(default_factory=dict)
    provenance: DataProvenance = DataProvenance.OBSERVED


class AuditLogCreate(AuditLogBase):
    pass


class AuditLog(AuditLogBase):
    id: Optional[int] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)
