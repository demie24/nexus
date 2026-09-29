"""
Predictive Intelligence Configuration
Defines forecasting horizons, thresholds, risk boundaries, model versions, and feature sets.
"""

from pathlib import Path
from typing import List
from services.schemas import SeverityLevel


# Forecasting horizons in minutes (1h, 2h, 4h, 6h)
DEFAULT_HORIZONS_MINUTES: List[int] = [60, 120, 240, 360]
PRIMARY_HORIZON_MINUTES: int = 120

# RUL and Health parameters
CRITICAL_HEALTH_THRESHOLD: float = 20.0
MAX_RUL_HOURS: float = 72.0
CONFIDENCE_LEVEL: float = 0.90
COLD_START_MIN_SAMPLES: int = 15
WINDOW_SIZE: int = 20

# Risk classification thresholds
RISK_THRESHOLD_LOW: float = 0.20
RISK_THRESHOLD_MEDIUM: float = 0.50
RISK_THRESHOLD_HIGH: float = 0.75


def classify_risk(probability: float) -> SeverityLevel:
    """Classifies failure probability into SeverityLevel."""
    if probability < RISK_THRESHOLD_LOW:
        return SeverityLevel.LOW
    elif probability < RISK_THRESHOLD_MEDIUM:
        return SeverityLevel.MEDIUM
    elif probability < RISK_THRESHOLD_HIGH:
        return SeverityLevel.HIGH
    return SeverityLevel.CRITICAL


# Versioning
MODEL_VERSION: str = "v1.0.0"
FEATURE_VERSION: str = "v1.0.0"

# Storage
ARTIFACTS_DIR: Path = Path("artifacts/models")
PREDICTIVE_MODEL_PATH: Path = ARTIFACTS_DIR / "predictive_suite_v1.joblib"

# Feature definitions
FEATURE_NAMES: List[str] = [
    "temp_current",
    "vib_current",
    "pressure_current",
    "current_a",
    "voltage_v",
    "rpm_val",
    "power_kw_val",
    "load_val",
    "eff_val",
    "temp_mean",
    "temp_std",
    "temp_slope",
    "vib_mean",
    "vib_std",
    "vib_slope",
    "pressure_mean",
    "pressure_slope",
    "current_mean",
    "current_slope",
    "power_mean",
    "power_slope",
    "eff_mean",
    "eff_slope",
    "load_mean",
    "load_slope",
    "thermal_stress",
    "vib_stress",
    "load_stress",
    "energy_intensity",
    "health_current",
    "health_slope",
    "health_delta",
]
