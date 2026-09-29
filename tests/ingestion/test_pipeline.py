"""
Unit & Integration Tests for Telemetry Ingestion Pipeline
Covers physical bounds validation, timestamp window validation, machine registry checks,
SHA-256 idempotency deduplication, partial batch acceptance, and event dispatching.
"""

from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.orm import Session

from database.models.models import MachineModel, TelemetryModel
from services.schemas import (
    TelemetryCreate,
    DataProvenance,
    IngestionItemStatus,
)
from services.ingestion.validator import (
    validate_telemetry_bounds,
    validate_timestamp,
    validate_machine_exists,
    TelemetryValidationError,
)
from services.ingestion.idempotency import (
    generate_telemetry_idempotency_hash,
    IdempotencyManager,
)
from services.ingestion.pipeline import TelemetryIngestionService
from services.ingestion.events import IngestionEventType, IngestionEvent, EventBus


@pytest.fixture
def seed_machine(db_session: Session):
    machine = MachineModel(
        id="M01",
        name="Milling Machine 01",
        line_id="LINE_01",
        machine_type="CNC_Milling",
        nominal_power_kw=15.0,
        nominal_rpm=1500.0,
        max_temperature_c=95.0,
        max_vibration_mms=8.0,
        rated_load=1.0,
        maintenance_status="OK"
    )
    db_session.add(machine)
    db_session.commit()
    return machine


def test_validator_physical_bounds_impossible_rejection():
    # Negative vibration is physically impossible
    invalid_vib = TelemetryCreate.model_construct(
        machine_id="M01",
        timestamp=datetime.now(timezone.utc),
        temperature=70.0,
        vibration=-1.0,
        pressure=2.5,
        current=10.0,
        voltage=400.0,
        rpm=1500.0,
        power_kw=12.0,
        load=1.0,
        output_rate=100.0,
        efficiency=100.0,
        quality_indicator=1.0,
        provenance=DataProvenance.OBSERVED
    )
    with pytest.raises(TelemetryValidationError) as exc:
        validate_telemetry_bounds(invalid_vib)
    assert "vibration" in str(exc.value)

    # Temperature below -50°C
    invalid_temp = TelemetryCreate.model_construct(
        machine_id="M01",
        timestamp=datetime.now(timezone.utc),
        temperature=-60.0,
        vibration=1.0,
        pressure=2.5,
        current=10.0,
        voltage=400.0,
        rpm=1500.0,
        power_kw=12.0,
        load=1.0,
        output_rate=100.0,
        efficiency=100.0,
        quality_indicator=1.0,
        provenance=DataProvenance.OBSERVED
    )
    with pytest.raises(TelemetryValidationError) as exc:
        validate_telemetry_bounds(invalid_temp)
    assert "temperature" in str(exc.value)

    # Efficiency > 100%
    invalid_eff = TelemetryCreate.model_construct(
        machine_id="M01",
        timestamp=datetime.now(timezone.utc),
        temperature=70.0,
        vibration=1.0,
        pressure=2.5,
        current=10.0,
        voltage=400.0,
        rpm=1500.0,
        power_kw=12.0,
        load=1.0,
        output_rate=100.0,
        efficiency=105.0,
        quality_indicator=1.0,
        provenance=DataProvenance.OBSERVED
    )
    with pytest.raises(TelemetryValidationError) as exc:
        validate_telemetry_bounds(invalid_eff)
    assert "efficiency" in str(exc.value)


def test_validator_allows_operational_anomalies():
    # Severe operational anomaly (vibration = 12.5 mm/s, temp = 115°C) is physically plausible and MUST be accepted
    anomaly_payload = TelemetryCreate(
        machine_id="M01",
        temperature=115.0,
        vibration=12.5,
        current=45.0,
        rpm=1600.0,
        power_kw=28.0,
        output_rate=50.0,
        efficiency=42.0
    )
    # Should not raise
    validate_telemetry_bounds(anomaly_payload)


def test_validator_timestamp_window():
    now = datetime.now(timezone.utc)
    # Future timestamp > 1 hour
    future_time = now + timedelta(hours=2)
    with pytest.raises(TelemetryValidationError) as exc:
        validate_timestamp(future_time)
    assert "future" in str(exc.value)

    # Expired timestamp > 30 days
    ancient_time = now - timedelta(days=35)
    with pytest.raises(TelemetryValidationError) as exc:
        validate_timestamp(ancient_time)
    assert "retention" in str(exc.value)

    # Valid recent timestamp
    validate_timestamp(now - timedelta(seconds=10))


def test_validator_machine_exists(seed_machine, db_session: Session):
    # Registered machine succeeds
    m = validate_machine_exists("M01", db_session)
    assert m.id == "M01"

    # Unregistered machine raises TelemetryValidationError
    with pytest.raises(TelemetryValidationError) as exc:
        validate_machine_exists("M_NONEXISTENT", db_session)
    assert "not registered" in str(exc.value)


