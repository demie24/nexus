"""
Tests for Multi-Machine Cascade & Line Bottleneck Effects
Verifies that machine interventions correctly compute production line impacts and avoid unsupported cross-line assumptions.
"""

import pytest
from services.schemas import CounterfactualScenarioType, WhatIfSimulationRequest
from services.simulation.snapshot import get_snapshot_manager
from services.simulation.counterfactual import get_what_if_engine


def test_m03_shutdown_line_01_cascade():
    mgr = get_snapshot_manager()
    engine = get_what_if_engine()

    snapshot = mgr.create_snapshot()

    req = WhatIfSimulationRequest(
        machine_id="M03",
        scenario_type=CounterfactualScenarioType.EMERGENCY_STOP,
        parameters={},
        horizon_hours=4.0,
        snapshot_id=snapshot.snapshot_id,
        persist=False
    )
    resp = engine.run_simulation(req, snapshot=snapshot)

    # Line 1 cascade checks
    assert "M01" in resp.affected_cascade_machines
    assert "M02" in resp.affected_cascade_machines
    # Line 2 machines must NOT be affected
    assert "M04" not in resp.affected_cascade_machines
    assert "M05" not in resp.affected_cascade_machines
    assert "M06" not in resp.affected_cascade_machines

    # Line impact
    cascade = resp.cascade_impact
    assert cascade["line_id"] == "LINE_01"
    assert cascade["line_throughput_loss_pct"] == 100.0
    assert cascade["factory_throughput_loss_pct"] > 0.0


def test_m03_load_modulation_cascade_throttling():
    mgr = get_snapshot_manager()
    engine = get_what_if_engine()

    snapshot = mgr.create_snapshot()

    req = WhatIfSimulationRequest(
        machine_id="M03",
        scenario_type=CounterfactualScenarioType.LOAD_MODULATION,
        parameters={"load_reduction": 0.40},
        horizon_hours=4.0,
        snapshot_id=snapshot.snapshot_id,
        persist=False
    )
    resp = engine.run_simulation(req, snapshot=snapshot)

    cascade = resp.cascade_impact
    assert cascade["line_id"] == "LINE_01"
    assert "M01" in resp.affected_cascade_machines
    assert cascade["line_throughput_loss_pct"] >= 35.0  # Approx 40% line output throttle
