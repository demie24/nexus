"""
API Integration Tests for What-If Counterfactual Simulation Endpoints
Tests /api/v1/simulation/what-if, /scenarios, /compare, /{simulation_id}, and /{simulation_id}/results.
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from database.models.models import MachineModel, TelemetryModel, MachineStateModel


def seed_machine_state(db: Session, machine_id: str = "M01"):
    """Seeds test machine and state into database."""
    machine = db.query(MachineModel).filter_by(id=machine_id).first()
    if not machine:
        machine = MachineModel(
            id=machine_id,
            name="CNC Unit 1",
            line_id="LINE_01",
            machine_type="CNC",
            nominal_power_kw=15.0,
            nominal_rpm=1500.0,
        )
        db.add(machine)
        db.commit()

    state = db.query(MachineStateModel).filter_by(machine_id=machine_id).first()
    if not state:
        state = MachineStateModel(
            machine_id=machine_id,
            status="OPERATING",
            health_score=75.0,
            failure_probability=0.25,
            load_factor=1.0,
            temperature=68.0,
            vibration=3.2,
            pressure=2.8,
            current=21.0,
            voltage=400.0,
            rpm=1490.0,
            power_kw=14.0,
            efficiency=95.0,
            output_rate=78.0,
            provenance="OBSERVED"
        )
        db.add(state)
        db.commit()


def test_simulation_api_full_flow(client: TestClient, db_session: Session):
    seed_machine_state(db_session, machine_id="M01")

    # 1. GET /api/v1/simulation/scenarios
    scen_resp = client.get("/api/v1/simulation/scenarios")
    assert scen_resp.status_code == 200
    scen_data = scen_resp.json()
    assert "supported_scenarios" in scen_data
    assert any(s["type"] == "LOAD_MODULATION" for s in scen_data["supported_scenarios"])

    # 2. POST /api/v1/simulation/what-if
    what_if_payload = {
        "machine_id": "M01",
        "scenario_type": "LOAD_MODULATION",
        "parameters": {"load_reduction": 0.20},
        "horizon_hours": 4.0,
        "seed": 42,
        "persist": True
    }
    resp = client.post("/api/v1/simulation/what-if", json=what_if_payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["machine_id"] == "M01"
    assert data["scenario"] == "LOAD_MODULATION"
    assert "result" in data
    assert "baseline_comparison" in data
    assert data["provenance"] == "SIMULATED"

    sim_id = data["simulation_id"]
    snapshot_id = data["snapshot_id"]

    # 3. GET /api/v1/simulation/{simulation_id}
    detail_resp = client.get(f"/api/v1/simulation/{sim_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["simulation_id"] == sim_id
    assert detail_data["snapshot_id"] == snapshot_id
    assert detail_data["status"] == "COMPLETED"

    # 4. GET /api/v1/simulation/{simulation_id}/results
    res_resp = client.get(f"/api/v1/simulation/{sim_id}/results")
    assert res_resp.status_code == 200
    res_data = res_resp.json()
    assert "outcome_metrics" in res_data
    assert "baseline_comparison" in res_data
    assert res_data["outcome_metrics"]["peak_temperature"] > 0.0

    # 5. POST /api/v1/simulation/compare
    compare_payload = {
        "machine_id": "M01",
        "horizon_hours": 4.0,
        "snapshot_id": snapshot_id,
        "seed": 42
    }
    comp_resp = client.post("/api/v1/simulation/compare", json=compare_payload)
    assert comp_resp.status_code == 200
    comp_data = comp_resp.json()

    assert comp_data["machine_id"] == "M01"
    assert comp_data["snapshot_id"] == snapshot_id
    assert len(comp_data["matrix"]) >= 2
    assert any(row["scenario"] == "DO_NOTHING" for row in comp_data["matrix"])
    assert any(row["scenario"] == "LOAD_MODULATION" for row in comp_data["matrix"])

    # 6. Error handling: invalid parameters
    bad_req = {
        "machine_id": "M01",
        "scenario_type": "LOAD_MODULATION",
        "parameters": {"load_reduction": 2.5}  # invalid
    }
    bad_resp = client.post("/api/v1/simulation/what-if", json=bad_req)
    assert bad_resp.status_code == 400

    # 7. Error handling: non-existent simulation
    not_found = client.get("/api/v1/simulation/SIM-NONEXISTENT-999")
    assert not_found.status_code == 404