def test_idempotency_hash_generation():
    ts = datetime(2026, 9, 29, 10, 0, 0, tzinfo=timezone.utc)
    t1 = TelemetryCreate(
        machine_id="M01",
        timestamp=ts,
        temperature=75.30,
        vibration=2.500,
        current=14.20,
        voltage=400.0,
        rpm=1500.0,
        power_kw=15.00,
        load=1.00,
        output_rate=100.0
    )
    t2 = TelemetryCreate(
        machine_id="M01",
        timestamp=ts,
        temperature=75.30,
        vibration=2.500,
        current=14.20,
        voltage=400.0,
        rpm=1500.0,
        power_kw=15.00,
        load=1.00,
        output_rate=100.0
    )
    h1 = generate_telemetry_idempotency_hash(t1)
    h2 = generate_telemetry_idempotency_hash(t2)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex string


def test_pipeline_ingest_and_deduplication(seed_machine, db_session: Session):
    service = TelemetryIngestionService()
    service.idempotency_manager.clear()

    ts = datetime.now(timezone.utc)
    payload = TelemetryCreate(
        machine_id="M01",
        timestamp=ts,
        temperature=72.5,
        vibration=2.1,
        current=12.0,
        voltage=400.0,
        rpm=1500.0,
        power_kw=14.0,
        load=1.0,
        output_rate=95.0,
        efficiency=98.0,
        provenance=DataProvenance.OBSERVED
    )

    # First ingestion -> ACCEPTED
    res1 = service.ingest(payload, db_session)
    assert res1.status == IngestionItemStatus.ACCEPTED
    assert res1.telemetry_id is not None
    assert res1.is_duplicate is False
    assert res1.digital_twin_updated is True

    # Check database record
    db_record = db_session.query(TelemetryModel).filter_by(id=res1.telemetry_id).first()
    assert db_record is not None
    assert db_record.machine_id == "M01"
    assert db_record.temperature == 72.5

    # Second ingestion of identical payload -> DUPLICATE
    res2 = service.ingest(payload, db_session)
    assert res2.status == IngestionItemStatus.DUPLICATE
    assert res2.is_duplicate is True
    assert res2.digital_twin_updated is False

    # Ensure no duplicate database rows created
    count = db_session.query(TelemetryModel).filter_by(machine_id="M01").count()
    assert count == 1


def test_pipeline_batch_partial_acceptance(seed_machine, db_session: Session):
    service = TelemetryIngestionService()
    service.idempotency_manager.clear()

    now = datetime.now(timezone.utc)
    # Valid payload 1
    p1 = TelemetryCreate(
        machine_id="M01",
        timestamp=now - timedelta(seconds=20),
        temperature=70.0,
        vibration=1.5,
        current=10.0,
        rpm=1500.0,
        power_kw=12.0,
        output_rate=90.0
    )
    # Invalid payload 2 (unregistered machine)
    p2 = TelemetryCreate(
        machine_id="UNKNOWN_M09",
        timestamp=now - timedelta(seconds=15),
        temperature=70.0,
        vibration=1.5,
        current=10.0,
        rpm=1500.0,
        power_kw=12.0,
        output_rate=90.0
    )
    # Duplicate payload 3 (identical to p1)
    p3 = TelemetryCreate(
        machine_id="M01",
        timestamp=now - timedelta(seconds=20),
        temperature=70.0,
        vibration=1.5,
        current=10.0,
        rpm=1500.0,
        power_kw=12.0,
        output_rate=90.0
    )
    # Valid payload 4
    p4 = TelemetryCreate(
        machine_id="M01",
        timestamp=now - timedelta(seconds=5),
        temperature=74.0,
        vibration=2.0,
        current=13.0,
        rpm=1500.0,
        power_kw=15.0,
        output_rate=92.0
    )

    batch_result = service.ingest_batch([p1, p2, p3, p4], db_session)

    assert batch_result.total_received == 4
    assert batch_result.accepted_count == 2
    assert batch_result.rejected_count == 1
    assert batch_result.duplicate_count == 1
    assert len(batch_result.results) == 4


def test_pipeline_event_bus_publishing(seed_machine, db_session: Session):
    service = TelemetryIngestionService()
    service.idempotency_manager.clear()

    events_received = []

    def handler(evt: IngestionEvent):
        events_received.append(evt)

    service.event_bus.subscribe(IngestionEventType.TELEMETRY_INGESTED, handler)
    service.event_bus.subscribe(IngestionEventType.DIGITAL_TWIN_UPDATED, handler)

    payload = TelemetryCreate(
        machine_id="M01",
        timestamp=datetime.now(timezone.utc),
        temperature=71.0,
        vibration=1.8,
        current=11.0,
        rpm=1500.0,
        power_kw=13.0,
        output_rate=92.0
    )

    res = service.ingest(payload, db_session)
    assert res.status == IngestionItemStatus.ACCEPTED
    assert len(events_received) >= 2
    types = [e.event_type for e in events_received]
    assert IngestionEventType.TELEMETRY_INGESTED in types
    assert IngestionEventType.DIGITAL_TWIN_UPDATED in types
