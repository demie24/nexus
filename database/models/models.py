"""
SQLAlchemy ORM Models for NEXUS Platform
Defines the database schema for machines, telemetry, digital twin states,
anomalies, predictions, simulations, recommendations, and audit logs.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    String, Float, Integer, Boolean, DateTime, JSON, ForeignKey, Index, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


class MachineModel(Base):
    __tablename__ = "machines"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    line_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    machine_type: Mapped[str] = mapped_column(String(50), nullable=False)
    nominal_power_kw: Mapped[float] = mapped_column(Float, default=15.0)
    nominal_rpm: Mapped[float] = mapped_column(Float, default=1500.0)
    max_temperature_c: Mapped[float] = mapped_column(Float, default=95.0)
    max_vibration_mms: Mapped[float] = mapped_column(Float, default=8.0)
    rated_load: Mapped[float] = mapped_column(Float, default=1.0)
    maintenance_status: Mapped[str] = mapped_column(String(50), default="OK")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    telemetries: Mapped[List["TelemetryModel"]] = relationship(
        "TelemetryModel", back_populates="machine", cascade="all, delete-orphan"
    )
    state: Mapped[Optional["MachineStateModel"]] = relationship(
        "MachineStateModel", back_populates="machine", uselist=False, cascade="all, delete-orphan"
    )
    anomalies: Mapped[List["AnomalyModel"]] = relationship(
        "AnomalyModel", back_populates="machine", cascade="all, delete-orphan"
    )
    predictions: Mapped[List["PredictionModel"]] = relationship(
        "PredictionModel", back_populates="machine", cascade="all, delete-orphan"
    )
    diagnostics: Mapped[List["DiagnosticModel"]] = relationship(
        "DiagnosticModel", back_populates="machine", cascade="all, delete-orphan"
    )
    simulations: Mapped[List["SimulationModel"]] = relationship(
        "SimulationModel", back_populates="machine", cascade="all, delete-orphan"
    )
    recommendations: Mapped[List["RecommendationModel"]] = relationship(
        "RecommendationModel", back_populates="machine", cascade="all, delete-orphan"
    )



class TelemetryModel(Base):
    __tablename__ = "telemetry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    machine_id: Mapped[str] = mapped_column(String(50), ForeignKey("machines.id"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    temperature: Mapped[float] = mapped_column(Float, nullable=False)
    vibration: Mapped[float] = mapped_column(Float, nullable=False)
    pressure: Mapped[float] = mapped_column(Float, default=2.5)
    current: Mapped[float] = mapped_column(Float, nullable=False)
    voltage: Mapped[float] = mapped_column(Float, default=400.0)
    rpm: Mapped[float] = mapped_column(Float, nullable=False)
    power_kw: Mapped[float] = mapped_column(Float, nullable=False)
    load: Mapped[float] = mapped_column(Float, default=1.0)
    output_rate: Mapped[float] = mapped_column(Float, nullable=False)
    efficiency: Mapped[float] = mapped_column(Float, default=100.0)
    quality_indicator: Mapped[float] = mapped_column(Float, default=1.0)
    provenance: Mapped[str] = mapped_column(String(20), default="OBSERVED")
    idempotency_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)

    machine: Mapped["MachineModel"] = relationship("MachineModel", back_populates="telemetries")

    __table_args__ = (
        Index("ix_telemetry_machine_time", "machine_id", "timestamp"),
    )


class MachineStateModel(Base):
    __tablename__ = "machine_states"

    machine_id: Mapped[str] = mapped_column(String(50), ForeignKey("machines.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(30), default="NORMAL")
    freshness: Mapped[str] = mapped_column(String(20), default="FRESH")
    health_score: Mapped[float] = mapped_column(Float, default=100.0)
    failure_probability: Mapped[float] = mapped_column(Float, default=0.0)
    load_factor: Mapped[float] = mapped_column(Float, default=1.0)
    maintenance_status: Mapped[str] = mapped_column(String(50), default="OK")
    temperature: Mapped[float] = mapped_column(Float, default=0.0)
    vibration: Mapped[float] = mapped_column(Float, default=0.0)
    pressure: Mapped[float] = mapped_column(Float, default=0.0)
    current: Mapped[float] = mapped_column(Float, default=0.0)
    voltage: Mapped[float] = mapped_column(Float, default=400.0)
    rpm: Mapped[float] = mapped_column(Float, default=0.0)
    power_kw: Mapped[float] = mapped_column(Float, default=0.0)
    efficiency: Mapped[float] = mapped_column(Float, default=100.0)
    output_rate: Mapped[float] = mapped_column(Float, default=0.0)
    temperature_trend: Mapped[float] = mapped_column(Float, default=0.0)
    vibration_trend: Mapped[float] = mapped_column(Float, default=0.0)
    last_telemetry_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_telemetry_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    provenance: Mapped[str] = mapped_column(String(20), default="OBSERVED")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    machine: Mapped["MachineModel"] = relationship("MachineModel", back_populates="state")


class AnomalyModel(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    machine_id: Mapped[str] = mapped_column(String(50), ForeignKey("machines.id"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    anomaly_detected: Mapped[bool] = mapped_column(Boolean, default=True)
    anomaly_type: Mapped[str] = mapped_column(String(50), default="MULTIVARIATE_ANOMALY")
    anomaly_score: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="LOW")
    status: Mapped[str] = mapped_column(String(30), default="DETECTED")
    primary_metric: Mapped[str] = mapped_column(String(50), nullable=False)
    observed_value: Mapped[float] = mapped_column(Float, nullable=False)
    expected_value: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    triggered_signals: Mapped[List[str]] = mapped_column(JSON, default=list)
    detector_evidence: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    provenance: Mapped[str] = mapped_column(String(20), default="OBSERVED")

    machine: Mapped["MachineModel"] = relationship("MachineModel", back_populates="anomalies")


class PredictionModel(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    machine_id: Mapped[str] = mapped_column(String(50), ForeignKey("machines.id"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    horizon_minutes: Mapped[int] = mapped_column(Integer, default=120)
    predicted_failure_probability: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_health_score: Mapped[float] = mapped_column(Float, nullable=False)
    remaining_useful_life_hours: Mapped[float] = mapped_column(Float, nullable=False)
    rul_lower_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rul_upper_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(20), default="LOW")
    confidence: Mapped[float] = mapped_column(Float, default=0.90)
    prediction_status: Mapped[str] = mapped_column(String(30), default="ESTIMATED", nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), default="v1.0.0", nullable=False)
    feature_version: Mapped[str] = mapped_column(String(50), default="v1.0.0", nullable=False)
    health_trajectory: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    risk_forecast: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    contributing_factors: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    provenance: Mapped[str] = mapped_column(String(20), default="PREDICTED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    machine: Mapped["MachineModel"] = relationship("MachineModel", back_populates="predictions")


class SimulationModel(Base):
    __tablename__ = "simulations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    scenario_name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_machine_id: Mapped[str] = mapped_column(String(50), ForeignKey("machines.id"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="COMPLETED", nullable=False)
    horizon_hours: Mapped[float] = mapped_column(Float, default=4.0, nullable=False)
    parameters: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    baseline_production_units: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    simulated_production_units: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    production_loss_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    simulated_failure_probability: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    risk_reduction_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    affected_cascade_machines: Mapped[Dict[str, Any]] = mapped_column(JSON, default=list)
    recovery_time_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=1.0)
    outcome_metrics: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    baseline_comparison: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    random_seed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    state_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provenance: Mapped[str] = mapped_column(String(20), default="SIMULATED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    machine: Mapped["MachineModel"] = relationship("MachineModel", back_populates="simulations")

    @property
    def machine_id(self) -> str:
        return self.target_machine_id


class SimulationSnapshotModel(Base):
    __tablename__ = "simulation_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    factory_id: Mapped[str] = mapped_column(String(50), default="NEXUS-FACTORY-01", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    machines: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    machine_states: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    telemetry_context: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    prediction_context: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False)



class RecommendationModel(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    machine_id: Mapped[str] = mapped_column(String(50), ForeignKey("machines.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reasoning: Mapped[Dict[str, Any]] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    risk_impact: Mapped[str] = mapped_column(String(50), nullable=False)
    cost_impact: Mapped[str] = mapped_column(String(20), default="LOW")
    production_loss_pct: Mapped[float] = mapped_column(Float, nullable=False)
    recommended_deadline_hours: Mapped[float] = mapped_column(Float, default=4.0)
    approval_status: Mapped[str] = mapped_column(String(30), default="PENDING")
    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    provenance: Mapped[str] = mapped_column(String(20), default="RECOMMENDED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    machine: Mapped["MachineModel"] = relationship("MachineModel", back_populates="recommendations")


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    provenance: Mapped[str] = mapped_column(String(20), default="OBSERVED")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )


class DiagnosticModel(Base):
    __tablename__ = "diagnostics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    diagnostic_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    machine_id: Mapped[str] = mapped_column(String(50), ForeignKey("machines.id"), nullable=False, index=True)
    incident_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    likely_cause: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    evidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), default="LOW", nullable=False)
    ranking: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    evidence_summary: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    text_report: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_info: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    provenance: Mapped[str] = mapped_column(String(20), default="DIAGNOSED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    machine: Mapped["MachineModel"] = relationship("MachineModel", back_populates="diagnostics")

    __table_args__ = (
        Index("ix_diagnostics_machine_time", "machine_id", "timestamp"),
    )

