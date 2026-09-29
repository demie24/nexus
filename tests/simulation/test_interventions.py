"""
Tests for Minimum Counterfactual Interventions
Verifies physics behaviour, directional correctness, parameter validation, and metric outcomes
for DO_NOTHING, LOAD_MODULATION, COOLING_BOOST, SCHEDULED_SHUTDOWN, and EMERGENCY_STOP.
"""

import pytest
from services.schemas import CounterfactualScenarioType, WhatIfSimulationRequest
from services.simulation.snapshot import get_snapshot_manager
from services.simulation.counterfactual import get_what_if_engine


def test_do_nothing_baseline_trajectory():
    mgr = get_snapshot_manager()
    engine = get_what_if_engine()

    # Create degraded machine state in snapshot to observe wear evolution
    custom_states = {
        "M03": {
            "machine_id": "M03",
            "status": "OPERATING",
            "health_score": 65.0,
            "load_factor": 1.0,
            "temperature": 78.5,
            "vibration": 4.5,
            "provenance": "OBSERVED"
        }
    }
    snapshot = mgr.create_snapshot(custom_machine_states=custom_states)

    req = WhatIfSimulationRequest(
        machine_id="M03",
        scenario_type=CounterfactualScenarioType.DO_NOTHING,
        horizon_hours=4.0,
        snapshot_id=snapshot.snapshot_id,
        persist=False
    )
    resp = engine.run_simulation(req, snapshot=snapshot)

    assert resp.scenario == CounterfactualScenarioType.DO_NOTHING
    assert resp.result.health_delta <= 0.0  # Ongoing degradation reduces health
    assert resp.result.final_health < resp.result.initial_health
    assert resp.result.risk_delta >= 0.0   # Failure risk increases over time
    assert resp.result.total_output > 0.0
    assert resp.result.downtime == 0.0
    assert resp.baseline_comparison.risk_delta_percentage_points == 0.0


def test_load_modulation_20_and_40():
    mgr = get_snapshot_manager()
    engine = get_what_if_engine()

    custom_states = {
        "M03": {
            "machine_id": "M03",
            "status": "OPERATING",
            "health_score": 75.0,
            "load_factor": 1.0,
            "temperature": 55.0,
            "vibration": 3.8,
            "provenance": "OBSERVED"
        }
    }
    snapshot = mgr.create_snapshot(custom_machine_states=custom_states)

    # 1. Baseline
    req_base = WhatIfSimulationRequest(
        machine_id="M03",
        scenario_type=CounterfactualScenarioType.DO_NOTHING,
        horizon_hours=4.0,
        snapshot_id=snapshot.snapshot_id,
        persist=False
    )
    res_base = engine.run_simulation(req_base, snapshot=snapshot)

    # 2. Load -20%
    req_20 = WhatIfSimulationRequest(
        machine_id="M03",
        scenario_type=CounterfactualScenarioType.LOAD_MODULATION,
        parameters={"load_reduction": 0.20},
        horizon_hours=4.0,
        snapshot_id=snapshot.snapshot_id,
        persist=False
    )
    res_20 = engine.run_simulation(req_20, snapshot=snapshot)

    # 3. Load -40%
    req_40 = WhatIfSimulationRequest(
        machine_id="M03",
        scenario_type=CounterfactualScenarioType.LOAD_MODULATION,
        parameters={"load_reduction": 0.40},
        horizon_hours=4.0,
        snapshot_id=snapshot.snapshot_id,
        persist=False
    )
    res_40 = engine.run_simulation(req_40, snapshot=snapshot)

    # Directional physics assertions:
    # Temperature: Baseline > Load -20% >= Load -40%
    assert res_base.result.peak_temperature > res_20.result.peak_temperature
    assert res_20.result.peak_temperature >= res_40.result.peak_temperature

    # RUL: Load -40% > Load -20% > Baseline
    assert res_40.result.final_rul > res_20.result.final_rul
    assert res_20.result.final_rul > res_base.result.final_rul

    # Risk: Baseline > Load -20% > Load -40%
    assert res_base.result.final_failure_probability > res_20.result.final_failure_probability
    assert res_20.result.final_failure_probability > res_40.result.final_failure_probability

    # Throughput: Baseline > Load -20% > Load -40%
    assert res_base.result.total_output > res_20.result.total_output
    assert res_20.result.total_output > res_40.result.total_output

    # Comparison metrics:
    assert res_20.baseline_comparison.risk_delta_percentage_points < 0.0
    assert res_40.baseline_comparison.risk_delta_percentage_points < res_20.baseline_comparison.risk_delta_percentage_points
    assert res_20.baseline_comparison.throughput_loss_pct > 0.0


