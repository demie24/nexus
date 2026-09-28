"""
Telemetry Transports for Virtual Factory Simulator
Supports In-Memory buffers, PostgreSQL database persistence, and MQTT broker publishing.
"""

from abc import ABC, abstractmethod
from collections import deque
import json
import logging
from typing import Dict, Any, List, Optional
import paho.mqtt.client as mqtt

from apps.api.config import get_settings
from database.session import SessionLocal
from database.models.models import TelemetryModel, MachineStateModel, MachineModel
from services.schemas import TelemetryCreate

logger = logging.getLogger("nexus.simulation.transports")
settings = get_settings()


class BaseTelemetryTransport(ABC):
    @abstractmethod
    def send(self, telemetry: TelemetryCreate, metadata: Dict[str, Any]) -> None:
        """Transports a telemetry packet and machine state metadata."""
        pass

    def close(self) -> None:
        """Closes any underlying network or IO resources."""
        pass


class InMemoryTransport(BaseTelemetryTransport):
    """
    In-memory ring buffer of recent telemetry packets. Ideal for CLI, testing, and zero-overhead queries.
    """
    def __init__(self, maxlen: int = 500):
        self.buffer: Dict[str, deque] = {}
        self.maxlen = maxlen
        self.latest_state: Dict[str, Dict[str, Any]] = {}

    def send(self, telemetry: TelemetryCreate, metadata: Dict[str, Any]) -> None:
        m_id = telemetry.machine_id
        if m_id not in self.buffer:
            self.buffer[m_id] = deque(maxlen=self.maxlen)
        self.buffer[m_id].append(telemetry)
        self.latest_state[m_id] = metadata

    def get_latest(self, machine_id: str) -> Optional[TelemetryCreate]:
        q = self.buffer.get(machine_id)
        return q[-1] if q else None

    def get_history(self, machine_id: str, limit: int = 50) -> List[TelemetryCreate]:
        q = self.buffer.get(machine_id, deque())
        items = list(q)
        return items[-limit:]


class MQTTTransport(BaseTelemetryTransport):
    """
    Publishes telemetry and digital twin state updates to Mosquitto MQTT broker.
    Topic pattern: nexus/factory/{factory_id}/line/{line_id}/machine/{machine_id}/telemetry
    """
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        factory_id: str = "FACTORY_01",
        client_id: str = "nexus-simulator-mqtt"
    ):
        self.host = host or settings.MQTT_BROKER_HOST
        self.port = port or settings.MQTT_BROKER_PORT
        self.factory_id = factory_id
        self.client_id = client_id
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_id)
        self.is_connected = False
        self._connect()

    def _connect(self) -> None:
        try:
            self.client.connect(self.host, self.port, keepalive=30)
            self.client.loop_start()
            self.is_connected = True
            logger.info(f"MQTTTransport connected to broker at {self.host}:{self.port}")
        except Exception as exc:
            logger.warning(f"MQTT broker connection failed ({self.host}:{self.port}): {exc}. Operating in offline mode.")
            self.is_connected = False

    def send(self, telemetry: TelemetryCreate, metadata: Dict[str, Any]) -> None:
        if not self.is_connected:
            return

        line_id = metadata.get("production_line", "LINE_01")
        machine_id = telemetry.machine_id

        # Hierarchical industrial topic:
        # nexus/factory/{factory_id}/line/{line_id}/machine/{machine_id}/telemetry
        topic = f"nexus/factory/{self.factory_id}/line/{line_id}/machine/{machine_id}/telemetry"

        payload = telemetry.model_dump(mode="json")
        payload["provenance"] = telemetry.provenance.value if hasattr(telemetry.provenance, "value") else str(telemetry.provenance)

        try:
            msg_str = json.dumps(payload)
            self.client.publish(topic, msg_str, qos=0)
        except Exception as exc:
            logger.warning(f"Failed to publish telemetry to MQTT: {exc}")

    def close(self) -> None:
        if self.is_connected:
            try:
                self.client.loop_stop()
                self.client.disconnect()
                self.is_connected = False
            except Exception:
                pass


class DatabaseTransport(BaseTelemetryTransport):
    """
    Directly persists telemetry and updates Digital Twin machine_states in PostgreSQL.
    """
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or SessionLocal
        self.enabled = True

    def send(self, telemetry: TelemetryCreate, metadata: Dict[str, Any]) -> None:
        if not self.enabled:
            return

        session = self.session_factory()
        try:
            # 1. Ensure machine exists in registry
            machine = session.query(MachineModel).filter_by(id=telemetry.machine_id).first()
            if not machine:
                machine = MachineModel(
                    id=telemetry.machine_id,
                    name=metadata.get("name", telemetry.machine_id),
                    line_id=metadata.get("production_line", "LINE_01"),
                    machine_type=metadata.get("type", "Industrial"),
                    rated_load=metadata.get("rated_load", 1.0),
                    maintenance_status=metadata.get("maintenance_status", "OK"),
                )
                session.add(machine)
                session.commit()

            # 2. Insert telemetry record
            tel_data = telemetry.model_dump()
            tel_data["provenance"] = telemetry.provenance.value if hasattr(telemetry.provenance, "value") else str(telemetry.provenance)
            record = TelemetryModel(**tel_data)
            session.add(record)

            # 3. Update Digital Twin machine_states record (State Tracking foundation)
            state = session.query(MachineStateModel).filter_by(machine_id=telemetry.machine_id).first()
            if not state:
                state = MachineStateModel(
                    machine_id=telemetry.machine_id,
                    status=metadata.get("operating_status", "OPERATING"),
                    health_score=metadata.get("health_score", 100.0),
                    failure_probability=metadata.get("failure_probability", 0.0),
                    load_factor=telemetry.load,
                    provenance="OBSERVED"
                )
                session.add(state)
            else:
                state.status = metadata.get("operating_status", state.status)
                state.health_score = metadata.get("health_score", state.health_score)
                state.failure_probability = metadata.get("failure_probability", state.failure_probability)
                state.load_factor = telemetry.load
                state.provenance = "OBSERVED"

            session.commit()
        except Exception as exc:
            session.rollback()
            logger.warning(f"DatabaseTransport persistence error for {telemetry.machine_id}: {exc}")
        finally:
            session.close()


class CompositeTransport(BaseTelemetryTransport):
    """Broadcasts telemetry packets to multiple registered transport backends."""
    def __init__(self, transports: Optional[List[BaseTelemetryTransport]] = None):
        self.transports = transports or []

    def add(self, transport: BaseTelemetryTransport) -> None:
        self.transports.append(transport)

    def send(self, telemetry: TelemetryCreate, metadata: Dict[str, Any]) -> None:
        for t in self.transports:
            try:
                t.send(telemetry, metadata)
            except Exception as err:
                logger.error(f"Error in transport {t.__class__.__name__}: {err}")

    def close(self) -> None:
        for t in self.transports:
            try:
                t.close()
            except Exception:
                pass
