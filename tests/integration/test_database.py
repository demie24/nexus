"""
Integration Tests for NEXUS Database Models & SQLAlchemy ORM
Tests relational cascades, queries, constraints, and audit log persistence.
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from database.models.models import (
    MachineModel,
    TelemetryModel,
    MachineStateModel,
    AnomalyModel,
    RecommendationModel,
    AuditLogModel,
)


def test_machine_and_telemetry_relation(db_session: Session):
    # Insert machine
    machine = MachineModel(
        id="M01",
        name="CNC Milling 1",
        line_id="LINE_01",
        machine_type="Milling",
        nominal_power_kw=15.0,
        nominal_rpm=1500.0,
        max_temperature_c=90.0,
        max_vibration_mms=8.0
    )
    db_session.add(machine)
    db_session.commit()

    # Insert telemetries
    t1 = TelemetryModel(
        machine_id="M01",
        timestamp=datetime.now(timezone.utc),
        temperature=74.2,
        vibration=3.1,
        current=12.5,
        voltage=400.0,
        rpm=1480.0,
        power_kw=14.8,
        output_rate=82.0,
        efficiency=97.0
    )
    t2 = TelemetryModel(
        machine_id="M01",
        timestamp=datetime.now(timezone.utc),
        temperature=76.8,
        vibration=3.4,
        current=13.0,
        voltage=400.0,
        rpm=1475.0,
        power_kw=15.1,
        output_rate=81.5,
        efficiency=96.5
    )
    db_session.add_all([t1, t2])
    db_session.commit()

    # Query machine with telemetries
    loaded_machine = db_session.query(MachineModel).filter_by(id="M01").first()
    assert loaded_machine is not None
    assert len(loaded_machine.telemetries) == 2


def test_machine_state_lifecycle(db_session: Session):
    machine = MachineModel(
        id="M02",
        name="Lathe 1",
        line_id="LINE_01",
        machine_type="Lathe",
    )
    db_session.add(machine)
    db_session.commit()

    state = MachineStateModel(
        machine_id="M02",
        status="NORMAL",
        health_score=98.5,
        failure_probability=0.02,
        load_factor=1.0,
    )
    db_session.add(state)
    db_session.commit()

    # Update state
    state.health_score = 85.0
    state.status = "DEGRADED"
    db_session.commit()

    reloaded_state = db_session.query(MachineStateModel).filter_by(machine_id="M02").first()
    assert reloaded_state.status == "DEGRADED"
    assert reloaded_state.health_score == 85.0


def test_audit_log_persistence(db_session: Session):
    log = AuditLogModel(
        actor="operator_1",
        action="APPROVED_ACTION",
        resource_type="Recommendation",
        resource_id="REC-001",
        details={"machine": "M01", "decision": "REDUCE_LOAD"}
    )
    db_session.add(log)
    db_session.commit()

    loaded = db_session.query(AuditLogModel).filter_by(resource_id="REC-001").first()
    assert loaded is not None
    assert loaded.actor == "operator_1"
    assert loaded.details["machine"] == "M01"
