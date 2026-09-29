"""
Unit tests for RCA reproducibility and metadata persistence.
"""

from datetime import datetime, timezone
import pytest
from services.schemas import TelemetryCreate, RootCauseType
from services.diagnostics.engine import get_rca_engine


def test_rca_analysis_reproducibility():
    engine = get_rca_engine()
    t_fixed = datetime(2026, 9, 29, 12, 30, 0, tzinfo=timezone.utc)

    # Synthetic degraded telemetry window
    records = [
        TelemetryCreate(
            machine_id="M02",
            timestamp=t_fixed,
            temperature=48.0 + 0.5 * i,
            vibration=3.5 + 0.3 * i,
            current=21.0 + 0.1 * i,
            rpm=1480.0,
            power_kw=13.0,
            load=1.0,
            efficiency=90.0 - 1.2 * i,
            output_rate=45.0,
        )
        for i in range(10)
    ]
    baselines = {
        "vibration": (1.8, 0.15),
        "efficiency": (100.0, 1.5),
        "temperature": (45.0, 1.2),
        "current": (20.0, 0.8),
        "power_kw": (12.0, 0.4),
        "load": (1.0, 0.05),
    }

    # Run analysis twice with exact same parameters
    report_1 = engine.analyze_from_telemetry(
        telemetry_records=records,
        baseline_stats=baselines,
        machine_id="M02",
        analysis_timestamp=t_fixed,
    )
    report_2 = engine.analyze_from_telemetry(
        telemetry_records=records,
        baseline_stats=baselines,
        machine_id="M02",
        analysis_timestamp=t_fixed,
    )

    # Assert deterministic repeatability
    assert report_1.likely_cause == report_2.likely_cause
    assert report_1.evidence_score == report_2.evidence_score
    assert report_1.confidence == report_2.confidence
    assert len(report_1.ranking) == len(report_2.ranking)

    for c1, c2 in zip(report_1.ranking, report_2.ranking):
        assert c1.cause == c2.cause
        assert c1.evidence_score == c2.evidence_score
        assert c1.rank == c2.rank

    # Assert metadata integrity
    assert report_1.metadata_info["machine_id"] == "M02"
    assert report_1.metadata_info["input_window"] == 10
    assert "diagnostic_version" in report_1.metadata_info
    assert "rule_version" in report_1.metadata_info
