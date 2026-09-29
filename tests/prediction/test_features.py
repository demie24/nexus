"""
Unit Tests for Predictive Feature Engineering Pipeline
Validates temporal windowing, absence of forward data leakage, mathematical slopes, and feature vectors.
"""

from datetime import datetime, timezone, timedelta
import numpy as np
import pytest

from services.schemas import TelemetryCreate
from services.prediction.config import (
    FEATURE_NAMES,
    WINDOW_SIZE,
    COLD_START_MIN_SAMPLES,
)
from services.prediction.features import PredictiveFeatureExtractor


def make_frame(machine_id: str, step: int, temp: float = 68.0, vib: float = 2.4, load: float = 1.0) -> TelemetryCreate:
    return TelemetryCreate(
        machine_id=machine_id,
        timestamp=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc) + timedelta(minutes=step * 6),
        temperature=temp,
        vibration=vib,
        pressure=3.0,
        current=21.5,
        voltage=400.0,
        rpm=1500.0,
        power_kw=15.0,
        load=load,
        output_rate=80.0,
        efficiency=98.0,
    )


def test_cold_start_threshold():
    """Verify that fewer than 15 historical samples returns None without crashing."""
    extractor = PredictiveFeatureExtractor(window_size=20)
    for i in range(14):
        f = make_frame("M01", i)
        extractor.push(f, 100.0)

    assert not extractor.has_sufficient_history("M01")
    f_dict, vec = extractor.extract_features("M01")
    assert f_dict is None
    assert vec is None

    # 15th sample reaches threshold
    f_15 = make_frame("M01", 14)
    extractor.push(f_15, 100.0)
    assert extractor.has_sufficient_history("M01")

    f_dict, vec = extractor.extract_features("M01")
    assert f_dict is not None
    assert vec is not None
    assert len(vec) == len(FEATURE_NAMES)


def test_slope_calculation_mathematics():
    """Verify ordinary least squares slope computation on deterministic linear trends."""
    extractor = PredictiveFeatureExtractor()

    # Empty and single point edge cases
    assert extractor.calculate_slope([]) == 0.0
    assert extractor.calculate_slope([42.0]) == 0.0

    # Constant sequence: slope == 0
    assert extractor.calculate_slope([5.0, 5.0, 5.0, 5.0]) == 0.0

    # Linear increase: y = 2.5 * x + 10 -> slope == 2.5
    y_asc = [10.0 + 2.5 * i for i in range(10)]
    assert pytest.approx(extractor.calculate_slope(y_asc), rel=1e-5) == 2.5

    # Linear decrease: y = -1.2 * x + 100 -> slope == -1.2
    y_desc = [100.0 - 1.2 * i for i in range(10)]
    assert pytest.approx(extractor.calculate_slope(y_desc), rel=1e-5) == -1.2


def test_window_buffer_eviction():
    """Verify oldest samples are evicted once window reaches capacity."""
    extractor = PredictiveFeatureExtractor(window_size=15)
    for i in range(25):
        f = make_frame("M02", i, temp=50.0 + i)
        extractor.push(f, 100.0 - i)

    assert extractor.get_sample_count("M02") == 15
    f_dict, vec = extractor.extract_features("M02")
    # Latest temp should be 50 + 24 = 74.0
    assert f_dict["temp_current"] == 74.0
    # Window should only contain last 15 items: temps from 60 to 74 -> mean = 67.0
    assert pytest.approx(f_dict["temp_mean"], rel=1e-3) == 67.0


def test_feature_names_order_and_finiteness():
    """Verify that extracted numpy vector exactly matches FEATURE_NAMES order and has no NaN/Inf."""
    extractor = PredictiveFeatureExtractor(window_size=20)
    for i in range(16):
        f = make_frame("M03", i, temp=70.0 + i * 0.5, vib=2.0 + i * 0.1)
        extractor.push(f, 98.0 - i * 0.5)

    f_dict, vec = extractor.extract_features("M03")
    assert np.all(np.isfinite(vec))
    for idx, name in enumerate(FEATURE_NAMES):
        assert vec[idx] == f_dict[name]
