"""
Unit Tests for MQTT Telemetry Consumer Worker
Tests topic routing, payload validation, error tolerance against malformed JSON, and pipeline routing.
"""

from unittest.mock import MagicMock
import json
import pytest
from sqlalchemy.orm import Session

from apps.worker.mqtt_consumer import MQTTConsumerWorker, TOPIC_PATTERN
from database.models.models import MachineModel, TelemetryModel
from services.ingestion.metrics import get_metrics_collector


@pytest.fixture
def seed_machine_worker(db_session: Session):
    m = MachineModel(
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
    db_session.add(m)
    db_session.commit()
    return m


def test_mqtt_topic_regex_pattern():
    valid_topic = "nexus/factory/FACTORY_01/line/LINE_01/machine/M01/telemetry"
    match = TOPIC_PATTERN.match(valid_topic)
    assert match is not None
    assert match.group("factory_id") == "FACTORY_01"
    assert match.group("line_id") == "LINE_01"
    assert match.group("machine_id") == "M01"

    invalid_topic_1 = "nexus/factory/FACTORY_01/telemetry"
    assert TOPIC_PATTERN.match(invalid_topic_1) is None

    invalid_topic_2 = "random/topic/test"
    assert TOPIC_PATTERN.match(invalid_topic_2) is None


def test_mqtt_consumer_handles_malformed_json_gracefully():
    worker = MQTTConsumerWorker()
    metrics = get_metrics_collector()
    before_rejected = metrics.telemetry_rejected_total

    # Create mock message with malformed JSON
    mock_msg = MagicMock()
    mock_msg.topic = "nexus/factory/FACTORY_01/line/LINE_01/machine/M01/telemetry"
    mock_msg.payload = b"NOT_A_VALID_JSON{{"

    # Should not raise exception
    worker._on_message(None, None, mock_msg)

    assert metrics.telemetry_rejected_total > before_rejected


def test_mqtt_consumer_handles_non_dict_json():
    worker = MQTTConsumerWorker()
    metrics = get_metrics_collector()
    before_rejected = metrics.telemetry_rejected_total

    mock_msg = MagicMock()
    mock_msg.topic = "nexus/factory/FACTORY_01/line/LINE_01/machine/M01/telemetry"
    mock_msg.payload = b"[1, 2, 3]"

    worker._on_message(None, None, mock_msg)
    assert metrics.telemetry_rejected_total > before_rejected


def test_mqtt_consumer_connection_callbacks():
    worker = MQTTConsumerWorker()
    metrics = get_metrics_collector()

    # Simulate connect
    mock_client = MagicMock()
    worker._on_connect(mock_client, None, None, 0)
    assert metrics.mqtt_connection_status is True
    mock_client.subscribe.assert_called_once_with(worker.topic, qos=1)

    # Simulate disconnect
    worker._on_disconnect(mock_client, None, None, 1)
    assert metrics.mqtt_connection_status is False