def test_cooling_boost():
    mgr = get_snapshot_manager()
    engine = get_what_if_engine()

    custom_states = {
        "M03": {
            "machine_id": "M03",
            "status": "OPERATING",
            "health_score": 75.0,
            "load_factor": 1.0,
            "temperature": 75.0,
            "vibration": 3.8,
            "provenance": "OBSERVED"
        }
    }
    snapshot = mgr.create_snapshot(custom_machine_states=custom_states)

    req_base = WhatIfSimulationRequest(
        machine_id="M03",
        scenario_type=CounterfactualScenarioType.DO_NOTHING,
        horizon_hours=4.0,
        snapshot_id=snapshot.snapshot_id,
        persist=False
    )
    res_base = engine.run_simulation(req_base, snapshot=snapshot)

    req_cool = WhatIfSimulationRequest(
        machine_id="M03",
        scenario_type=CounterfactualScenarioType.COOLING_BOOST,
        parameters={"cooling_multiplier": 1.50},
        horizon_hours=4.0,
        snapshot_id=snapshot.snapshot_id,
        persist=False
    )
    res_cool = engine.run_simulation(req_cool, snapshot=snapshot)

    # Cooling boost lowers temperature significantly
    assert res_cool.result.peak_temperature < res_base.result.peak_temperature
    # RUL is extended
    assert res_cool.result.final_rul > res_base.result.final_rul
    # Risk is lower
    assert res_cool.result.final_failure_probability < res_base.result.final_failure_probability
    # Output is preserved because load was not reduced
    assert abs(res_cool.result.total_output - res_base.result.total_output) < 10.0



def test_scheduled_shutdown_vs_emergency_stop():
    mgr = get_snapshot_manager()
    engine = get_what_if_engine()

    custom_states = {
        "M03": {
            "machine_id": "M03",
            "status": "OPERATING",
            "health_score": 50.0,
            "load_factor": 1.0,
            "temperature": 80.0,
            "vibration": 5.0,
            "provenance": "OBSERVED"
        }
    }
    snapshot = mgr.create_snapshot(custom_machine_states=custom_states)

    # Scheduled shutdown at 2h in a 4h horizon
    req_sched = WhatIfSimulationRequest(
        machine_id="M03",
        scenario_type=CounterfactualScenarioType.SCHEDULED_SHUTDOWN,
        parameters={"shutdown_delay_hours": 2.0},
        horizon_hours=4.0,
        snapshot_id=snapshot.snapshot_id,
        persist=False
    )
    res_sched = engine.run_simulation(req_sched, snapshot=snapshot)

    # Emergency stop immediately at 0h
    req_emerg = WhatIfSimulationRequest(
        machine_id="M03",
        scenario_type=CounterfactualScenarioType.EMERGENCY_STOP,
        parameters={},
        horizon_hours=4.0,
        snapshot_id=snapshot.snapshot_id,
        persist=False
    )
    res_emerg = engine.run_simulation(req_emerg, snapshot=snapshot)

    # Scheduled produced output during the first 2 hours
    assert res_sched.result.total_output > 0.0
    assert res_sched.result.downtime == 2.0
    assert res_sched.result.recovery_time == 1.5

    # Emergency stopped immediately: 0 output, full downtime
    assert res_emerg.result.total_output == 0.0
    assert res_emerg.result.downtime == 4.0
    assert res_emerg.result.recovery_time == 3.0


def test_invalid_parameters_controlled_error():
    engine = get_what_if_engine()

    # 1. Invalid load reduction
    bad_req_1 = WhatIfSimulationRequest(
        machine_id="M03",
        scenario_type=CounterfactualScenarioType.LOAD_MODULATION,
        parameters={"load_reduction": 1.50},  # > 1.0 invalid
        horizon_hours=4.0
    )
    with pytest.raises(ValueError, match="load_reduction must be a float between 0.0 and 1.0"):
        engine.run_simulation(bad_req_1)

    # 2. Invalid cooling multiplier
    bad_req_2 = WhatIfSimulationRequest(
        machine_id="M03",
        scenario_type=CounterfactualScenarioType.COOLING_BOOST,
        parameters={"cooling_multiplier": -0.5},  # negative invalid
        horizon_hours=4.0
    )
    with pytest.raises(ValueError, match="cooling_multiplier must be a positive number"):
        engine.run_simulation(bad_req_2)

    # 3. Invalid shutdown delay (exceeds horizon)
    bad_req_3 = WhatIfSimulationRequest(
        machine_id="M03",
        scenario_type=CounterfactualScenarioType.SCHEDULED_SHUTDOWN,
        parameters={"shutdown_delay_hours": 10.0},  # > horizon (4.0)
        horizon_hours=4.0
    )
    with pytest.raises(ValueError, match="shutdown_delay_hours must be between 0.0 and horizon"):
        engine.run_simulation(bad_req_3)

    # 4. Unregistered machine
    bad_req_4 = WhatIfSimulationRequest(
        machine_id="MACHINE_99",
        scenario_type=CounterfactualScenarioType.DO_NOTHING,
        horizon_hours=4.0
    )
    with pytest.raises(ValueError, match="not registered in the factory topology"):
        engine.run_simulation(bad_req_4)
