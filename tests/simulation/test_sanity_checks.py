"""
Tests for Physical Sanity Checks and Boundary Enforcement
Verifies that impossible physics trigger controlled errors rather than silent clamping.
"""

import pytest
from services.schemas import OutcomeMetrics
from services.simulation.metrics import validate_metrics_sanity, SimulationSanityError


def test_temperature_below_ambient_triggers_error():
    bad_metrics = OutcomeMetrics(
        initial_health=100.0,
        final_health=95.0,
        health_delta=-5.0,
        initial_failure_probability=0.01,
        final_failure_probability=0.05,
        risk_delta=0.04,
        initial_rul=40.0,
        final_rul=36.0,
        rul_delta=-4.0,
        peak_temperature=5.0,  # Below physical ambient threshold (15C)
        peak_vibration=2.0,
        total_output=300.0,
        throughput_loss=0.05
    )
    with pytest.raises(SimulationSanityError, match="below ambient minimum"):
        validate_metrics_sanity(bad_metrics)


def test_negative_output_triggers_error():
    bad_metrics = OutcomeMetrics(
        initial_health=100.0,
        final_health=95.0,
        health_delta=-5.0,
        initial_failure_probability=0.01,
        final_failure_probability=0.05,
        risk_delta=0.04,
        peak_temperature=65.0,
        peak_vibration=2.0,
        total_output=-50.0,  # Negative output
        throughput_loss=0.0
    )
    with pytest.raises(SimulationSanityError, match="Negative production output"):
        validate_metrics_sanity(bad_metrics)


def test_invalid_failure_probability_triggers_error():
    bad_metrics = OutcomeMetrics(
        initial_health=100.0,
        final_health=95.0,
        health_delta=-5.0,
        initial_failure_probability=1.5,  # > 1.0
        final_failure_probability=0.05,
        risk_delta=-1.45,
        peak_temperature=65.0,
        peak_vibration=2.0,
        total_output=200.0,
        throughput_loss=0.0
    )
    with pytest.raises(SimulationSanityError, match="out of probability bounds"):
        validate_metrics_sanity(bad_metrics)
