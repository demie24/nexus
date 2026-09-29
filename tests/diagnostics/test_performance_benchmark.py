"""
Performance and Latency Benchmarks for RCA Engine
Verifies that complete RCA analysis and constituent modules execute within P95 < 300ms.
"""

from datetime import datetime, timezone
import time
import numpy as np
import pytest

from services.schemas import TelemetryCreate
from services.diagnostics.engine import get_rca_engine


def test_rca_engine_p95_latency():
    engine = get_rca_engine()
    t0 = datetime(2026, 9, 29, 12, 0, 0, tzinfo=timezone.utc)

    # 30-tick telemetry window
    records = [
        TelemetryCreate(
            machine_id="M01",
            timestamp=t0,
            temperature=45.0 + 0.5 * (i % 5),
            vibration=2.5 + 0.1 * (i % 4),
            current=21.0,
            rpm=1490.0,
            power_kw=12.5,
            load=1.0,
            efficiency=92.0 - 0.5 * (i % 3),
            output_rate=48.0,
        )
        for i in range(30)
    ]
    baselines = {
        "temperature": (45.0, 1.2),
        "vibration": (1.8, 0.15),
        "current": (20.0, 0.8),
        "power_kw": (12.0, 0.4),
        "load": (1.0, 0.05),
        "efficiency": (100.0, 1.5),
        "pressure": (2.5, 0.1),
        "rpm": (1500.0, 15.0),
    }

    # Warm-up run
    engine.analyze_from_telemetry(records, baselines, machine_id="M01")

    # Benchmark 50 consecutive runs
    latencies_ms = []
    for _ in range(50):
        t_start = time.perf_counter()
        engine.analyze_from_telemetry(records, baselines, machine_id="M01")
        t_elapsed = (time.perf_counter() - t_start) * 1000.0
        latencies_ms.append(t_elapsed)

    p50 = np.percentile(latencies_ms, 50)
    p95 = np.percentile(latencies_ms, 95)
    mean_lat = np.mean(latencies_ms)

    print(f"\nRCA Benchmark (50 runs): Mean={mean_lat:.2f}ms | P50={p50:.2f}ms | P95={p95:.2f}ms")

    # Strict SLA Assertion: P95 < 300 ms (Requirement 23)
    assert p95 < 300.0, f"P95 latency {p95:.2f}ms exceeded SLA threshold of 300ms"
