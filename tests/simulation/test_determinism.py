"""
Tests for Determinism and Reproducibility in Counterfactual Simulation
Verifies that identical snapshot + scenario + parameters + seed produces bitwise/numerical identical outputs.
"""

import pytest
from services.schemas import CounterfactualScenarioType, WhatIfSimulationRequest
from services.simulation.snapshot import get_snapshot_manager
from services.simulation.counterfactual import get_what_if_engine


def test_exact_determinism_across_replays():
    mgr = get_snapshot_manager()
    engine = get_what_if_engine()

    snapshot = mgr.create_snapshot()

    req = WhatIfSimulationRequest(
        machine_id="M01",
        scenario_type=CounterfactualScenarioType.LOAD_MODULATION,
        parameters={"load_reduction": 0.25},
        horizon_hours=4.0,
        seed=42,
        snapshot_id=snapshot.snapshot_id,
        persist=False
    )

    # Run 5 independent replays
    runs = [engine.run_simulation(req, snapshot=snapshot) for _ in range(5)]

    first = runs[0]
    for other in runs[1:]:
        assert first.result.initial_health == other.result.initial_health
        assert first.result.final_health == other.result.final_health
        assert first.result.peak_temperature == other.result.peak_temperature
        assert first.result.peak_vibration == other.result.peak_vibration
        assert first.result.total_output == other.result.total_output
        assert first.result.final_rul == other.result.final_rul
        assert first.result.final_failure_probability == other.result.final_failure_probability
        assert first.metadata_info["state_hash"] == other.metadata_info["state_hash"]
        assert first.metadata_info["random_seed"] == other.metadata_info["random_seed"]
