"""
API Integration Tests for Anomaly Detection Endpoints
Tests /anomalies, /anomalies/{id}, /anomalies/analyze, and machine-specific anomaly endpoints.
"""

from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient


def test_anomaly_api_lifecycle(client: TestClient):
    # 1. Register test machine
    client.post("/api/v1/machines", json={
        "id": "M01",
        "name": "Milling Machine 01",
        "line_id": "LINE_01",
        "machine_type": "Milling",
        "nominal_power_kw": 15.0,
        "nominal_rpm": 1500.0,
    })

    # 2. Establish baseline by sending 10 nominal frames via /telemetry
    now = datetime.now(timezone.utc) - timedelta(minutes=5)
    for i in range(10):
        client.post("/api/v1/telemetry", json={
            "machine_id": "M01",
            "timestamp": (now + timedelta(seconds=i * 2)).isoformat(),
            "temperature": 65.0,
            "vibration": 2.2,
            "pressure": 2.5,
            "current": 12.0,
            "voltage": 400.0,
            "rpm": 1500.0,
            "power_kw": 15.0,
            "output_rate": 85.0,
            "efficiency": 96.0
        })

    # 3. Check machine anomaly status: should be ESTABLISHED and NORMAL
    res_status = client.get("/api/v1/machines/M01/anomaly-status")
    assert res_status.status_code == 200
    st_data = res_status.json()
    assert st_data["machine_id"] == "M01"
    assert st_data["baseline_status"] == "ESTABLISHED"
    assert st_data["has_active_anomaly"] is False

    # 4. Trigger on-demand anomaly analysis with severe thermal & vibration failure
    anomaly_payload = {
        "machine_id": "M01",
        "timestamp": (now + timedelta(seconds=30)).isoformat(),
        "temperature": 115.0,
        "vibration": 9.8,
        "pressure": 3.8,
        "current": 25.0,
        "voltage": 400.0,
        "rpm": 1400.0,
        "power_kw": 28.0,
        "load": 1.4,
        "output_rate": 50.0,
        "efficiency": 60.0
    }
    res_analyze = client.post("/api/v1/anomalies/analyze", json=anomaly_payload)
    assert res_analyze.status_code == 200
    analysis = res_analyze.json()

    assert analysis["anomaly_detected"] is True
    assert analysis["severity"] in ["HIGH", "CRITICAL"]
    assert analysis["anomaly_score"] >= 0.70
    assert analysis["anomaly_type"] in ["MACHINE_BEHAVIOR", "MULTIVARIATE_ANOMALY"]
    assert len(analysis["triggered_signals"]) >= 2
    assert "latencies_ms" in analysis["detector_evidence"]
    assert analysis["persisted_anomaly_id"] is not None

    persisted_id = analysis["persisted_anomaly_id"]

    # 5. Retrieve anomaly by ID: GET /api/v1/anomalies/{id}
    res_detail = client.get(f"/api/v1/anomalies/{persisted_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["id"] == persisted_id
    assert detail["machine_id"] == "M01"
    assert detail["severity"] in ["HIGH", "CRITICAL"]
    assert detail["resolved"] is False

    # 6. List anomalies with filter: GET /api/v1/anomalies?machine_id=M01
    res_list = client.get("/api/v1/anomalies?machine_id=M01&resolved=false")
    assert res_list.status_code == 200
    anomalies_list = res_list.json()
    assert len(anomalies_list) >= 1
    assert anomalies_list[0]["id"] == persisted_id

    # 7. Machine anomalies endpoint: GET /api/v1/machines/M01/anomalies
    res_mach_anomalies = client.get("/api/v1/machines/M01/anomalies")
    assert res_mach_anomalies.status_code == 200
    mach_anomalies = res_mach_anomalies.json()
    assert len(mach_anomalies) >= 1

    # 8. Machine anomaly status now reflects active anomaly
    res_status_active = client.get("/api/v1/machines/M01/anomaly-status")
    assert res_status_active.status_code == 200
    act_data = res_status_active.json()
    assert act_data["has_active_anomaly"] is True
    assert act_data["active_anomaly_count"] >= 1
    assert act_data["latest_severity"] in ["HIGH", "CRITICAL"]
