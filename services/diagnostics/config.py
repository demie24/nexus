"""
NEXUS Root Cause Analysis (RCA) Configuration & Cause Taxonomy
Defines candidate root causes, expected physical couplings, evidence fusion weights,
and confidence thresholds. Extensible via configuration without altering core engine.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from services.schemas import RootCauseType, SignalDirection


# Software & Diagnostic Versions for Provenance & Reproducibility
DIAGNOSTIC_VERSION = "v1.0.0"
RULE_VERSION = "v1.0.0"
FEATURE_VERSION = "v1.0.0"
MODEL_VERSION = "v1.0.0"

# Evidence Fusion Weight Distribution (Sums to 1.00)
WEIGHT_OBSERVED: float = 0.30
WEIGHT_GRAPH: float = 0.20
WEIGHT_PHYSICAL: float = 0.25
WEIGHT_TEMPORAL: float = 0.15
WEIGHT_MODEL: float = 0.10

# Decision & Confidence Thresholds
MIN_EVIDENCE_THRESHOLD: float = 0.35        # Below this score, defaults to UNKNOWN
CONFIDENCE_HIGH_THRESHOLD: float = 0.70     # Score needed for HIGH confidence
CONFIDENCE_HIGH_MARGIN: float = 0.15        # Score difference between Rank 1 and Rank 2 for HIGH
CONFIDENCE_MEDIUM_THRESHOLD: float = 0.45   # Score needed for MEDIUM confidence


@dataclass
class CauseDefinition:
    cause: RootCauseType
    name: str
    description: str
    expected_signals: Dict[str, SignalDirection]
    primary_signals: List[str]
    signal_weights: Dict[str, float]
    base_prior: float = 0.10
    contraindicated_conditions: List[str] = field(default_factory=list)


# Registry of Supported Candidate Causes (Extensible without altering core logic)
CAUSE_TAXONOMY: Dict[RootCauseType, CauseDefinition] = {
    RootCauseType.BEARING_DEGRADATION: CauseDefinition(
        cause=RootCauseType.BEARING_DEGRADATION,
        name="Bearing Degradation",
        description="Progressive mechanical wear, raceway spalling, or lubrication failure in rotating bearings.",
        expected_signals={
            "vibration": SignalDirection.INCREASING,
            "efficiency": SignalDirection.DECREASING,
            "temperature": SignalDirection.INCREASING,
            "current": SignalDirection.INCREASING,
        },
        primary_signals=["vibration", "efficiency"],
        signal_weights={
            "vibration": 0.45,
            "efficiency": 0.25,
            "temperature": 0.15,
            "current": 0.15,
        },
        base_prior=0.20,
    ),
    RootCauseType.COOLING_DEGRADATION: CauseDefinition(
        cause=RootCauseType.COOLING_DEGRADATION,
        name="Cooling Degradation",
        description="Heat exchanger clogging, coolant flow restriction, or radiator fan failure.",
        expected_signals={
            "temperature": SignalDirection.INCREASING,
            "efficiency": SignalDirection.DECREASING,
        },
        primary_signals=["temperature", "efficiency"],
        signal_weights={
            "temperature": 0.55,
            "efficiency": 0.30,
            "vibration": 0.15,  # Expected normal or minor drift
        },
        base_prior=0.20,
    ),
    RootCauseType.OVERLOAD: CauseDefinition(
        cause=RootCauseType.OVERLOAD,
        name="Operational Overload",
        description="Machine operated beyond rated capacity, excessive mechanical demand, or feed rate overload.",
        expected_signals={
            "load": SignalDirection.INCREASING,
            "current": SignalDirection.INCREASING,
            "power_kw": SignalDirection.INCREASING,
            "temperature": SignalDirection.INCREASING,
            "efficiency": SignalDirection.DECREASING,
        },
        primary_signals=["load", "current", "power_kw"],
        signal_weights={
            "load": 0.35,
            "current": 0.25,
            "power_kw": 0.25,
            "temperature": 0.15,
        },
        base_prior=0.20,
    ),
    RootCauseType.MOTOR_INEFFICIENCY: CauseDefinition(
        cause=RootCauseType.MOTOR_INEFFICIENCY,
        name="Motor Inefficiency",
        description="Stator winding degradation, core loss, electrical unbalance, or severe power loss.",
        expected_signals={
            "efficiency": SignalDirection.DECREASING,
            "power_kw": SignalDirection.INCREASING,
            "current": SignalDirection.INCREASING,
            "temperature": SignalDirection.INCREASING,
        },
        primary_signals=["efficiency", "power_kw"],
        signal_weights={
            "efficiency": 0.40,
            "power_kw": 0.30,
            "current": 0.20,
            "temperature": 0.10,
        },
        base_prior=0.15,
    ),
    RootCauseType.SENSOR_ANOMALY: CauseDefinition(
        cause=RootCauseType.SENSOR_ANOMALY,
        name="Sensor Anomaly",
        description="Transducer glitch, intermittent wiring, calibration drift, or isolated telemetry artifact.",
        expected_signals={
            # Evaluated dynamically based on isolated single-channel spike
        },
        primary_signals=[],
        signal_weights={},
        base_prior=0.15,
    ),
    RootCauseType.UNKNOWN: CauseDefinition(
        cause=RootCauseType.UNKNOWN,
        name="Unknown / Insufficient Evidence",
        description="Telemetry observations are contradictory, noisy, or lack sufficient statistical evidence.",
        expected_signals={},
        primary_signals=[],
        signal_weights={},
        base_prior=0.10,
    ),
}
