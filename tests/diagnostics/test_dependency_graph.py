"""
Unit tests for Dependency Graph representation, traversal, and alignment.
"""

import pytest
from services.schemas import RootCauseType, SignalDirection
from services.diagnostics.graph import DiagnosticDependencyGraph, get_dependency_graph


def test_dependency_graph_topology():
    graph = get_dependency_graph()
    assert graph is not None

    # Check root cause nodes exist
    for cause in [
        RootCauseType.BEARING_DEGRADATION,
        RootCauseType.COOLING_DEGRADATION,
        RootCauseType.OVERLOAD,
        RootCauseType.MOTOR_INEFFICIENCY,
        RootCauseType.SENSOR_ANOMALY,
    ]:
        assert cause.value in graph.graph.nodes
        assert graph.graph.nodes[cause.value]["type"] == "cause"

    # Check observables exist
    for obs in ["vibration", "temperature", "current", "power_kw", "load", "efficiency"]:
        assert obs in graph.graph.nodes
        assert graph.graph.nodes[obs]["type"] == "observable"


def test_reachable_observables_for_bearing():
    graph = get_dependency_graph()
    observables = graph.get_reachable_observables(RootCauseType.BEARING_DEGRADATION)

    assert "vibration" in observables
    assert observables["vibration"]["direction"] == SignalDirection.INCREASING
    assert observables["vibration"]["weight"] > 0.80

    assert "efficiency" in observables
    assert observables["efficiency"]["direction"] == SignalDirection.DECREASING


def test_explain_path():
    graph = get_dependency_graph()
    paths = graph.explain_path(RootCauseType.BEARING_DEGRADATION, "vibration")
    assert len(paths) >= 1
    assert "MechanicalFriction" in paths[0] or "friction" in paths[0].lower()


def test_graph_alignment_evaluation():
    graph = get_dependency_graph()

    # Alignment with Bearing Degradation across physical channels
    observed_bearing = {
        "vibration": (SignalDirection.INCREASING, 0.90),
        "efficiency": (SignalDirection.DECREASING, 0.80),
        "temperature": (SignalDirection.INCREASING, 0.70),
        "current": (SignalDirection.INCREASING, 0.60),
        "health_score": (SignalDirection.DECREASING, 0.85),
    }
    score_bearing, matches_bearing = graph.evaluate_graph_alignment(
        RootCauseType.BEARING_DEGRADATION, observed_bearing
    )
    assert score_bearing >= 0.70
    assert len(matches_bearing) >= 3

    # Contradictory alignment: vibration increasing but evaluated against Cooling
    score_cooling, _ = graph.evaluate_graph_alignment(
        RootCauseType.COOLING_DEGRADATION, {"vibration": (SignalDirection.INCREASING, 0.90)}
    )
    # Cooling does not have vibration as reachable observable
    assert score_cooling == 0.0
