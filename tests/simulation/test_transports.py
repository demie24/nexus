"""
Integration Tests for Telemetry Transports (InMemory, Database, and MQTT)
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from database.session import SessionLocal
from database.models.models import TelemetryModel, MachineStateModel, MachineModel
from services.simulation.engine import VirtualFactorySimulator
from services.simulation.transports import (
    InMemoryTransport,
    DatabaseTransport,
    MQTTTransport,
)


def test_in_memory_transport():
    sim = VirtualFactorySimulator(seed=42)
    # in_memory_transport is enabled by default
    sim.step(1.0)

    tel = sim.get_latest_telemetry("M01")
    assert tel is not None
    assert tel.machine_id == "M01"
    assert tel.temperature > 50.0


def test_database_transport_persistence(db_session: Session):
    sim = VirtualFactorySimulator(seed=42)
    db_transport = DatabaseTransport(session_factory=lambda: db_session)
    sim.add_transport(db_transport)

    initial_tel_count = db_session.query(TelemetryModel).count()

    # Step simulator (generates 6 frames)
    sim.step(1.0)

    new_tel_count = db_session.query(TelemetryModel).count()
    assert new_tel_count == initial_tel_count + 6

    # Verify machine states updated
    m01_state = db_session.query(MachineStateModel).filter_by(machine_id="M01").first()
    assert m01_state is not None
    assert m01_state.health_score > 90.0


def test_mqtt_transport_instantiation_and_publish():
    # Test connection and publish to local Mosquitto
    mqtt_t = MQTTTransport(host="localhost", port=1884)
    sim = VirtualFactorySimulator(seed=42, transports=[mqtt_t])

    # Should publish without raising exceptions
    sim.step(1.0)

    mqtt_t.close()
