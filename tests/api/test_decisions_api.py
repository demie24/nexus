"""
Integration Tests for Multi-Criteria Decision Engine API Endpoints
Verifies REST endpoints for on-demand analysis, policies query, listing, and detail views.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from database.models.models import MachineModel
from services.schemas import OperatingStatus


def _seed_machine(db: Session, machine_id: str = "M01"):
    m = db.query(MachineModel).filter(MachineModel.id == machine_id).first()
    if not m:
        m = MachineModel(
            id=machine_id,
            name="CNC Milling Machine 01",
            line_id="LINE_A",
            machine_type="CNC_MILL",
            nominal_power_kw=15.0,
            nominal_rpm=1500.0,
            max_temperature_c=95.0,
            max_vibration_mms=8.0,
            rated_load=1.0,
            maintenance_status="OK",
            is_active=True,
        )
        db.add(m)
        db.commit()


def test_get_decision_policies(client: TestClient):
    resp = client.get("/api/v1/decision-policies")
    assert resp.status_code == 200
    data = resp.json()
    assert "policies" in data
    assert "BALANCED" in data["policies"]
    assert "SAFETY_FIRST" in data["policies"]
    assert "PRODUCTION_FIRST" in data["policies"]
    assert "default_constraints" in data
    assert "criteria_definitions" in data

    # Also test alias route
    resp_alias = client.get("/api/v1/decisions/policies")
    assert resp_alias.status_code == 200


def test_analyze_decision_endpoint(client: TestClient, db_session: Session):
    _seed_machine(db_session, "M01")

    payload = {
        "machine_id": "M01",
        "policy_profile": "BALANCED",
        "horizon_hours": 4.0,
        "persist": True,
    }

    resp = client.post("/api/v1/decisions/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["machine_id"] == "M01"
    assert data["decision_id"].startswith("DEC-M01-")
    assert data["policy_profile"] == "BALANCED"
    assert len(data["ranked_candidates"]) == 6
    assert data["top_recommended_candidate"] is not None
    assert "decision_explanation" in data
    assert len(data["sensitivity_analysis"]) == 3


def test_analyze_decision_unknown_machine(client: TestClient):
    payload = {
        "machine_id": "UNKNOWN_MACHINE_999",
        "policy_profile": "BALANCED",
        "horizon_hours": 4.0,
    }
    resp = client.post("/api/v1/decisions/analyze", json=payload)
    assert resp.status_code == 404
    assert "not registered" in resp.json()["detail"]


def test_list_and_get_decisions(client: TestClient, db_session: Session):
    _seed_machine(db_session, "M01")

    # Run analysis first to create a record
    payload = {
        "machine_id": "M01",
        "policy_profile": "BALANCED",
        "horizon_hours": 2.0,
        "persist": True,
    }
    analyze_resp = client.post("/api/v1/decisions/analyze", json=payload)
    assert analyze_resp.status_code == 200
    decision_id = analyze_resp.json()["decision_id"]

    # Test listing decisions
    list_resp = client.get("/api/v1/decisions?machine_id=M01")
    assert list_resp.status_code == 200
    decisions = list_resp.json()
    assert len(decisions) >= 1
    assert any(d["decision_id"] == decision_id for d in decisions)

    # Test get decision by ID
    detail_resp = client.get(f"/api/v1/decisions/{decision_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["decision_id"] == decision_id
    assert detail_data["machine_id"] == "M01"
    assert len(detail_data["ranked_candidates"]) == 6

    # Test 404 on nonexistent decision ID
    bad_resp = client.get("/api/v1/decisions/DEC-NONEXISTENT")
    assert bad_resp.status_code == 404


def test_get_machine_decisions_endpoint(client: TestClient, db_session: Session):
    _seed_machine(db_session, "M01")

    # Create analysis
    payload = {
        "machine_id": "M01",
        "policy_profile": "SAFETY_FIRST",
        "horizon_hours": 2.0,
        "persist": True,
    }
    client.post("/api/v1/decisions/analyze", json=payload)

    resp = client.get("/api/v1/machines/M01/decisions")
    assert resp.status_code == 200
    records = resp.json()
    assert len(records) >= 1
    assert records[0]["machine_id"] == "M01"
