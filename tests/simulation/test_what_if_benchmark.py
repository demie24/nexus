"""
Performance Benchmarks for What-If Counterfactual Simulation Engine
Verifies that single-machine 4-hour simulations execute with P95 < 500ms,
and benchmarks multi-scenario 8-hour simulations.
"""

import time
import numpy as np
import pytest

from services.schemas import CounterfactualScenarioType, WhatIfSimulationRequest, ScenarioCompareRequest
from services.simulation.snapshot import get_snapshot_manager
from services.simulation.counterfactual import get_what_if_engine
from services.simulation.comparison import get_comparison_engine


def test_single_machine_4h_p95_latency():
    mgr = get_snapshot_manager()
    engine = get_what_if_engine()

    snapshot = mgr.create_snapshot()
    req = WhatIfSimulationRequest(
        machine_id="M03",
        scenario_type=CounterfactualScenarioType.LOAD_MODULATION,
        parameters={"load_reduction": 0.20},
        horizon_hours=4.0,
        snapshot_id=snapshot.snapshot_id,
        persist=False
    )

    # Warm-up run
    engine.run_simulation(req, snapshot=snapshot)

    # Benchmark 50 runs
    latencies_ms = []
    for _ in range(50):
        t0 = time.perf_counter()
        engine.run_simulation(req, snapshot=snapshot)
        elapsed = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(elapsed)

    p50 = np.percentile(latencies_ms, 50)
    p95 = np.percentile(latencies_ms, 95)
    mean_lat = np.mean(latencies_ms)

    print(f"\nWhat-If 4h Simulation Benchmark (50 runs): Mean={mean_lat:.2f}ms | P50={p50:.2f}ms | P95={p95:.2f}ms")

    # Strict SLA Assertion: P95 < 500 ms
    assert p95 < 500.0, f"P95 latency {p95:.2f}ms exceeded SLA threshold of 500ms"


def test_multi_scenario_8h_comparison_benchmark():
    mgr = get_snapshot_manager()
    comp_engine = get_comparison_engine()

    snapshot = mgr.create_snapshot()
    req = ScenarioCompareRequest(
        machine_id="M03",
        horizon_hours=8.0,
        snapshot_id=snapshot.snapshot_id,
        persist=False
    )

    # Run comparison suite (runs DO_NOTHING, Load -20%, Load -40%, Cooling Boost, Emergency Stop)
    t0 = time.perf_counter()
    resp = comp_engine.compare(req)
    total_time_ms = (time.perf_counter() - t0) * 1000.0

    print(f"\nMulti-Scenario 8h Comparison Suite (5 scenarios): Total={total_time_ms:.2f}ms")

    assert len(resp.scenarios) == 5
    assert len(resp.matrix) == 5
    assert total_time_ms < 2000.0  # Entire 5-scenario 8h suite in < 2 seconds
