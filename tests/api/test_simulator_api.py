"""
API Tests for Virtual Factory Simulator Endpoints
"""

from fastapi.testclient import TestClient


def test_get_simulator_status(client: TestClient):
    res = client.get("/api/v1/simulator/status")
    assert res.status_code == 200
    data = res.json()
    assert data["factory_id"] == "FACTORY_01"
    assert data["machine_count"] == 6
    assert "time_scale" in data


def test_list_simulated_machines(client: TestClient):
    res = client.get("/api/v1/simulator/machines")
    assert res.status_code == 200
    machines = res.json()
    assert len(machines) == 6
    ids = [m["machine_id"] for m in machines]
    assert "M01" in ids
    assert "M03" in ids


def test_trigger_and_recover_scenario_api(client: TestClient):
    # Trigger scenario
    payload = {
        "scenario_type": "bearing_degradation",
        "machine_id": "M03",
        "severity": 0.85,
        "duration_sim_seconds": 250.0
    }
    res_trig = client.post("/api/v1/simulator/scenarios/trigger", json=payload)
    assert res_trig.status_code == 201
    scen_data = res_trig.json()
    scen_id = scen_data["scenario_id"]
    assert scen_data["status"] == "ACTIVE"

    # List scenarios
    res_list = client.get("/api/v1/simulator/scenarios")
    assert res_list.status_code == 200
    active_ids = [s["scenario_id"] for s in res_list.json()]
    assert scen_id in active_ids

    # Recover scenario
    res_rec = client.post(f"/api/v1/simulator/scenarios/{scen_id}/recover")
    assert res_rec.status_code == 200


def test_step_simulation_api(client: TestClient):
    payload = {"count": 2, "dt_seconds": 1.0}
    res = client.post("/api/v1/simulator/step", json=payload)
    assert res.status_code == 200
    frames = res.json()
    # 2 steps * 6 machines = 12 frames
    assert len(frames) == 12
    assert frames[0]["provenance"] == "OBSERVED"
