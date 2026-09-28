"""
API Tests for Audit Log Endpoints
"""

from fastapi.testclient import TestClient


def test_record_and_list_audit_logs(client: TestClient):
    payload = {
        "actor": "operator_sarah",
        "action": "APPROVED_LOAD_REDUCTION",
        "resource_type": "Recommendation",
        "resource_id": "REC-M03-01",
        "details": {"action": "REDUCE_LOAD", "target_pct": 70},
        "provenance": "OBSERVED"
    }

    res_post = client.post("/api/v1/audit", json=payload)
    assert res_post.status_code == 201
    created = res_post.json()
    assert created["actor"] == "operator_sarah"
    assert created["resource_id"] == "REC-M03-01"

    # List audit logs
    res_list = client.get("/api/v1/audit")
    assert res_list.status_code == 200
    logs = res_list.json()
    assert len(logs) >= 1
    assert logs[0]["actor"] == "operator_sarah"

    # Filter by resource type
    res_filtered = client.get("/api/v1/audit?resource_type=Recommendation")
    assert res_filtered.status_code == 200
    assert len(res_filtered.json()) >= 1
