"""
API Integration Tests for Predictive Intelligence Endpoints
Tests /predictions and /machines/{id}/predictions, /risk-forecast, and /rul routes.
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from database.models.models import MachineModel, PredictionModel, MachineStateModel
from services.schemas import (
    SeverityLevel,
    OperatingStatus,
    PredictionStatus,
    DataProvenance,
)


@pytest.fixture
def registered_machine(db_session: Session):
    """Seed machine and initial state in the test database."""
    m = MachineModel(
        id="M-TEST-PRED",
        name="Test Prediction Machine",
        line_id="LINE_01",
        machine_type="CNC Milling",
        nominal_power_kw=15.0,
        nominal_rpm=1500.0,
        max_temperature_c=95.0,
        max_vibration_mms=8.0,
        rated_load=1.0,
        maintenance_status="OK",
    )
    db_session.add(m)
    state = MachineStateModel(
        machine_id="M-TEST-PRED",
        status="OPERATING",
        health_score=92.5,
        failure_probability=0.04,
        load_factor=1.0,
    )
    db_session.add(state)
    db_session.commit()
    return m


def test_list_predictions_empty(client: TestClient):
    """Verify empty list returned when no predictions exist."""
    resp = client.get("/api/v1/predictions")
    assert resp.status_code == 200
    assert resp.json() == []


def test_prediction_analyze_cold_start_and_persist(client: TestClient, registered_machine: MachineModel):
    """Verify on-demand analyze endpoint works, returns cold start info, and persists."""
    payload = {
        "machine_id": "M-TEST-PRED",
        "horizon_minutes": 120,
        "persist": True,
    }
    resp = client.post("/api/v1/predictions/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["machine_id"] == "M-TEST-PRED"
    assert "prediction" in data
    assert "risk_forecast" in data
    assert "health_trajectory" in data
    assert "rul" in data
    assert "contributing_factors" in data

    # Check prediction fields
    pred = data["prediction"]
    assert pred["machine_id"] == "M-TEST-PRED"
    assert pred["prediction_status"] == PredictionStatus.INSUFFICIENT_DATA.value
    assert pred["provenance"] == DataProvenance.PREDICTED.value
    assert pred["id"] is not None

    # Check database persistence
    list_resp = client.get(f"/api/v1/predictions?machine_id=M-TEST-PRED")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


def test_get_prediction_detail(client: TestClient, registered_machine: MachineModel):
    """Verify retrieving specific prediction by ID."""
    # Analyze and persist
    post_resp = client.post("/api/v1/predictions/analyze", json={"machine_id": "M-TEST-PRED", "persist": True})
    pred_id = post_resp.json()["prediction"]["id"]

    get_resp = client.get(f"/api/v1/predictions/{pred_id}")
    assert get_resp.status_code == 200
    detail = get_resp.json()
    assert detail["id"] == pred_id
    assert detail["machine_id"] == "M-TEST-PRED"


def test_get_prediction_detail_not_found(client: TestClient):
    """Verify 404 returned for non-existent prediction ID."""
    resp = client.get("/api/v1/predictions/999999")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_machine_sub_routes_predictions_risk_rul(client: TestClient, registered_machine: MachineModel):
    """Verify /machines/{id}/predictions, /machines/{id}/risk-forecast, and /machines/{id}/rul."""
    # 1. Predictions sub-route
    pred_resp = client.get("/api/v1/machines/M-TEST-PRED/predictions")
    assert pred_resp.status_code == 200
    assert isinstance(pred_resp.json(), list)

    # 2. Risk forecast sub-route
    risk_resp = client.get("/api/v1/machines/M-TEST-PRED/risk-forecast")
    assert risk_resp.status_code == 200
    r_data = risk_resp.json()
    assert r_data["machine_id"] == "M-TEST-PRED"
    assert len(r_data["horizons"]) == 4
    for h in r_data["horizons"]:
        assert h["horizon_minutes"] in [60, 120, 240, 360]
        assert 0.0 <= h["failure_probability"] <= 1.0

    # 3. RUL sub-route
    rul_resp = client.get("/api/v1/machines/M-TEST-PRED/rul")
    assert rul_resp.status_code == 200
    rul_data = rul_resp.json()
    assert rul_data["machine_id"] == "M-TEST-PRED"
    assert rul_data["remaining_useful_life_hours"] >= 0.0
    assert rul_data["provenance"] == DataProvenance.PREDICTED.value


def test_machine_prediction_routes_not_found(client: TestClient):
    """Verify 404 returned when machine does not exist."""
    assert client.get("/api/v1/machines/NONEXISTENT/predictions").status_code == 404
    assert client.get("/api/v1/machines/NONEXISTENT/risk-forecast").status_code == 404
    assert client.get("/api/v1/machines/NONEXISTENT/rul").status_code == 404
    assert client.post("/api/v1/predictions/analyze", json={"machine_id": "NONEXISTENT"}).status_code == 404
