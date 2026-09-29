"""
Performance Benchmark for DecisionEngine
Measures execution latency across multiple iterations and verifies that
P95 response time strictly satisfies the SLA requirement (< 200 ms).
"""

import time
import numpy as np
import pytest
from services.schemas import DecisionAnalysisRequest, PolicyProfileType
from services.decision.engine import get_decision_engine


def test_decision_engine_p95_latency_benchmark():
    engine = get_decision_engine()
    latencies_ms = []

    # Warm-up run
    warmup_req = DecisionAnalysisRequest(
        machine_id="M01",
        policy_profile=PolicyProfileType.BALANCED,
        horizon_hours=2.0,
        persist=False,
    )
    engine.analyze(request=warmup_req)

    # Benchmark runs (15 iterations)
    iterations = 15
    for i in range(iterations):
        machine_id = f"M0{(i % 4) + 1}"
        req = DecisionAnalysisRequest(
            machine_id=machine_id,
            policy_profile=PolicyProfileType.BALANCED,
            horizon_hours=2.0,
            persist=False,
        )
        t_start = time.perf_counter()
        engine.analyze(request=req)
        t_end = time.perf_counter()
        latencies_ms.append((t_end - t_start) * 1000.0)

    p50 = float(np.percentile(latencies_ms, 50))
    p95 = float(np.percentile(latencies_ms, 95))
    max_lat = float(np.max(latencies_ms))

    print(f"\n[BENCHMARK] DecisionEngine Latency: P50={p50:.2f}ms, P95={p95:.2f}ms, Max={max_lat:.2f}ms")

    # Strict SLA check: P95 < 200ms
    assert p95 < 200.0, f"P95 latency {p95:.2f}ms exceeds 200ms threshold."
