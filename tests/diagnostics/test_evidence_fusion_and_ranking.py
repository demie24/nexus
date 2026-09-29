"""
Unit tests for Evidence Fusion, Ranking, Confidence Levels, and Multi-Signal Reasoning.
"""

import pytest
from services.schemas import (
    RootCauseType,
    SignalDirection,
    PhysicalConsistencyStatus,
)
from services.diagnostics.graph import get_dependency_graph
from services.diagnostics.fusion import EvidenceFusionEngine


@pytest.fixture
def fusion_engine():
    graph = get_dependency_graph()
    return EvidenceFusionEngine(graph)


def test_bearing_degradation_fusion(fusion_engine):
    # Simultaneous vibration rise, efficiency decline, and temperature rise
    observed = {"vibration": 5.2, "efficiency": 78.0, "temperature": 52.0, "current": 21.5, "load": 1.0}
    baselines = {
        "vibration": (1.8, 0.15),
        "efficiency": (100.0, 1.5),
        "temperature": (45.0, 1.2),
        "current": (20.0, 0.8),
        "load": (1.0, 0.05),
        "power_kw": (12.0, 0.4),
    }
    dynamics = {
        "vibration": {"direction": SignalDirection.INCREASING, "is_persistent": True, "persistence": 0.8},
        "efficiency": {"direction": SignalDirection.DECREASING, "is_persistent": True, "persistence": 0.7},
        "temperature": {"direction": SignalDirection.INCREASING, "is_persistent": True, "persistence": 0.6},
        "current": {"direction": SignalDirection.INCREASING, "is_persistent": False, "persistence": 0.3},
        "load": {"direction": SignalDirection.STABLE, "is_persistent": False, "persistence": 0.0},
    }

    likely_cause, top_score, confidence, ranking, evidence = fusion_engine.fuse_evidence(
        observed, baselines, dynamics
    )

    assert likely_cause == RootCauseType.BEARING_DEGRADATION
    assert top_score >= 0.70
    assert confidence in ["HIGH", "MEDIUM"]
    assert ranking[0].cause == RootCauseType.BEARING_DEGRADATION
    assert ranking[0].rank == 1
    assert len(evidence) >= 2


def test_sensor_anomaly_suppresses_physical_causes(fusion_engine):
    # Vibration spikes to 8.5 but ALL other signals are normal
    observed = {"vibration": 8.5, "efficiency": 99.8, "temperature": 45.1, "current": 20.0, "load": 1.0, "power_kw": 12.0}
    baselines = {
        "vibration": (1.8, 0.15),
        "efficiency": (100.0, 1.5),
        "temperature": (45.0, 1.2),
        "current": (20.0, 0.8),
        "load": (1.0, 0.05),
        "power_kw": (12.0, 0.4),
    }
    dynamics = {
        "vibration": {"direction": SignalDirection.SPIKE, "is_spike": True, "is_persistent": False, "net_dev_z": 8.0},
        "efficiency": {"direction": SignalDirection.STABLE, "is_persistent": False, "net_dev_z": 0.1},
        "temperature": {"direction": SignalDirection.STABLE, "is_persistent": False, "net_dev_z": 0.0},
        "current": {"direction": SignalDirection.STABLE, "is_persistent": False, "net_dev_z": 0.0},
        "load": {"direction": SignalDirection.STABLE, "is_persistent": False, "net_dev_z": 0.0},
        "power_kw": {"direction": SignalDirection.STABLE, "is_persistent": False, "net_dev_z": 0.0},
    }
    anomaly_context = {"anomaly_type": "SENSOR_ANOMALY", "triggered_signals": ["vibration"]}

    likely_cause, top_score, confidence, ranking, _ = fusion_engine.fuse_evidence(
        observed, baselines, dynamics, anomaly_context=anomaly_context
    )

    assert likely_cause == RootCauseType.SENSOR_ANOMALY
    assert top_score >= 0.75
    # Bearing degradation must be penalized because coupled signals are nominal and sensor classifier triggered
    bearing_cand = next((c for c in ranking if c.cause == RootCauseType.BEARING_DEGRADATION), None)
    assert bearing_cand is not None
    assert bearing_cand.evidence_score < 0.45


def test_multi_signal_reasoning_vs_single_signal(fusion_engine):
    # Single signal deviation without coupled physical degradation
    observed = {"vibration": 2.8, "efficiency": 99.5, "temperature": 45.0, "current": 20.0, "load": 1.0}
    baselines = {
        "vibration": (1.8, 0.15),
        "efficiency": (100.0, 1.5),
        "temperature": (45.0, 1.2),
        "current": (20.0, 0.8),
        "load": (1.0, 0.05),
    }
    dynamics = {
        "vibration": {"direction": SignalDirection.INCREASING, "is_persistent": False},
        "efficiency": {"direction": SignalDirection.STABLE, "is_persistent": False},
        "temperature": {"direction": SignalDirection.STABLE, "is_persistent": False},
        "current": {"direction": SignalDirection.STABLE, "is_persistent": False},
        "load": {"direction": SignalDirection.STABLE, "is_persistent": False},
    }

    likely_cause, top_score, confidence, ranking, _ = fusion_engine.fuse_evidence(
        observed, baselines, dynamics
    )

    # Isolated moderate vibration without efficiency decline is not enough for confident bearing degradation
    bearing_cand = next((c for c in ranking if c.cause == RootCauseType.BEARING_DEGRADATION), None)
    assert bearing_cand is not None
    assert bearing_cand.confidence != "HIGH"
