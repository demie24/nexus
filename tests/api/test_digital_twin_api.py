"""
API Integration Tests for Digital Twin & Telemetry Batch Endpoints
Tests state retrieval, factory snapshots, batch ingestion partial acceptance,
and time-series query parameters.
"""

from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient


def test_digital_twin_api_endpoints(client: TestClient):
    # 1. Register machines
    client.post("/api/v1/machines", json={
        "id": "M01",
        "name": "Milling Machine 01",
        "line_id": "LINE_01",
        "machine_type": "Milling"
    })
    client.post("/api/v1/machines", json={
        "id": "M02",
        "name": "Lathe Machine 01",
        "line_id": "LINE_01",
        "machine_type": "Lathe"
    })

    # 2. Ingest telemetry for M01
    now = datetime.now(timezone.utc)
    tel_payload = {
        "machine_id": "M01",
        "timestamp": now.isoformat(),
        "temperature": 73.5,
        "vibration": 2.2,
        "pressure": 2.5,
        "current": 13.0,
        "voltage": 400.0,
        "rpm": 1500.0,
        "power_kw": 14.5,
        "load": 1.0,
        "output_rate": 88.0,
        "efficiency": 97.0
    }
    res_ingest = client.post("/api/v1/telemetry", json=tel_payload)
    assert res_ingest.status_code == 201

    # 3. Retrieve machine state: GET /api/v1/machines/{machine_id}/state
    res_state = client.get("/api/v1/machines/M01/state")
    assert res_state.status_code == 200
    state_data = res_state.json()
    assert state_data["machine_id"] == "M01"
    assert state_data["temperature"] == 73.5
    assert state_data["freshness"] == "FRESH"
    assert state_data["status"] in ["OPERATING", "NORMAL"]

    # 4. Non-existent machine state returns 404
    res_404 = client.get("/api/v1/machines/M_UNKNOWN/state")
    assert res_404.status_code == 404

    # 5. Retrieve all machine states: GET /api/v1/machines/states
    res_all_states = client.get("/api/v1/machines/states")
    assert res_all_states.status_code == 200
    all_states = res_all_states.json()
    assert len(all_states) >= 2
    machine_ids = [m["machine_id"] for m in all_states]
    assert "M01" in machine_ids
    assert "M02" in machine_ids

    # 6. Retrieve Factory Snapshot: GET /api/v1/factory/state
    res_factory = client.get("/api/v1/factory/state")
    assert res_factory.status_code == 200
    factory_data = res_factory.json()
    assert factory_data["total_machines"] >= 2
    assert "overall_health" in factory_data
    assert "operating_machines" in factory_data
    assert "stale_machines" in factory_data
    assert len(factory_data["machines"]) >= 2


def test_batch_ingestion_api(client: TestClient):
    # Register machine M03
    client.post("/api/v1/machines", json={
        "id": "M03",
        "name": "Drill Machine 01",
        "line_id": "LINE_01",
        "machine_type": "Drill"
    })

    now = datetime.now(timezone.utc)
    batch = [
        # Valid item 1
        {
            "machine_id": "M03",
            "timestamp": (now - timedelta(seconds=10)).isoformat(),
            "temperature": 68.0,
            "vibration": 1.2,
            "current": 8.0,
            "rpm": 1200.0,
            "power_kw": 9.0,
            "output_rate": 70.0
        },
        # Invalid item 2 (unregistered machine)
        {
            "machine_id": "GHOST_MACHINE",
            "timestamp": now.isoformat(),
            "temperature": 70.0,
            "vibration": 1.0,
            "current": 10.0,
            "rpm": 1200.0,
            "power_kw": 10.0,
            "output_rate": 70.0
        }
    ]

    res_batch = client.post("/api/v1/telemetry/batch", json=batch)
    assert res_batch.status_code == 200
    data = res_batch.json()
    assert data["total_received"] == 2
    assert data["accepted_count"] == 1
    assert data["rejected_count"] == 1
    assert len(data["results"]) == 2


def test_machine_telemetry_series_query(client: TestClient):
    client.post("/api/v1/machines", json={
        "id": "M04",
        "name": "Press Machine 01",
        "line_id": "LINE_02",
        "machine_type": "Press"
    })

    base_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    for i in range(5):
        client.post("/api/v1/telemetry", json={
            "machine_id": "M04",
            "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
            "temperature": 70.0 + i,
            "vibration": 1.5 + (i * 0.1),
            "current": 10.0,
            "rpm": 1400.0,
            "power_kw": 12.0,
            "output_rate": 80.0
        })

    # Query with limit
    res = client.get("/api/v1/machines/M04/telemetry?limit=3&order=desc")
    assert res.status_code == 200
    records = res.json()
    assert len(records) == 3
    # Check descending order (latest first)
    assert records[0]["temperature"] == 74.0

    # Query with order asc
    res_asc = client.get("/api/v1/machines/M04/telemetry?limit=2&order=asc")
    assert res_asc.status_code == 200
    records_asc = res_asc.json()
    assert len(records_asc) == 2
    assert records_asc[0]["temperature"] == 70.0


def test_metrics_observability_endpoint(client: TestClient):
    res = client.get("/metrics")
    assert res.status_code == 200
    data = res.json()
    assert "ingestion" in data
    ing = data["ingestion"]
    assert "telemetry_received_total" in ing
    assert "telemetry_accepted_total" in ing
    assert "ingestion_latency" in ing
    assert "digital_twin_latency" in ing
