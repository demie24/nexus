"""
API Tests for Machine Registry Endpoints
"""

from fastapi.testclient import TestClient


def test_register_and_get_machine(client: TestClient):
    payload = {
        "id": "M01",
        "name": "CNC Milling Center 1",
        "line_id": "LINE_01",
        "machine_type": "Milling",
        "nominal_power_kw": 22.0,
        "nominal_rpm": 1800.0,
        "max_temperature_c": 92.0,
        "max_vibration_mms": 7.5
    }
    # Register machine
    res = client.post("/api/v1/machines", json=payload)
    assert res.status_code == 201
    created = res.json()
    assert created["id"] == "M01"
    assert created["is_active"] is True

    # Get specific machine
    res_get = client.get("/api/v1/machines/M01")
    assert res_get.status_code == 200
    assert res_get.json()["name"] == "CNC Milling Center 1"

    # List machines
    res_list = client.get("/api/v1/machines")
    assert res_list.status_code == 200
    machines = res_list.json()
    assert len(machines) == 1
    assert machines[0]["id"] == "M01"


def test_register_duplicate_machine_conflict(client: TestClient):
    payload = {
        "id": "M02",
        "name": "Industrial Lathe 1",
        "line_id": "LINE_01",
        "machine_type": "Lathe"
    }
    res1 = client.post("/api/v1/machines", json=payload)
    assert res1.status_code == 201

    # Duplicate should return 409 Conflict
    res2 = client.post("/api/v1/machines", json=payload)
    assert res2.status_code == 409


def test_get_nonexistent_machine_returns_404(client: TestClient):
    res = client.get("/api/v1/machines/NONEXISTENT_999")
    assert res.status_code == 404
