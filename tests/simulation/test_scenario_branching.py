"""
Tests for Scenario Branching Isolation
Verifies that multiple branches forking from the same snapshot remain strictly isolated.
"""

import pytest
from services.schemas import CounterfactualScenarioType, WhatIfSimulationRequest
from services.simulation.snapshot import get_snapshot_manager
from services.simulation.counterfactual import get_what_if_engine


def test_scenario_branch_independence_and_order_invariance():
    mgr = get_snapshot_manager()
    engine = get_what_if_engine()

    snapshot = mgr.create_snapshot()

    req_load20 = WhatIfSimulationRequest(
        machine_id="M03",
        scenario_type=CounterfactualScenarioType.LOAD_MODULATION,
        parameters={"load_reduction": 0.20},
        horizon_hours=4.0,
        seed=101,
        snapshot_id=snapshot.snapshot_id,
        persist=False
    )

    req_emergency = WhatIfSimulationRequest(
        machine_id="M03",
        scenario_type=CounterfactualScenarioType.EMERGENCY_STOP,
        parameters={},
        horizon_hours=4.0,
        seed=101,
        snapshot_id=snapshot.snapshot_id,
        persist=False
    )

    # Execution Order 1: Load20 first, then Emergency
    res_load20_first = engine.run_simulation(req_load20, snapshot=snapshot)
    res_emergency_second = engine.run_simulation(req_emergency, snapshot=snapshot)

    # Execution Order 2: Emergency first, then Load20 on fresh copy of same snapshot
    res_emergency_first = engine.run_simulation(req_emergency, snapshot=snapshot)
    res_load20_second = engine.run_simulation(req_load20, snapshot=snapshot)

    # Assert exact result equality regardless of execution sequence
    assert res_load20_first.result.total_output == res_load20_second.result.total_output
    assert res_load20_first.result.peak_temperature == res_load20_second.result.peak_temperature
    assert res_load20_first.result.final_rul == res_load20_second.result.final_rul

    assert res_emergency_first.result.total_output == res_emergency_second.result.total_output
    assert res_emergency_first.result.final_rul == res_emergency_second.result.final_rul
    assert res_emergency_first.result.downtime == res_emergency_second.result.downtime

    # Assert that results between different scenarios differ fundamentally
    assert res_load20_first.result.total_output > res_emergency_first.result.total_output
    assert res_emergency_first.result.downtime == 4.0
    assert res_load20_first.result.downtime == 0.0
