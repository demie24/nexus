"""
Unit Tests for Predictive Intelligence ML Models
Validates multi-horizon failure probabilities, monotonic consistency, RUL uncertainty intervals, and health forecasting.
"""

import numpy as np
import pytest

from services.prediction.config import (
    DEFAULT_HORIZONS_MINUTES,
    CRITICAL_HEALTH_THRESHOLD,
    MAX_RUL_HOURS,
    FEATURE_NAMES,
)
from services.prediction.models import (
    MultiHorizonFailureClassifier,
    RULRegressor,
    HealthTrajectoryForecaster,
)


@pytest.fixture
def synthetic_training_data():
    """Generates synthetic feature matrix and ground truths."""
    rng = np.random.default_rng(42)
    n = 150
    p = len(FEATURE_NAMES)
    X = rng.normal(size=(n, p))
    # Ensure health_current (idx 29) is in [0, 100]
    X[:, 29] = rng.uniform(10.0, 100.0, size=n)
    # Ensure health_slope (idx 30) is in [-1.0, 0.2]
    X[:, 30] = rng.uniform(-1.0, 0.2, size=n)

    # RUL is proportional to health
    y_rul = np.clip((X[:, 29] - 20.0) * 0.8, 0.0, MAX_RUL_HOURS)

    # Multi-horizon failures
    y_failure = {
        h: np.where(y_rul <= (h / 60.0), 1.0, 0.0)
        for h in DEFAULT_HORIZONS_MINUTES
    }

    # Health trajectory
    y_health = {
        h: np.clip(X[:, 29] + X[:, 30] * (h / 6.0), 0.0, 100.0)
        for h in DEFAULT_HORIZONS_MINUTES
    }

    return X, y_rul, y_failure, y_health


def test_failure_classifier_probabilities_and_monotonicity(synthetic_training_data):
    """Verify calibrated failure probabilities stay within [0, 1] and satisfy monotonic risk."""
    X, _, y_failure, _ = synthetic_training_data
    clf = MultiHorizonFailureClassifier(DEFAULT_HORIZONS_MINUTES)
    clf.fit(X, y_failure)

    probs = clf.predict_proba(X)
    assert set(probs.keys()) == set(DEFAULT_HORIZONS_MINUTES)

    for h in DEFAULT_HORIZONS_MINUTES:
        p = probs[h]
        assert np.all(p >= 0.0)
        assert np.all(p <= 1.0)

    # Monotonic risk: P(60m) <= P(120m) <= P(240m) <= P(360m)
    p60 = probs[60]
    p120 = probs[120]
    p240 = probs[240]
    p360 = probs[360]

    assert np.all(p60 <= p120 + 1e-6)
    assert np.all(p120 <= p240 + 1e-6)
    assert np.all(p240 <= p360 + 1e-6)


def test_failure_classifier_explain_factors(synthetic_training_data):
    """Verify contributing factors extraction returns valid non-empty factors."""
    X, _, y_failure, _ = synthetic_training_data
    clf = MultiHorizonFailureClassifier(DEFAULT_HORIZONS_MINUTES)
    clf.fit(X, y_failure)

    # Degraded sample
    sample = X[0].copy()
    sample[1] = 6.5   # vib_current
    sample[0] = 88.0  # temp_current
    factors = clf.explain_factors(sample, top_n=3)

    assert len(factors) <= 3
    assert len(factors) > 0
    for f in factors:
        assert "factor_name" in f
        assert "importance" in f
        assert "impact_direction" in f
        assert "description" in f
        assert 0.0 <= f["importance"] <= 1.0


def test_rul_regressor_bounds_and_zero_for_failed(synthetic_training_data):
    """Verify RUL point estimates and uncertainty bounds: 0 <= rul_lower <= rul <= rul_upper."""
    X, y_rul, _, _ = synthetic_training_data
    reg = RULRegressor()
    reg.fit(X, y_rul)

    pt, low, high = reg.predict(X)

    assert np.all(pt >= 0.0)
    assert np.all(low >= 0.0)
    assert np.all(low <= pt + 1e-5)
    assert np.all(pt <= high + 1e-5)

    # Test failed machine: health <= 20.0 must yield 0.0 RUL
    failed_sample = X[0:1].copy()
    failed_sample[0, 29] = 12.0  # health_current <= 20.0
    pt_f, low_f, high_f = reg.predict(failed_sample)
    assert pt_f[0] == 0.0
    assert low_f[0] == 0.0
    assert high_f[0] == 0.0


def test_health_forecaster_bounds(synthetic_training_data):
    """Verify health forecaster bounds predictions between 0 and 100."""
    X, _, _, y_health = synthetic_training_data
    forecaster = HealthTrajectoryForecaster(DEFAULT_HORIZONS_MINUTES)
    forecaster.fit(X, y_health)

    preds = forecaster.predict(X)
    for h in DEFAULT_HORIZONS_MINUTES:
        h_vals = preds[h]
        assert np.all(h_vals >= 0.0)
        assert np.all(h_vals <= 100.0)
