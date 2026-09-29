"""
Unit Tests for NEXUS Anomaly Detectors
Covers Statistical Z-Score Detector, Rolling Trend Detector, and Isolation Forest Unsupervised Detector.
"""

from datetime import datetime, timezone
import pytest
import numpy as np

from services.schemas import TelemetryCreate, DataProvenance
from services.anomaly.baseline import MachineBaseline
from services.anomaly.features import AnomalyFeatureExtractor
from services.anomaly.detectors import (
    StatisticalAnomalyDetector,
    RollingTrendDetector,
    IsolationForestDetector,
)


@pytest.fixture
def baseline():
    b = MachineBaseline("M01")
    # Simulate 15 nominal readings to establish baseline
    now = datetime.now(timezone.utc)
    for _ in range(15):
        t = TelemetryCreate(
            machine_id="M01",
            timestamp=now,
            temperature=65.0,
            vibration=2.2,
            pressure=2.5,
            current=12.0,
            voltage=400.0,
            rpm=1500.0,
            power_kw=15.0,
            load=1.0,
            output_rate=85.0,
            efficiency=96.0,
            provenance=DataProvenance.OBSERVED
        )
        b.update(t)
    return b


@pytest.fixture
def extractor():
    return AnomalyFeatureExtractor(window_size=15)


def test_statistical_detector_nominal(baseline, extractor):
    detector = StatisticalAnomalyDetector()
    now = datetime.now(timezone.utc)
    tel = TelemetryCreate(
        machine_id="M01",
        timestamp=now,
        temperature=65.2,
        vibration=2.25,
        pressure=2.5,
        current=12.1,
        voltage=400.0,
        rpm=1500.0,
        power_kw=15.1,
        load=1.0,
        output_rate=85.0,
        efficiency=96.0,
        provenance=DataProvenance.OBSERVED
    )
    features = extractor.extract_features(tel, baseline)
    evidence = detector.detect(tel, features, baseline)

    assert evidence["detector"] == "statistical_zscore"
    assert evidence["score"] < 0.25
    assert len(evidence["triggered_signals"]) == 0
    assert evidence["max_z_score"] < 2.0


def test_statistical_detector_outlier_trigger(baseline, extractor):
    detector = StatisticalAnomalyDetector()
    now = datetime.now(timezone.utc)
    # Severe thermal outlier (temperature 95°C vs baseline 65°C, std ~3.5 -> Z ~ 8.5)
    tel = TelemetryCreate(
        machine_id="M01",
        timestamp=now,
        temperature=95.0,
        vibration=2.2,
        pressure=2.5,
        current=12.0,
        voltage=400.0,
        rpm=1500.0,
        power_kw=15.0,
        load=1.0,
        output_rate=85.0,
        efficiency=96.0,
        provenance=DataProvenance.OBSERVED
    )
    features = extractor.extract_features(tel, baseline)
    evidence = detector.detect(tel, features, baseline)

    assert evidence["score"] >= 0.85
    assert "temperature" in evidence["triggered_signals"]
    assert evidence["primary_metric"] == "temperature"
    assert evidence["max_z_score"] > 4.0


def test_rolling_trend_detector_stable(extractor):
    detector = RollingTrendDetector()
    now = datetime.now(timezone.utc)
    extractor.clear("M01")

    # Feed 8 stable frames
    for i in range(8):
        t = TelemetryCreate(
            machine_id="M01",
            timestamp=now,
            temperature=65.0 + (i % 2) * 0.1,
            vibration=2.2,
            pressure=2.5,
            current=12.0,
            rpm=1500.0,
            power_kw=15.0,
            output_rate=85.0,
            efficiency=96.0
        )
        extractor.push_telemetry(t)

    latest = t
    features = extractor.extract_features(latest)
    evidence = detector.detect(latest, features)

    assert evidence["score"] < 0.20
    assert len(evidence["trending_signals"]) == 0


def test_rolling_trend_detector_rising_temperature_drift(extractor):
    detector = RollingTrendDetector()
    now = datetime.now(timezone.utc)
    extractor.clear("M01")

    # Feed 8 frames with a steep temperature climb: 60 -> 64 -> 68 -> 72 -> 76 -> 80 -> 84 -> 88
    for i in range(8):
        t = TelemetryCreate(
            machine_id="M01",
            timestamp=now,
            temperature=60.0 + i * 4.0,  # Slope = +4.0 deg/tick!
            vibration=2.2,
            pressure=2.5,
            current=12.0,
            rpm=1500.0,
            power_kw=15.0,
            output_rate=85.0,
            efficiency=96.0
        )
        extractor.push_telemetry(t)

    features = extractor.extract_features(t)
    evidence = detector.detect(t, features)

    assert evidence["score"] >= 0.60
    assert "temperature" in evidence["trending_signals"]
    assert evidence["slopes"]["temperature"] > 0.20
    assert evidence["streaks"]["temperature"] >= 4


def test_isolation_forest_detector_inlier_and_outlier(extractor):
    detector = IsolationForestDetector()
    now = datetime.now(timezone.utc)

    # 1. Normal inlier telemetry
    normal_tel = TelemetryCreate(
        machine_id="M01",
        timestamp=now,
        temperature=65.0,
        vibration=2.2,
        pressure=2.5,
        current=12.0,
        voltage=400.0,
        rpm=1500.0,
        power_kw=15.0,
        load=1.0,
        efficiency=96.0,
        output_rate=85.0
    )
    features_normal = extractor.extract_features(normal_tel)
    evidence_normal = detector.detect(features_normal)

    assert evidence_normal["detector"] == "isolation_forest"
    assert evidence_normal["score"] < 0.40
    assert evidence_normal["is_outlier"] is False
    assert evidence_normal["model_version"] == "v1.0.0"

    # 2. Catastrophic outlier (extreme vibration 15.0, temperature 140, current 80, efficiency 30)
    outlier_tel = TelemetryCreate(
        machine_id="M01",
        timestamp=now,
        temperature=140.0,
        vibration=15.0,
        pressure=6.0,
        current=80.0,
        voltage=400.0,
        rpm=1800.0,
        power_kw=45.0,
        load=2.0,
        efficiency=30.0,
        output_rate=20.0
    )
    features_outlier = extractor.extract_features(outlier_tel)
    evidence_outlier = detector.detect(features_outlier)

    assert evidence_outlier["score"] >= 0.70
    assert evidence_outlier["is_outlier"] is True
