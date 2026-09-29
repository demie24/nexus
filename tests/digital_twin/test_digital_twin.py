"""
Unit & Integration Tests for Digital Twin Engine
Tests state estimation, deterministic state transitions, dynamic freshness tracking,
and factory snapshot aggregation.
"""

from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.orm import Session

from database.models.models import MachineModel, TelemetryModel, MachineStateModel
from services.schemas import OperatingStatus, FreshnessStatus
from services.digital_twin.engine import DigitalTwinEngine


@pytest.fixture
def dt_engine():
    return DigitalTwinEngine(stale_threshold_seconds=60.0)


@pytest.fixture
def seed_machines(db_session: Session):
    m1 = MachineModel(
        id="M01",
        name="Milling 01",
        line_id="LINE_01",
        machine_type="CNC_Milling",
        nominal_power_kw=15.0,
        nominal_rpm=1500.0,
        max_temperature_c=95.0,
        max_vibration_mms=8.0,
        rated_load=1.0,
        maintenance_status="OK"
    )
    m2 = MachineModel(
        id="M02",
        name="Lathe 01",
        line_id="LINE_01",
        machine_type="CNC_Lathe",
        nominal_power_kw=18.0,
        nominal_rpm=1200.0,
        max_temperature_c=90.0,
        max_vibration_mms=7.0,
        rated_load=1.0,
        maintenance_status="OK"
    )
    db_session.add_all([m1, m2])
    db_session.commit()
    return [m1, m2]


def test_deterministic_state_transitions(dt_engine: DigitalTwinEngine):
    # Operating / Normal
    s1 = dt_engine.determine_state_transition(
        health_score=95.0,
        failure_prob=0.05,
        load_factor=1.0,
        maintenance_status="OK",
        current_status=OperatingStatus.OPERATING
    )
    assert s1 == OperatingStatus.OPERATING

    # Idle (low load)
    s2 = dt_engine.determine_state_transition(
        health_score=95.0,
        failure_prob=0.05,
        load_factor=0.02,
        maintenance_status="OK",
        current_status=OperatingStatus.OPERATING
    )
    assert s2 == OperatingStatus.IDLE

    # Degraded (health below 75 or fail prob >= 0.3)
    s3 = dt_engine.determine_state_transition(
        health_score=68.0,
        failure_prob=0.32,
        load_factor=1.0,
        maintenance_status="OK",
        current_status=OperatingStatus.OPERATING
    )
    assert s3 == OperatingStatus.DEGRADED

    # High Risk (health below 45 or fail prob >= 0.65)
    s4 = dt_engine.determine_state_transition(
        health_score=40.0,
        failure_prob=0.68,
        load_factor=1.0,
        maintenance_status="OK",
        current_status=OperatingStatus.DEGRADED
    )
    assert s4 == OperatingStatus.HIGH_RISK

    # Critical (health below 25)
    s5 = dt_engine.determine_state_transition(
        health_score=20.0,
        failure_prob=0.85,
        load_factor=1.0,
        maintenance_status="OK",
        current_status=OperatingStatus.HIGH_RISK
    )
    assert s5 == OperatingStatus.CRITICAL

    # Failed (health <= 0 or current status is FAILED)
    s6 = dt_engine.determine_state_transition(
        health_score=0.0,
        failure_prob=1.0,
        load_factor=0.0,
        maintenance_status="FAILED",
        current_status=OperatingStatus.CRITICAL
    )
    assert s6 == OperatingStatus.FAILED

    # Maintenance
    s7 = dt_engine.determine_state_transition(
        health_score=80.0,
        failure_prob=0.1,
        load_factor=0.0,
        maintenance_status="MAINTENANCE",
        current_status=OperatingStatus.OPERATING
    )
    assert s7 == OperatingStatus.MAINTENANCE


