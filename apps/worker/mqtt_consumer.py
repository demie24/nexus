"""
NEXUS MQTT Ingestion Consumer Worker
Subscribes to factory telemetry topics, validates payloads, and routes messages
into the Telemetry Ingestion Service and Digital Twin Engine.
Topic schema: nexus/factory/{factory_id}/line/{line_id}/machine/{machine_id}/telemetry
"""

import json
import logging
import re
import signal
import sys
import time
from typing import Optional
import paho.mqtt.client as mqtt

from apps.api.config import get_settings
from database.session import SessionLocal
from services.ingestion.pipeline import get_ingestion_service
from services.ingestion.metrics import get_metrics_collector

logger = logging.getLogger("nexus.worker.mqtt")
settings = get_settings()

TOPIC_PATTERN = re.compile(
    r"^nexus/factory/(?P<factory_id>[^/]+)/line/(?P<line_id>[^/]+)/machine/(?P<machine_id>[^/]+)/telemetry$"
)


class MQTTConsumerWorker:
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        topic: str = "nexus/factory/+/line/+/machine/+/telemetry",
        client_id: str = "nexus-mqtt-ingestion-worker"
    ):
        self.host = host or settings.MQTT_BROKER_HOST
        self.port = port or settings.MQTT_BROKER_PORT
        self.topic = topic
        self.client_id = client_id
        self.ingestion_service = get_ingestion_service()
        self.metrics = get_metrics_collector()
        self.is_running = False

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.client_id
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info(f"MQTT Consumer successfully connected to {self.host}:{self.port}")
            self.metrics.set_mqtt_status(True)
            client.subscribe(self.topic, qos=1)
            logger.info(f"Subscribed to telemetry topic: '{self.topic}'")
        else:
            logger.error(f"MQTT Consumer connection rejected with code: {rc}")
            self.metrics.set_mqtt_status(False)

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        logger.warning(f"MQTT Consumer disconnected (rc={rc})")
        self.metrics.set_mqtt_status(False)

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        match = TOPIC_PATTERN.match(topic)
        if not match:
            logger.warning(f"Received MQTT message on non-standard topic: {topic}")

        try:
            raw_text = msg.payload.decode("utf-8")
        except UnicodeDecodeError as u_err:
            logger.error(f"Invalid non-UTF8 payload on topic {topic}: {u_err}")
            self.metrics.record_received(1)
            self.metrics.record_rejected(1)
            return

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as j_err:
            logger.error(f"Malformed JSON payload on topic {topic}: {j_err}")
            self.metrics.record_received(1)
            self.metrics.record_rejected(1)
            return

        if not isinstance(data, dict):
            logger.error(f"Invalid JSON type (expected dict, got {type(data).__name__}) on topic {topic}")
            self.metrics.record_received(1)
            self.metrics.record_rejected(1)
            return

        # If payload omitted machine_id, infer from topic
        if match and "machine_id" not in data:
            data["machine_id"] = match.group("machine_id")

        # Ingest through pipeline
        session = SessionLocal()
        try:
            result = self.ingestion_service.ingest_dict(data, session)
            logger.debug(
                f"MQTT Ingestion: machine={result.machine_id} status={result.status.value} msg={result.message}"
            )
        except Exception as exc:
            logger.error(f"Unexpected error processing MQTT message: {exc}", exc_info=True)
            self.metrics.record_rejected(1)
        finally:
            session.close()

    def start(self) -> None:
        """Starts the MQTT worker loop in a background thread."""
        logger.info(f"Starting MQTT Consumer connecting to {self.host}:{self.port}...")
        try:
            self.client.connect(self.host, self.port, keepalive=30)
            self.client.loop_start()
            self.is_running = True
        except Exception as exc:
            logger.warning(f"Failed to connect to MQTT broker ({self.host}:{self.port}): {exc}")
            self.metrics.set_mqtt_status(False)

    def stop(self) -> None:
        """Stops the worker gracefully."""
        if self.is_running:
            logger.info("Stopping MQTT Consumer...")
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass
            self.is_running = False
            self.metrics.set_mqtt_status(False)


def run_worker():
    """CLI Entrypoint for running the worker in a standalone process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    )
    worker = MQTTConsumerWorker()
    worker.start()

    def handle_exit(sig, frame):
        logger.info("Termination signal received. Exiting...")
        worker.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    logger.info("MQTT Consumer Worker running. Press Ctrl+C to stop.")
    while True:
        time.sleep(1)


if __name__ == "__main__":
    run_worker()
