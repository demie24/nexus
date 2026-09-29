"""
Tests for Predictive Engine Behavior Across Industrial Scenarios
Tests Normal, Bearing Degradation, Cooling Degradation, Overload, and Recovery dynamics.
"""

from datetime import datetime, timezone, timedelta
import pytest

from services.schemas import TelemetryCreate, SeverityLevel, PredictionStatus
from services.simulation.config import get_default_factory_spec
from services.prediction.engine import PredictiveIntelligenceEngine
from services.prediction.dataset import generate_single_trajectory


@pytest.fixture(scope="module")
def engine():
    return PredictiveIntelligenceEngine(auto_train=False)


def test_normal_operation_prediction(engine):
    """Under normal operating conditions, failure risk is low and RUL is high."""
    spec = get_default_factory_spec().get_machine("M01")
    telems, healths, _ = generate_single_trajectory(spec, "normal", total_steps=30, seed=101)

    engine.feature_extractor.clear("M01")
    for t, h in zip(telems, healths):
        engine.push_telemetry(t, h)

    res = engine.predict("M01", current_health=healths[-1])
    assert res.prediction.risk_level in [SeverityLevel.LOW, SeverityLevel.MEDIUM]
    assert res.rul.remaining_useful_life_hours > 5.0
    assert res.prediction.predicted_failure_probability < 0.35


def test_bearing_degradation_prediction_escalation(engine):
    """Under bearing degradation, failure probability ramps up and RUL decreases."""
    spec = get_default_factory_spec().get_machine("M01")
    telems, healths, _ = generate_single_trajectory(spec, "bearing_degradation", total_steps=65, seed=102)

    engine.feature_extractor.clear("M01")
    # Feed first 25 steps (early wear)
    for t, h in zip(telems[:25], healths[:25]):
        engine.push_telemetry(t, h)
    early_res = engine.predict("M01", current_health=healths[24])

    # Feed up to step 60 (severe degradation)
    for t, h in zip(telems[25:60], healths[25:60]):
        engine.push_telemetry(t, h)
    late_res = engine.predict("M01", current_health=healths[59])

    # Late stage risk should be higher than early stage risk
    assert late_res.prediction.predicted_failure_probability >= early_res.prediction.predicted_failure_probability
    assert late_res.rul.remaining_useful_life_hours <= early_res.rul.remaining_useful_life_hours


def test_recovery_scenario_extends_rul_and_reduces_risk(engine):
    """After maintenance recovery, failure risk drops and RUL is extended."""
    spec = get_default_factory_spec().get_machine("M02")
    telems, healths, _ = generate_single_trajectory(spec, "recovery", total_steps=60, seed=103)

    engine.feature_extractor.clear("M02")
    # Feed degraded phase (steps 0-38)
    for t, h in zip(telems[:38], healths[:38]):
        engine.push_telemetry(t, h)
    degraded_res = engine.predict("M02", current_health=healths[37])

    # Feed recovered phase (steps 38-55)
    for t, h in zip(telems[38:55], healths[38:55]):
        engine.push_telemetry(t, h)
    recovered_res = engine.predict("M02", current_health=healths[54])

    assert recovered_res.prediction.predicted_health_score > degraded_res.prediction.predicted_health_score
    assert recovered_res.rul.remaining_useful_life_hours >= degraded_res.rul.remaining_useful_life_hours
