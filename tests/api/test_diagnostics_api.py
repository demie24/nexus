"""
API integration tests for Diagnostics and Root Cause Analysis Endpoints.
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from database.models.models import MachineModel, TelemetryModel, DiagnosticModel


def seed_machine_and_telemetry(db: Session, machine_id: str = "M01"):
    """Seeds test machine and telemetry into the database."""
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

    now = datetime.now(timezone.utc)
    for i in range(15):
        tel = TelemetryModel(
            machine_id=machine_id,
            timestamp=now,
            temperature=50.0 + i,
            vibration=3.5 + 0.2 * i,
            current=22.0,
            voltage=400.0,
            rpm=1480.0,
            power_kw=13.0,
            load=1.0,
            efficiency=85.0 - i,
            output_rate=45.0,
            provenance="OBSERVED"
        )
        db.add(tel)
    db.commit()


def test_diagnostics_api_flow(client: TestClient, db_session: Session):
    seed_machine_and_telemetry(db_session, machine_id="M01")

    # 1. Trigger POST /api/v1/diagnostics/analyze
    analyze_payload = {
        "machine_id": "M01",
        "incident_id": "INC-TEST-001",
        "window_size": 15,
        "persist": True
    }
    resp = client.post("/api/v1/diagnostics/analyze", json=analyze_payload)
    if resp.status_code != 200:
        print("DIAGNOSTICS ANALYZE ERROR:", resp.status_code, resp.text)
    assert resp.status_code == 200
    data = resp.json()

    assert data["machine_id"] == "M01"
    assert data["incident_id"] == "INC-TEST-001"
    assert "likely_cause" in data
    assert "evidence_score" in data
    assert len(data["ranking"]) > 0
    assert "text_report" in data
    assert "NEXUS ROOT CAUSE ANALYSIS" in data["text_report"]

    diagnostic_id = data["diagnostic_id"]

    # 2. Query GET /api/v1/diagnostics
    list_resp = client.get("/api/v1/diagnostics?machine_id=M01")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert len(list_data) >= 1
    assert any(d["diagnostic_id"] == diagnostic_id for d in list_data)

    # 3. Query GET /api/v1/diagnostics/{id}
    detail_resp = client.get(f"/api/v1/diagnostics/{diagnostic_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["diagnostic_id"] == diagnostic_id

    # 4. Query GET /api/v1/machines/{machine_id}/diagnostics
    m_diag_resp = client.get("/api/v1/machines/M01/diagnostics")
    assert m_diag_resp.status_code == 200
    m_data = m_diag_resp.json()
    assert len(m_data) >= 1

    # 5. Non-existent machine error handling
    bad_resp = client.post("/api/v1/diagnostics/analyze", json={"machine_id": "NON_EXISTENT_MACHINE"})
    assert bad_resp.status_code == 404

    # 6. Non-existent diagnostic detail
    bad_detail = client.get("/api/v1/diagnostics/RCA-UNKNOWN-99999")
    assert bad_detail.status_code == 404
