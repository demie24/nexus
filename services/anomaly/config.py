"""
NEXUS Anomaly Detection Engine Configuration
Centralizes detector thresholds, fusion weights, severity boundaries, and lifecycle parameters.
All parameters are configuration-driven and explainable.
"""

from typing import Dict, List
from pydantic import BaseModel, Field


class AnomalyEngineConfig(BaseModel):
    # Monitored physical signals
    signals: List[str] = [
        "temperature",
        "vibration",
        "pressure",
        "current",
        "voltage",
        "rpm",
        "power_kw",
        "efficiency",
        "output_rate",
    ]

    # Detector A: Statistical Z-Score Thresholds
    z_score_warning_threshold: float = 2.5
    z_score_critical_threshold: float = 4.0

    # Detector B: Rolling Trend Parameters
    trend_window_size: int = 15
    trend_min_samples: int = 5
    slope_thresholds: Dict[str, float] = {
        "temperature": 0.20,     # °C per tick
        "vibration": 0.05,       # mm/s per tick
        "efficiency": -0.30,     # % per tick (negative is degrading)
        "power_kw": 0.25,        # kW per tick
        "current": 0.30,         # A per tick
    }
    monotonic_streak_threshold: int = 4

    # Detector C: Isolation Forest Parameters
    isolation_forest_features: List[str] = [
        "temperature",
        "vibration",
        "pressure",
        "current",
        "voltage",
        "rpm",
        "power_kw",
        "load",
        "efficiency",
        "output_rate",
    ]
    isolation_forest_contamination: float = 0.05
    isolation_forest_n_estimators: int = 100
    isolation_forest_random_seed: int = 42
    model_version: str = "v1.0.0"

    # Detector Weights for Fusion
    weight_statistical: float = 0.35
    weight_rolling_trend: float = 0.30
    weight_isolation_forest: float = 0.35

    # Severity Mapping Boundaries [min, max)
    severity_normal_max: float = 0.30
    severity_low_max: float = 0.50
    severity_medium_max: float = 0.70
    severity_high_max: float = 0.85
    # Above 0.85 is CRITICAL

    # Temporal Persistence & Lifecycle Parameters
    min_consecutive_anomalies_to_confirm: int = 2
    recovery_cooldown_ticks: int = 5
    min_baseline_samples_required: int = 10


_default_config = AnomalyEngineConfig()


def get_anomaly_config() -> AnomalyEngineConfig:
    return _default_config