def test_dynamic_freshness_evaluation(dt_engine: DigitalTwinEngine):
    now = datetime.now(timezone.utc)

    # None -> UNKNOWN
    assert dt_engine.evaluate_freshness(None) == FreshnessStatus.UNKNOWN

    # Within 60 seconds -> FRESH
    recent = now - timedelta(seconds=25)
    assert dt_engine.evaluate_freshness(recent) == FreshnessStatus.FRESH

    # Older than 60 seconds -> STALE
    stale = now - timedelta(seconds=75)
    assert dt_engine.evaluate_freshness(stale) == FreshnessStatus.STALE


def test_update_from_telemetry_persists_and_caches(dt_engine: DigitalTwinEngine, seed_machines, db_session: Session):
    m1 = seed_machines[0]
    now = datetime.now(timezone.utc)

    tel = TelemetryModel(
        machine_id=m1.id,
        timestamp=now,
        temperature=72.0,
        vibration=1.8,
        pressure=2.5,
        current=12.0,
        voltage=400.0,
        rpm=1500.0,
        power_kw=14.0,
        load=1.0,
        output_rate=90.0,
        efficiency=98.0,
        quality_indicator=1.0,
        provenance="OBSERVED"
    )
    db_session.add(tel)
    db_session.commit()
    db_session.refresh(tel)

    dt_state = dt_engine.update_from_telemetry(tel, m1, db_session)

    assert dt_state.machine_id == "M01"
    assert dt_state.status == OperatingStatus.OPERATING
    assert dt_state.freshness == FreshnessStatus.FRESH
    assert dt_state.temperature == 72.0

    # Verify database state record
    db_state = db_session.query(MachineStateModel).filter_by(machine_id="M01").first()
    assert db_state is not None
    assert db_state.temperature == 72.0
    assert db_state.last_telemetry_id == tel.id

    # Verify query returns matching state
    retrieved = dt_engine.get_machine_state("M01", db_session)
    assert retrieved is not None
    assert retrieved.temperature == 72.0


def test_factory_snapshot_aggregation(dt_engine: DigitalTwinEngine, seed_machines, db_session: Session):
    m1, m2 = seed_machines
    now = datetime.now(timezone.utc)

    # Machine 1 has fresh normal telemetry
    tel1 = TelemetryModel(
        machine_id=m1.id,
        timestamp=now - timedelta(seconds=10),
        temperature=70.0,
        vibration=1.5,
        pressure=2.5,
        current=10.0,
        voltage=400.0,
        rpm=1500.0,
        power_kw=12.0,
        load=1.0,
        output_rate=90.0,
        efficiency=98.0,
        provenance="OBSERVED"
    )
    db_session.add(tel1)
    db_session.commit()
    db_session.refresh(tel1)
    dt_engine.update_from_telemetry(tel1, m1, db_session)

    # Machine 2 has degraded state with stale timestamp (> 60s)
    tel2 = TelemetryModel(
        machine_id=m2.id,
        timestamp=now - timedelta(seconds=120),
        temperature=98.0,
        vibration=6.5,
        pressure=3.0,
        current=28.0,
        voltage=400.0,
        rpm=1100.0,
        power_kw=25.0,
        load=1.2,
        output_rate=60.0,
        efficiency=65.0,
        provenance="OBSERVED"
    )
    db_session.add(tel2)
    db_session.commit()
    db_session.refresh(tel2)
    dt_engine.update_from_telemetry(tel2, m2, db_session)

    # Manually backdate the machine_states last_telemetry_timestamp to simulate stale
    state2 = db_session.query(MachineStateModel).filter_by(machine_id=m2.id).first()
    state2.last_telemetry_timestamp = now - timedelta(seconds=120)
    db_session.commit()

    snapshot = dt_engine.get_factory_snapshot(db_session, active_scenarios_count=1)

    assert snapshot.total_machines == 2
    assert snapshot.active_scenarios == 1
    assert snapshot.stale_machines == 1  # m2 is stale
    assert snapshot.operating_machines >= 1
    assert 0.0 <= snapshot.overall_health <= 100.0
    assert len(snapshot.machines) == 2
