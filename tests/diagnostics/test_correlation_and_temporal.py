"""
Unit tests for Correlation Engine, Lagged Relationships, and Temporal Reasoning.
"""

from datetime import datetime, timezone, timedelta
import numpy as np
import pytest

from services.schemas import TelemetryCreate, SignalDirection
from services.diagnostics.correlation import CorrelationEngine
from services.diagnostics.temporal import TemporalReasoningEngine


def test_spearman_and_pearson_correlation():
    # Generate perfectly positively correlated series
    x = [float(i) for i in range(10)]
    y = [float(2 * i + 1) for i in range(10)]

    corr_map = CorrelationEngine.calculate_correlations({"x": x, "y": y}, method="spearman")
    assert ("x", "y") in corr_map
    assert pytest.approx(corr_map[("x", "y")], 0.01) == 1.0


def test_lagged_cross_correlation():
    # Series A leads Series B by exactly 2 discrete ticks
    base_signal = [0.0, 0.0, 1.0, 2.0, 3.5, 5.0, 7.0, 8.5, 9.0, 9.5, 10.0, 10.0]
    leader = base_signal[:-2]
    # Follower delayed by 2 ticks
    follower = [0.0, 0.0] + leader[:-2]

    best_lag, max_corr = CorrelationEngine.calculate_lagged_cross_correlation(leader, follower, max_lag=4)
    assert best_lag == 2
    assert max_corr > 0.90


def test_ols_trend_slope():
    # Flat series -> slope 0
    flat = [5.0] * 10
    assert pytest.approx(TemporalReasoningEngine.calculate_trend_slope(flat), 0.001) == 0.0

    # Linear increase (+0.5 per step)
    increasing = [1.0 + 0.5 * i for i in range(10)]
    assert pytest.approx(TemporalReasoningEngine.calculate_trend_slope(increasing), 0.001) == 0.5


def test_temporal_dynamics_and_persistence():
    # Baseline: mean 2.0, std 0.2
    # Persistent drift: values start drifting above 3.0
    series = [2.0, 2.1, 2.0, 2.8, 3.2, 3.5, 3.9, 4.2, 4.5, 4.8]
    dyn = TemporalReasoningEngine.evaluate_signal_dynamics(series, baseline_mean=2.0, baseline_std=0.2)

    assert dyn["direction"] == SignalDirection.INCREASING
    assert dyn["is_persistent"] is True
    assert dyn["onset_idx"] == 3
    assert dyn["slope"] > 0.10


def test_no_future_temporal_leakage():
    t0 = datetime(2026, 9, 29, 12, 0, 0, tzinfo=timezone.utc)
    t_analysis = datetime(2026, 9, 29, 12, 10, 0, tzinfo=timezone.utc)

    # 15 records spaced by 1 minute: 10 past/present records, 5 future records
    records = []
    for m in range(15):
        t_rec = t0 + timedelta(minutes=m)
        records.append(TelemetryCreate(
            machine_id="M01",
            timestamp=t_rec,
            temperature=45.0,
            vibration=1.8,
            current=20.0,
            rpm=1500.0,
            power_kw=12.0,
            output_rate=50.0,
            efficiency=98.0,
        ))

    filtered = TemporalReasoningEngine.enforce_no_future_leakage(records, t_analysis)

    # Must contain exactly 11 records (0 to 10 inclusive), none beyond 12:10:00
    assert len(filtered) == 11
    assert max(r.timestamp for r in filtered) <= t_analysis
    for r in filtered:
        assert r.timestamp <= t_analysis
