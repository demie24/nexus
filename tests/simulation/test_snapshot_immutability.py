"""
Tests for Digital Twin Immutable Snapshot Capture and Isolation
Verifies that snapshots are immutable, accurately capture machine states, and prevent mutation of live state.
"""

from datetime import datetime, timezone
import pytest

from services.schemas import CounterfactualScenarioType, WhatIfSimulationRequest
from services.simulation.snapshot import get_snapshot_manager
from services.simulation.counterfactual import get_what_if_engine


def test_snapshot_creation_and_integrity():
    mgr = get_snapshot_manager()
    snapshot = mgr.create_snapshot()

    assert snapshot.snapshot_id.startswith("SNAP-")
    assert snapshot.factory_id == "NEXUS-FACTORY-01"
    assert len(snapshot.machines) == 6
    assert "M01" in snapshot.machine_states
    assert "M03" in snapshot.machine_states
    assert len(snapshot.state_hash) == 64

    # Verify state fields
    m3_state = snapshot.machine_states["M03"]
    assert m3_state["machine_id"] == "M03"
    assert m3_state["temperature"] > 0.0
    assert m3_state["health_score"] > 0.0


def test_snapshot_immutability_on_modification():
    mgr = get_snapshot_manager()
    snapshot = mgr.create_snapshot()
    orig_temp = snapshot.machine_states["M03"]["temperature"]

    # Attempt mutation of the retrieved snapshot object
    snapshot.machine_states["M03"]["temperature"] = 999.9

    # Re-retrieve from manager
    re_retrieved = mgr.get_snapshot(snapshot.snapshot_id)
    assert re_retrieved.machine_states["M03"]["temperature"] == orig_temp
    assert re_retrieved.machine_states["M03"]["temperature"] != 999.9


def test_simulation_does_not_mutate_snapshot():
    mgr = get_snapshot_manager()
    engine = get_what_if_engine()

    snapshot = mgr.create_snapshot()
    initial_health = snapshot.machine_states["M03"]["health_score"]

    # Run heavy simulation scenario
    req = WhatIfSimulationRequest(
        machine_id="M03",
        scenario_type=CounterfactualScenarioType.DO_NOTHING,
        horizon_hours=8.0,
        snapshot_id=snapshot.snapshot_id,
        persist=False
    )
    resp = engine.run_simulation(req, snapshot=snapshot)

    # Verify response ran and completed
    assert resp.status.value == "COMPLETED"

    # Re-fetch snapshot and verify internal states were untouched
    fresh_copy = mgr.get_snapshot(snapshot.snapshot_id)
    assert fresh_copy.machine_states["M03"]["health_score"] == initial_health
