"""
API Tests for Telemetry Ingestion Endpoints
"""

from datetime import datetime, timezone
from fastapi.testclient import TestClient


def test_ingest_telemetry_success(client: TestClient):
    # First register machine
    client.post("/api/v1/machines", json={
        "id": "M01",
        "name": "Milling Machine 1",
        "line_id": "LINE_01",
        "machine_type": "Milling"
    })

    telemetry_payload = {
        "machine_id": "M01",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature": 75.3,
        "vibration": 3.2,
        "current": 14.5,
        "voltage": 400.0,
        "rpm": 1490.0,
        "power_kw": 15.8,
        "output_rate": 84.0,
        "efficiency": 96.0,
        "provenance": "OBSERVED"
    }

    res = client.post("/api/v1/telemetry", json=telemetry_payload)
    assert res.status_code == 201
    data = res.json()
    assert data["machine_id"] == "M01"
    assert data["temperature"] == 75.3
    assert data["provenance"] == "OBSERVED"

    # Fetch latest telemetry
    res_latest = client.get("/api/v1/telemetry/M01/latest")
    assert res_latest.status_code == 200
    latest_data = res_latest.json()
    assert latest_data["temperature"] == 75.3


def test_ingest_telemetry_unregistered_machine_returns_404(client: TestClient):
    telemetry_payload = {
        "machine_id": "UNREGISTERED_M99",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature": 70.0,
        "vibration": 2.0,
        "current": 10.0,
        "rpm": 1400.0,
        "power_kw": 12.0,
        "output_rate": 80.0
    }
    res = client.post("/api/v1/telemetry", json=telemetry_payload)
    assert res.status_code == 404
