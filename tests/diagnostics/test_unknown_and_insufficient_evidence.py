"""
Unit tests for UNKNOWN / Insufficient Evidence Fallback.
"""

from datetime import datetime, timezone
import pytest
from services.schemas import (
    RootCauseType,
    SignalDirection,
    PhysicalConsistencyStatus,
    TelemetryCreate,
)
from services.diagnostics.engine import get_rca_engine
from services.diagnostics.fusion import EvidenceFusionEngine
from services.diagnostics.graph import get_dependency_graph


def test_nominal_telemetry_returns_unknown():
    engine = get_rca_engine()

    # Completely normal, nominal telemetry
    t0 = datetime(2026, 9, 29, 12, 0, 0, tzinfo=timezone.utc)
    records = [
        TelemetryCreate(
            machine_id="M01",
            timestamp=t0,
            temperature=45.0 + 0.1 * i,
            vibration=1.8 + 0.01 * (i % 2),
            current=20.0,
            rpm=1500.0,
            power_kw=12.0,
            load=1.0,
            efficiency=100.0,
            output_rate=50.0,
        )
        for i in range(10)
    ]
    baselines = {
        "temperature": (45.0, 1.2),
        "vibration": (1.8, 0.15),
        "current": (20.0, 0.8),
        "load": (1.0, 0.05),
        "efficiency": (100.0, 1.5),
        "power_kw": (12.0, 0.4),
    }

    report = engine.analyze_from_telemetry(records, baselines, machine_id="M01")

    assert report.likely_cause == RootCauseType.UNKNOWN
    assert report.confidence == "LOW"
    assert report.ranking[0].cause == RootCauseType.UNKNOWN
    assert "insufficient" in report.ranking[0].summary.lower() or "ambiguous" in report.ranking[0].summary.lower()


def test_insufficient_records_cold_start():
    engine = get_rca_engine()
    t0 = datetime(2026, 9, 29, 12, 0, 0, tzinfo=timezone.utc)

    # Only 2 records (less than minimum 3 required)
    records = [
        TelemetryCreate(
            machine_id="M01",
            timestamp=t0,
            temperature=45.0,
            vibration=1.8,
            current=20.0,
            rpm=1500.0,
            power_kw=12.0,
            load=1.0,
            efficiency=100.0,
            output_rate=50.0,
        )
        for _ in range(2)
    ]
    baselines = {"temperature": (45.0, 1.2), "vibration": (1.8, 0.15)}

    report = engine.analyze_from_telemetry(records, baselines, machine_id="M01")

    assert report.likely_cause == RootCauseType.UNKNOWN
    assert report.confidence == "LOW"
    assert "insufficient" in report.ranking[0].summary.lower()


def test_contradictory_evidence_falls_back():
    graph = get_dependency_graph()
    fusion = EvidenceFusionEngine(graph)

    # Conflicting noise with no clear pattern
    observed = {"vibration": 1.7, "efficiency": 101.0, "temperature": 44.5, "current": 19.8, "load": 0.98}
    baselines = {
        "vibration": (1.8, 0.15),
        "efficiency": (100.0, 1.5),
        "temperature": (45.0, 1.2),
        "current": (20.0, 0.8),
        "load": (1.0, 0.05),
    }
    dynamics = {k: {"direction": SignalDirection.STABLE, "is_persistent": False} for k in observed}

    likely_cause, top_score, confidence, ranking, _ = fusion.fuse_evidence(observed, baselines, dynamics)

    assert likely_cause == RootCauseType.UNKNOWN
    assert confidence == "LOW"
