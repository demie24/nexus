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
    OPERATING = "OPERATING"
    NORMAL = "NORMAL"
    IDLE = "IDLE"
    DEGRADED = "DEGRADED"
    WARNING = "WARNING"
    HIGH_RISK = "HIGH_RISK"
    CRITICAL = "CRITICAL"
    SHUTDOWN = "SHUTDOWN"
    MAINTENANCE = "MAINTENANCE"
    FAILED = "FAILED"


class FreshnessStatus(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class SeverityLevel(str, Enum):
    NORMAL = "NORMAL"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AnomalyType(str, Enum):
    MACHINE_BEHAVIOR = "MACHINE_BEHAVIOR"
    SENSOR_ANOMALY = "SENSOR_ANOMALY"
    MULTIVARIATE_ANOMALY = "MULTIVARIATE_ANOMALY"


class AnomalyLifecycleStatus(str, Enum):
    DETECTED = "DETECTED"
    CONFIRMED = "CONFIRMED"
    ACTIVE = "ACTIVE"
    RECOVERING = "RECOVERING"
    RESOLVED = "RESOLVED"
    INSUFFICIENT_BASELINE = "INSUFFICIENT_BASELINE"


class PredictionStatus(str, Enum):
    ESTIMATED = "ESTIMATED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    MAINTENANCE_REQUIRED = "MAINTENANCE_REQUIRED"
    HEALTHY = "HEALTHY"


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
    DIAGNOSED = "DIAGNOSED"


class RootCauseType(str, Enum):
    BEARING_DEGRADATION = "BEARING_DEGRADATION"
    COOLING_DEGRADATION = "COOLING_DEGRADATION"
    OVERLOAD = "OVERLOAD"
    MOTOR_INEFFICIENCY = "MOTOR_INEFFICIENCY"
    SENSOR_ANOMALY = "SENSOR_ANOMALY"
    UNKNOWN = "UNKNOWN"


class EvidenceSource(str, Enum):
    OBSERVED = "OBSERVED"
    GRAPH = "GRAPH"
    PHYSICAL_CONSISTENCY = "PHYSICAL_CONSISTENCY"
    TEMPORAL = "TEMPORAL"
    CORRELATION = "CORRELATION"
    MODEL_DERIVED = "MODEL_DERIVED"


class PhysicalConsistencyStatus(str, Enum):
    CONSISTENT = "CONSISTENT"
    INCONSISTENT = "INCONSISTENT"
    AMBIGUOUS = "AMBIGUOUS"


class SignalDirection(str, Enum):
    INCREASING = "INCREASING"
    DECREASING = "DECREASING"
    STABLE = "STABLE"
    SPIKE = "SPIKE"
    STEP_CHANGE = "STEP_CHANGE"


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
    rated_load: float = Field(default=1.0, ge=0.0)
    maintenance_status: str = Field(default="OK")


class MachineCreate(MachineBase):
    pass


class Machine(MachineBase):
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Telemetry Schema (Observed stream with Physical Validation)
# ---------------------------------------------------------------------------
class TelemetryBase(BaseModel):
    machine_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    temperature: float = Field(..., ge=-50.0, le=400.0, description="Operating temperature in Celsius")
    vibration: float = Field(..., ge=0.0, le=150.0, description="Vibration velocity in mm/s")
    pressure: float = Field(default=2.5, ge=0.0, le=1000.0, description="Operating pressure in bar")
    current: float = Field(..., ge=0.0, le=500.0, description="Electric current in Amperes")
    voltage: float = Field(default=400.0, ge=0.0, le=1000.0, description="Operating voltage in Volts")
    rpm: float = Field(..., ge=0.0, le=25000.0, description="Rotations per minute")
    power_kw: float = Field(..., ge=0.0, le=1000.0, description="Active power consumption in kW")
    load: float = Field(default=1.0, ge=0.0, le=5.0, description="Operating load percentage / factor")
    output_rate: float = Field(..., ge=0.0, le=50000.0, description="Production units per hour")
    efficiency: float = Field(default=100.0, ge=0.0, le=100.0, description="Operating efficiency %")
    quality_indicator: float = Field(default=1.0, ge=0.0, le=1.0, description="Data quality score")
    provenance: DataProvenance = DataProvenance.OBSERVED
    idempotency_hash: Optional[str] = None


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
    anomaly_type: AnomalyType = AnomalyType.MULTIVARIATE_ANOMALY
    anomaly_score: float = Field(..., ge=0.0, le=1.0, description="Normalized anomaly score 0-1")
    severity: SeverityLevel = SeverityLevel.LOW
    status: AnomalyLifecycleStatus = AnomalyLifecycleStatus.DETECTED
    primary_metric: str = Field(..., description="Metric triggering anomaly (e.g. vibration, temperature)")
    observed_value: float
    expected_value: float
    threshold: float
    triggered_signals: List[str] = Field(default_factory=list)
    detector_evidence: Dict[str, Any] = Field(default_factory=dict)
    explanation: Optional[str] = None
    provenance: DataProvenance = DataProvenance.OBSERVED
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class AnomalyCreate(AnomalyBase):
    pass


class Anomaly(AnomalyBase):
    id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class AnomalyAnalysisRequest(BaseModel):
    machine_id: str
    telemetry: Optional[TelemetryCreate] = None


class AnomalyAnalysisResponse(BaseModel):
    machine_id: str
    timestamp: datetime
    anomaly_detected: bool
    anomaly_score: float
    severity: SeverityLevel
    anomaly_type: Optional[AnomalyType] = None
    status: AnomalyLifecycleStatus
    primary_metric: str
    observed_value: float
    expected_value: float
    threshold: float
    triggered_signals: List[str] = Field(default_factory=list)
    detector_evidence: Dict[str, Any] = Field(default_factory=dict)
    explanation: str
    persisted_anomaly_id: Optional[int] = None


class MachineAnomalyStatus(BaseModel):
    machine_id: str
    has_active_anomaly: bool
    active_anomaly_count: int
    latest_severity: SeverityLevel
    baseline_status: str
    latest_anomaly: Optional[Anomaly] = None


# ---------------------------------------------------------------------------
# Prediction Schema
# ---------------------------------------------------------------------------
class RiskHorizonForecast(BaseModel):
    horizon_minutes: int
    horizon_hours: float
    failure_probability: float = Field(..., ge=0.0, le=1.0)
    risk_level: SeverityLevel
    confidence: float = Field(default=0.90, ge=0.0, le=1.0)


class RiskForecastResponse(BaseModel):
    machine_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    current_status: OperatingStatus = OperatingStatus.NORMAL
    current_health_score: float = Field(..., ge=0.0, le=100.0)
    horizons: List[RiskHorizonForecast] = Field(default_factory=list)
    provenance: DataProvenance = DataProvenance.PREDICTED


class HealthTrajectoryPoint(BaseModel):
    horizon_minutes: int
    horizon_hours: float
    predicted_health_score: float = Field(..., ge=0.0, le=100.0)
    health_status: str
    provenance: DataProvenance = DataProvenance.PREDICTED


class RULResponse(BaseModel):
    machine_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    remaining_useful_life_hours: float = Field(..., ge=0.0)
    rul_lower_hours: Optional[float] = None
    rul_upper_hours: Optional[float] = None
    confidence_level: float = Field(default=0.90, ge=0.0, le=1.0)
    prediction_status: PredictionStatus = PredictionStatus.ESTIMATED
    model_version: str = "v1.0.0"
    provenance: DataProvenance = DataProvenance.PREDICTED


class ContributingFactor(BaseModel):
    factor_name: str
    metric_name: str
    importance: float
    impact_direction: str = "increases_risk"  # "increases_risk", "stable", "decreases_risk"
    description: str


class PredictionBase(BaseModel):
    machine_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    horizon_minutes: int = Field(default=120, description="Forecast horizon in minutes")
    predicted_failure_probability: float = Field(..., ge=0.0, le=1.0)
    predicted_health_score: float = Field(..., ge=0.0, le=100.0)
    remaining_useful_life_hours: float = Field(..., ge=0.0, description="Estimated RUL in operating hours")
    rul_lower_hours: Optional[float] = None
    rul_upper_hours: Optional[float] = None
    risk_level: SeverityLevel = SeverityLevel.LOW
    confidence: float = Field(default=0.90, ge=0.0, le=1.0)
    prediction_status: PredictionStatus = PredictionStatus.ESTIMATED
    model_version: str = "v1.0.0"
    feature_version: str = "v1.0.0"
    health_trajectory: Dict[str, float] = Field(default_factory=dict)
    risk_forecast: Dict[str, float] = Field(default_factory=dict)
    contributing_factors: List[Dict[str, Any]] = Field(default_factory=list)
    provenance: DataProvenance = DataProvenance.PREDICTED
    created_at: Optional[datetime] = None


class PredictionCreate(PredictionBase):
    pass


class Prediction(PredictionBase):
    id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class PredictionAnalysisRequest(BaseModel):
    machine_id: str
    horizon_minutes: Optional[int] = 120
    persist: bool = True


class PredictionAnalysisResponse(BaseModel):
    machine_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    prediction: Prediction
    risk_forecast: RiskForecastResponse
    health_trajectory: List[HealthTrajectoryPoint] = Field(default_factory=list)
    rul: RULResponse
    contributing_factors: List[ContributingFactor] = Field(default_factory=list)
    baseline_comparison: Dict[str, Any] = Field(default_factory=dict)


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


# ---------------------------------------------------------------------------
# Digital Twin State & Factory Snapshot Schemas (Phase 3)
# ---------------------------------------------------------------------------
class DigitalTwinState(BaseModel):
    machine_id: str
    machine_name: str
    line_id: str
    machine_type: str
    status: OperatingStatus
    freshness: FreshnessStatus = FreshnessStatus.FRESH
    health_score: float = Field(..., ge=0.0, le=100.0)
    failure_probability: float = Field(..., ge=0.0, le=1.0)
    load_factor: float
    maintenance_status: str = "OK"
    temperature: float
    vibration: float
    pressure: float
    current: float
    voltage: float
    rpm: float
    power_kw: float
    efficiency: float
    output_rate: float
    last_telemetry_timestamp: Optional[datetime] = None
    last_telemetry_id: Optional[int] = None
    provenance: DataProvenance = DataProvenance.OBSERVED
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


class FactorySnapshot(BaseModel):
    factory_id: str = "FACTORY_01"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_machines: int
    operating_machines: int
    degraded_machines: int
    high_risk_machines: int
    failed_machines: int
    stale_machines: int
    overall_health: float = Field(..., ge=0.0, le=100.0)
    active_scenarios: int = 0
    latest_telemetry_timestamp: Optional[datetime] = None
    machines: List[DigitalTwinState] = Field(default_factory=list)


class IngestionItemStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    REJECTED = "REJECTED"


class IngestionResult(BaseModel):
    status: IngestionItemStatus
    message: str
    telemetry_id: Optional[int] = None
    machine_id: str
    is_duplicate: bool = False
    idempotency_hash: Optional[str] = None
    digital_twin_updated: bool = False


class BatchIngestionResult(BaseModel):
    total_received: int
    accepted_count: int
    duplicate_count: int
    rejected_count: int
    results: List[IngestionResult] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Phase 6: Root Cause Analysis (RCA) & Diagnostics Schemas
# ---------------------------------------------------------------------------
class EvidenceItem(BaseModel):
    signal: str = Field(..., description="Observed sensor signal or derived metric")
    direction: SignalDirection = Field(..., description="Direction of signal movement")
    strength: float = Field(..., ge=0.0, le=1.0, description="Normalized strength of evidence [0, 1]")
    source: EvidenceSource = Field(..., description="Source of evidence")
    description: str = Field(..., description="Explainable description of the evidence")
    observed_value: Optional[float] = Field(None, description="Current or window-average observed value")
    baseline_value: Optional[float] = Field(None, description="Expected nominal baseline value")
    pct_deviation: Optional[float] = Field(None, description="Percentage deviation from baseline")


class CauseCandidate(BaseModel):
    cause: RootCauseType = Field(..., description="Identified candidate root cause")
    rank: int = Field(..., ge=0, description="Rank position (1 is most likely)")
    evidence_score: float = Field(..., ge=0.0, le=1.0, description="Evidence score [0, 1]")
    confidence: str = Field(..., description="Confidence rating: HIGH, MEDIUM, LOW")
    physical_consistency_status: PhysicalConsistencyStatus = Field(..., description="Physical consistency check result")
    evidence: List[EvidenceItem] = Field(default_factory=list, description="Itemized supporting evidence")
    summary: str = Field(default="", description="Explanatory rationale for this candidate")


class CorrelationEvidence(BaseModel):
    signal_a: str
    signal_b: str
    method: str = "spearman"
    coefficient: float
    lag_ticks: int = 0
    relationship: str
    interpretation: str


class DiagnosticMetadata(BaseModel):
    diagnostic_version: str = "v1.0.0"
    feature_version: str = "v1.0.0"
    rule_version: str = "v1.0.0"
    analysis_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    input_window: int = 30
    machine_id: str
    model_version: str = "v1.0.0"
    incident_id: Optional[str] = None


class DiagnosticBase(BaseModel):
    diagnostic_id: str
    machine_id: str
    incident_id: Optional[str] = None
    timestamp: datetime
    likely_cause: RootCauseType
    evidence_score: float = Field(..., ge=0.0, le=1.0)
    confidence: str
    ranking: List[CauseCandidate] = Field(default_factory=list)
    evidence_summary: List[EvidenceItem] = Field(default_factory=list)
    text_report: str
    metadata_info: Dict[str, Any] = Field(default_factory=dict)
    provenance: DataProvenance = DataProvenance.DIAGNOSED


class DiagnosticCreate(DiagnosticBase):
    pass


class Diagnostic(DiagnosticBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DiagnosticReport(BaseModel):
    diagnostic_id: str
    machine_id: str
    incident_id: Optional[str] = None
    timestamp: datetime
    likely_cause: RootCauseType
    evidence_score: float
    confidence: str
    ranking: List[CauseCandidate]
    evidence_summary: List[EvidenceItem]
    alternative_causes: List[CauseCandidate] = Field(default_factory=list)
    correlations: List[CorrelationEvidence] = Field(default_factory=list)
    graph_paths: Dict[str, List[str]] = Field(default_factory=dict)
    text_report: str
    metadata_info: Dict[str, Any]
    provenance: DataProvenance = DataProvenance.DIAGNOSED


class DiagnosticAnalysisRequest(BaseModel):
    machine_id: str = Field(..., description="Target machine ID")
    incident_id: Optional[str] = Field(None, description="Optional incident ID for incident-level RCA")
    start_time: Optional[datetime] = Field(None, description="Start timestamp of analysis window")
    end_time: Optional[datetime] = Field(None, description="End timestamp of analysis window (no future leakage)")
    window_size: Optional[int] = Field(30, ge=5, le=300, description="Telemetry window size in ticks")
    persist: bool = Field(True, description="Whether to persist diagnostic record in database")


class DiagnosticAnalysisResponse(BaseModel):
    diagnostic_id: str
    machine_id: str
    incident_id: Optional[str] = None
    timestamp: datetime
    likely_cause: RootCauseType
    evidence_score: float
    confidence: str
    ranking: List[CauseCandidate]
    evidence_summary: List[EvidenceItem]
    text_report: str
    metadata_info: Dict[str, Any]


