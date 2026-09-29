"""
Unit Tests for Anomaly Classification, Fusion Engine, and Explainability
Tests SENSOR_ANOMALY vs MACHINE_BEHAVIOR distinction, weighted consensus, and evidence generation.
"""

import pytest
from services.schemas import AnomalyType, SeverityLevel
from services.anomaly.classification import AnomalyClassifier
from services.anomaly.fusion import AnomalyFusionEngine


def test_sensor_anomaly_classification():
    # Scenario: Vibration spikes sharply (Z = 5.2), but all other signals are strictly nominal (Z < 1.0)
    statistical_evidence = {
        "score": 0.85,
        "primary_metric": "vibration",
        "max_z_score": 5.2,
        "z_scores": {
            "vibration": 5.2,
            "temperature": 0.3,
            "current": 0.4,
            "power_kw": 0.2,
            "efficiency": 0.5,
            "pressure": 0.1,
            "rpm": 0.2
        },
        "triggered_signals": ["vibration"]
    }
    trend_evidence = {"score": 0.10, "trending_signals": []}
    isolation_evidence = {"score": 0.45, "is_outlier": False}
    pct_deviations = {"vibration": 150.0, "temperature": 1.2, "efficiency": -0.5}

    classification = AnomalyClassifier.classify(
        statistical_evidence=statistical_evidence,
        trend_evidence=trend_evidence,
        isolation_evidence=isolation_evidence,
        pct_deviations=pct_deviations
    )

    assert classification["type"] == AnomalyType.SENSOR_ANOMALY
    assert "Isolated sensor spike" in classification["reason"]

    # Now verify Fusion Engine dampens SENSOR_ANOMALY to avoid false critical machine failure panic
    fusion = AnomalyFusionEngine()
    result = fusion.fuse(
        statistical_evidence=statistical_evidence,
        trend_evidence=trend_evidence,
        isolation_evidence=isolation_evidence,
        classification=classification,
        pct_deviations=pct_deviations
    )

    assert result["anomaly_type"] == AnomalyType.SENSOR_ANOMALY
    # Should be capped at 0.65 (MEDIUM), NOT CRITICAL
    assert result["unified_score"] <= 0.65
    assert result["severity"] in [SeverityLevel.LOW, SeverityLevel.MEDIUM]
    assert "SENSOR_ANOMALY" in result["explanation"]


def test_machine_behavior_correlated_anomaly():
    # Scenario: Bearing wear — Vibration elevated AND efficiency drops AND temperature climbs
    statistical_evidence = {
        "score": 0.88,
        "primary_metric": "vibration",
        "max_z_score": 4.6,
        "z_scores": {
            "vibration": 4.6,
            "temperature": 3.1,
            "current": 2.8,
            "power_kw": 2.9,
            "efficiency": 3.8,
            "pressure": 0.5,
            "rpm": 1.1
        },
        "triggered_signals": ["vibration", "temperature", "efficiency", "power_kw"]
    }
    trend_evidence = {
        "score": 0.78,
        "trending_signals": ["vibration", "temperature", "efficiency"]
    }
    isolation_evidence = {
        "score": 0.82,
        "is_outlier": True
    }
    pct_deviations = {
        "vibration": 65.0,
        "temperature": 25.0,
        "efficiency": -18.0,
        "power_kw": 22.0
    }

    classification = AnomalyClassifier.classify(
        statistical_evidence=statistical_evidence,
        trend_evidence=trend_evidence,
        isolation_evidence=isolation_evidence,
        pct_deviations=pct_deviations
    )

    assert classification["type"] == AnomalyType.MACHINE_BEHAVIOR
    assert "multi-signal physical degradation" in classification["reason"]

    fusion = AnomalyFusionEngine()
    result = fusion.fuse(
        statistical_evidence=statistical_evidence,
        trend_evidence=trend_evidence,
        isolation_evidence=isolation_evidence,
        classification=classification,
        pct_deviations=pct_deviations
    )

    assert result["anomaly_type"] == AnomalyType.MACHINE_BEHAVIOR
    assert result["unified_score"] >= 0.80
    assert result["severity"] in [SeverityLevel.HIGH, SeverityLevel.CRITICAL]
    assert "MACHINE_BEHAVIOR" in result["explanation"]
    assert "Baseline Deviations" in result["explanation"]
    assert "vibration" in result["all_triggered_signals"]
    assert "efficiency" in result["all_triggered_signals"]


def test_anomaly_fusion_severity_levels():
    fusion = AnomalyFusionEngine()
    classif_normal = {"type": AnomalyType.MULTIVARIATE_ANOMALY, "reason": "Normal operations"}

    # 1. Normal
    res_norm = fusion.fuse(
        {"score": 0.1}, {"score": 0.1}, {"score": 0.1}, classif_normal, {}
    )
    assert res_norm["severity"] == SeverityLevel.NORMAL
    assert res_norm["is_anomaly"] is False

    # 2. Low
    res_low = fusion.fuse(
        {"score": 0.4}, {"score": 0.4}, {"score": 0.4}, classif_normal, {}
    )
    assert res_low["severity"] == SeverityLevel.LOW
    assert res_low["is_anomaly"] is True

    # 3. Medium
    res_med = fusion.fuse(
        {"score": 0.6}, {"score": 0.6}, {"score": 0.6}, classif_normal, {}
    )
    assert res_med["severity"] == SeverityLevel.MEDIUM

    # 4. High
    res_high = fusion.fuse(
        {"score": 0.75}, {"score": 0.75}, {"score": 0.75}, classif_normal, {}
    )
    assert res_high["severity"] == SeverityLevel.HIGH

    # 5. Critical
    res_crit = fusion.fuse(
        {"score": 0.95}, {"score": 0.90}, {"score": 0.92}, classif_normal, {}
    )
    assert res_crit["severity"] == SeverityLevel.CRITICAL
