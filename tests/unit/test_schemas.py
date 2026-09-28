"""
Unit Tests for NEXUS Pydantic Domain Schemas
Validates schema validation, boundary values, defaults, and provenance integrity.
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from services.schemas import (
    MachineCreate,
    Machine,
    TelemetryCreate,
    Telemetry,
    MachineStateCreate,
    MachineState,
    AnomalyCreate,
    Anomaly,
    PredictionCreate,
    Prediction,
    SimulationScenario,
    SimulationResultBase,
    RecommendationCreate,
    Recommendation,
    AuditLogCreate,
    AuditLog,
    OperatingStatus,
    SeverityLevel,
    ActionType,
    ActionApprovalStatus,
    DataProvenance
)


def test_machine_schema_validation():
    # Valid machine
    m = MachineCreate(
        id="M01",
        name="CNC Milling 1",
        line_id="LINE_01",
        machine_type="Milling",
        nominal_power_kw=18.5,
        nominal_rpm=1500.0,
        max_temperature_c=90.0,
        max_vibration_mms=7.5
    )
    assert m.id == "M01"
    assert m.nominal_power_kw == 18.5

    # Negative nominal power should fail validation
    with pytest.raises(ValidationError):
        MachineCreate(
            id="M02",
            name="Lathe 1",
            line_id="LINE_01",
            machine_type="Lathe",
            nominal_power_kw=-5.0  # Invalid
        )


def test_telemetry_schema_validation():
    now = datetime.now(timezone.utc)
    t = TelemetryCreate(
        machine_id="M01",
        timestamp=now,
        temperature=72.4,
        vibration=2.8,
        current=14.2,
        voltage=400.0,
        rpm=1450.0,
        power_kw=15.2,
        output_rate=80.0,
        efficiency=98.5,
        provenance=DataProvenance.OBSERVED
    )
    assert t.machine_id == "M01"
    assert t.provenance == DataProvenance.OBSERVED
    assert t.efficiency == 98.5

    # Efficiency out of bounds (> 100)
    with pytest.raises(ValidationError):
        TelemetryCreate(
            machine_id="M01",
            timestamp=now,
            temperature=72.4,
            vibration=2.8,
            current=14.2,
            rpm=1450.0,
            power_kw=15.2,
            output_rate=80.0,
            efficiency=120.0  # Invalid
        )


def test_machine_state_schema_validation():
    s = MachineStateCreate(
        machine_id="M03",
        status=OperatingStatus.DEGRADED,
        health_score=68.5,
        failure_probability=0.45,
        load_factor=0.85,
        temperature_trend=0.4,
        vibration_trend=0.2,
        provenance=DataProvenance.OBSERVED
    )
    assert s.status == OperatingStatus.DEGRADED
    assert s.health_score == 68.5
    assert s.failure_probability == 0.45

    # Failure probability out of range (> 1.0)
    with pytest.raises(ValidationError):
        MachineStateCreate(
            machine_id="M03",
            health_score=50.0,
            failure_probability=1.5  # Invalid
        )


def test_anomaly_schema_validation():
    a = AnomalyCreate(
        machine_id="M03",
        anomaly_detected=True,
        anomaly_score=0.88,
        severity=SeverityLevel.HIGH,
        primary_metric="vibration",
        observed_value=7.4,
        expected_value=3.2,
        threshold=5.5
    )
    assert a.anomaly_detected is True
    assert a.severity == SeverityLevel.HIGH
    assert a.anomaly_score == 0.88


def test_prediction_schema_validation():
    p = PredictionCreate(
        machine_id="M03",
        horizon_minutes=120,
        predicted_failure_probability=0.74,
        predicted_health_score=45.0,
        remaining_useful_life_hours=18.5,
        risk_level=SeverityLevel.HIGH,
        confidence=0.92,
        provenance=DataProvenance.PREDICTED
    )
    assert p.provenance == DataProvenance.PREDICTED
    assert p.predicted_failure_probability == 0.74


def test_simulation_schema_validation():
    sim = SimulationResultBase(
        scenario_name="Reduce M03 Load 20%",
        target_machine_id="M03",
        action_type=ActionType.REDUCE_LOAD,
        baseline_production_units=1000.0,
        simulated_production_units=940.0,
        production_loss_pct=6.0,
        simulated_failure_probability=0.19,
        risk_reduction_pct=55.0,
        affected_cascade_machines=["M04", "M05"],
        recovery_time_hours=2.5,
        provenance=DataProvenance.SIMULATED
    )
    assert sim.provenance == DataProvenance.SIMULATED
    assert sim.production_loss_pct == 6.0


def test_recommendation_schema_validation():
    r = RecommendationCreate(
        machine_id="M03",
        title="Reduce M03 load to 70% and schedule maintenance",
        action_type=ActionType.REDUCE_LOAD,
        reasoning=["Vibration rising at 0.5 mm/s/min", "Bearing degradation detected (72%)"],
        confidence=0.89,
        risk_impact="HIGH -> LOW",
        cost_impact=SeverityLevel.LOW,
        production_loss_pct=6.5,
        recommended_deadline_hours=4.0,
        approval_status=ActionApprovalStatus.PENDING,
        provenance=DataProvenance.RECOMMENDED
    )
    assert r.provenance == DataProvenance.RECOMMENDED
    assert r.approval_status == ActionApprovalStatus.PENDING
    assert len(r.reasoning) == 2


def test_audit_log_schema_validation():
    audit = AuditLogCreate(
        actor="operator_admin",
        action="APPROVE_RECOMMENDATION",
        resource_type="Recommendation",
        resource_id="REC-042",
        details={"approved_action": "REDUCE_LOAD", "target": "M03"},
        provenance=DataProvenance.OBSERVED
    )
    assert audit.actor == "operator_admin"
    assert audit.action == "APPROVE_RECOMMENDATION"
