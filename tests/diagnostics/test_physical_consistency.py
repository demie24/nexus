"""
Unit tests for Physical Consistency Checks based on thermodynamic and mechanical couplings.
"""

import pytest
from services.schemas import RootCauseType, PhysicalConsistencyStatus, SignalDirection
from services.diagnostics.physical_consistency import PhysicalConsistencyChecker


def test_bearing_physical_consistency():
    baseline = {"vibration": 1.8, "efficiency": 100.0, "load": 1.0}
    dynamics = {
        "vibration": {"is_persistent": True, "direction": SignalDirection.INCREASING},
        "efficiency": {"is_persistent": True, "direction": SignalDirection.DECREASING},
    }

    # Consistent bearing degradation
    observed_consistent = {"vibration": 4.5, "efficiency": 82.0, "load": 1.0}
    status, score, reasons = PhysicalConsistencyChecker.check_consistency(
        RootCauseType.BEARING_DEGRADATION, observed_consistent, baseline, dynamics
    )
    assert status == PhysicalConsistencyStatus.CONSISTENT
    assert score >= 0.70

    # Inconsistent: vibration is nominal
    observed_inconsistent = {"vibration": 1.82, "efficiency": 99.0, "load": 1.0}
    status_bad, score_bad, _ = PhysicalConsistencyChecker.check_consistency(
        RootCauseType.BEARING_DEGRADATION, observed_inconsistent, baseline, dynamics
    )
    assert status_bad == PhysicalConsistencyStatus.INCONSISTENT
    assert score_bad < 0.30


def test_cooling_physical_consistency():
    baseline = {"temperature": 45.0, "efficiency": 100.0, "load": 1.0, "vibration": 1.8}
    dynamics = {
        "temperature": {"is_persistent": True, "direction": SignalDirection.INCREASING, "slope": 0.15},
        "efficiency": {"direction": SignalDirection.DECREASING},
    }

    # High temperature while load is nominal
    observed_cooling = {"temperature": 68.0, "efficiency": 85.0, "load": 1.0, "vibration": 1.85}
    status, score, _ = PhysicalConsistencyChecker.check_consistency(
        RootCauseType.COOLING_DEGRADATION, observed_cooling, baseline, dynamics
    )
    assert status == PhysicalConsistencyStatus.CONSISTENT
    assert score >= 0.70


def test_overload_physical_consistency():
    baseline = {"load": 1.0, "current": 20.0, "power_kw": 12.0, "temperature": 45.0}
    dynamics = {
        "load": {"direction": SignalDirection.INCREASING},
        "current": {"direction": SignalDirection.INCREASING},
        "power_kw": {"direction": SignalDirection.INCREASING},
    }

    # Consistent overload
    observed_overload = {"load": 1.38, "current": 27.8, "power_kw": 16.5, "temperature": 52.0}
    status, score, _ = PhysicalConsistencyChecker.check_consistency(
        RootCauseType.OVERLOAD, observed_overload, baseline, dynamics
    )
    assert status == PhysicalConsistencyStatus.CONSISTENT
    assert score >= 0.70


def test_sensor_anomaly_physical_consistency():
    baseline = {"vibration": 1.8, "temperature": 45.0, "current": 20.0, "power_kw": 12.0, "efficiency": 100.0}
    dynamics = {
        "vibration": {"is_spike": True, "net_dev_z": 7.5},
        "temperature": {"net_dev_z": 0.1},
        "current": {"net_dev_z": 0.2},
        "power_kw": {"net_dev_z": 0.1},
        "efficiency": {"net_dev_z": -0.2},
    }

    observed = {"vibration": 9.2, "temperature": 45.2, "current": 20.1, "power_kw": 12.1, "efficiency": 99.8}
    status, score, reasons = PhysicalConsistencyChecker.check_consistency(
        RootCauseType.SENSOR_ANOMALY, observed, baseline, dynamics, anomaly_classifier_type="SENSOR_ANOMALY"
    )
    assert status == PhysicalConsistencyStatus.CONSISTENT
    assert score >= 0.80
