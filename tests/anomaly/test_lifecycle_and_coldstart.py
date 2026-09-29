"""
Unit Tests for Cold Start Handling, Temporal Persistence, and Anomaly Lifecycle Transitions
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from database.models.models import MachineModel, AnomalyModel
from services.schemas import (
    TelemetryCreate,
    AnomalyLifecycleStatus,
    SeverityLevel,
    DataProvenance,
)
from services.anomaly.baseline import MachineBaselineManager
from services.anomaly.lifecycle import AnomalyLifecycleManager
from services.anomaly.engine import AnomalyEngine


@pytest.fixture
def seed_machine_lifecycle(db_session: Session):
    m = MachineModel(
        id="M01",
        name="CNC Milling 01",
        line_id="LINE_01",
        machine_type="CNC_Milling",
        nominal_power_kw=15.0,
        nominal_rpm=1500.0,
        max_temperature_c=95.0,
        max_vibration_mms=8.0,
        rated_load=1.0,
        maintenance_status="OK"
    )
    db_session.add(m)
    db_session.commit()
    return m


def test_cold_start_insufficient_baseline(seed_machine_lifecycle, db_session: Session):
    engine = AnomalyEngine()
    engine.baseline_manager.reset("M01")
    engine.feature_extractor.clear("M01")
    now = datetime.now(timezone.utc)

    # First sample: cold-start
    tel_1 = TelemetryCreate(
        machine_id="M01",
        timestamp=now,
        temperature=85.0,  # elevated, but should be suppressed due to cold-start
        vibration=4.0,
        pressure=2.5,
        current=14.0,
        voltage=400.0,
        rpm=1500.0,
        power_kw=16.0,
        load=1.0,
        output_rate=80.0,
        efficiency=90.0,
        provenance=DataProvenance.OBSERVED
    )

    res_1 = engine.analyze(tel_1, db_session, persist_if_detected=True)
    assert res_1.status == AnomalyLifecycleStatus.INSUFFICIENT_BASELINE
    assert res_1.anomaly_detected is False
    assert res_1.persisted_anomaly_id is None

    # Feed 9 more nominal frames to establish baseline (total 10)
    for _ in range(9):
        tel_normal = TelemetryCreate(
            machine_id="M01",
            timestamp=now,
            temperature=65.0,
            vibration=2.2,
            pressure=2.5,
            current=12.0,
            voltage=400.0,
            rpm=1500.0,
            power_kw=15.0,
            load=1.0,
            output_rate=85.0,
            efficiency=96.0
        )
        engine.analyze(tel_normal, db_session, persist_if_detected=False)

    baseline = engine.baseline_manager.get_baseline("M01")
    assert baseline.is_established(10) is True


def test_temporal_persistence_and_recovery_lifecycle(seed_machine_lifecycle, db_session: Session):
    lifecycle = AnomalyLifecycleManager()
    lifecycle.reset("M01")

    # Step 1: First abnormal frame (LOW/MEDIUM severity) -> DETECTED
    status_1, _ = lifecycle.update_lifecycle("M01", is_anomalous=True, severity=SeverityLevel.MEDIUM, db=db_session)
    assert status_1 == AnomalyLifecycleStatus.DETECTED

    # Step 2: Second consecutive abnormal frame -> CONFIRMED
    status_2, _ = lifecycle.update_lifecycle("M01", is_anomalous=True, severity=SeverityLevel.MEDIUM, db=db_session)
    assert status_2 == AnomalyLifecycleStatus.CONFIRMED

    # Create dummy DB anomaly record to link with active_anomaly_id
    now = datetime.now(timezone.utc)
    record = AnomalyModel(
        machine_id="M01",
        timestamp=now,
        anomaly_detected=True,
        anomaly_type="MACHINE_BEHAVIOR",
        anomaly_score=0.72,
        severity="HIGH",
        status="ACTIVE",
        primary_metric="vibration",
        observed_value=5.4,
        expected_value=2.2,
        threshold=3.5,
        resolved=False
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    lifecycle.set_active_anomaly_id("M01", record.id)

    # Step 3: Third consecutive abnormal frame -> ACTIVE
    status_3, act_id = lifecycle.update_lifecycle("M01", is_anomalous=True, severity=SeverityLevel.MEDIUM, db=db_session)
    assert status_3 == AnomalyLifecycleStatus.ACTIVE
    assert act_id == record.id

    # Step 4: First normal frame -> RECOVERING
    status_4, act_id = lifecycle.update_lifecycle("M01", is_anomalous=False, severity=SeverityLevel.NORMAL, db=db_session)
    assert status_4 == AnomalyLifecycleStatus.RECOVERING

    # Step 5: Feed 4 more normal frames (total 5 normal cooldown frames) -> RESOLVED
    for _ in range(4):
        status_rec, _ = lifecycle.update_lifecycle("M01", is_anomalous=False, severity=SeverityLevel.NORMAL, db=db_session)

    assert status_rec == AnomalyLifecycleStatus.RESOLVED

    # Verify database record updated to resolved=True
    db_session.refresh(record)
    assert record.resolved is True
    assert record.status == "RESOLVED"
    assert record.resolved_at is not None
