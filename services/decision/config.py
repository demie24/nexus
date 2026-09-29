"""
NEXUS Multi-Criteria Decision Engine Configuration
Defines default policy profiles, criterion weights, intervention cost mappings, and domain constraints.
"""

from typing import Dict, Any
from services.schemas import (
    PolicyProfileType,
    CriteriaWeights,
    DomainConstraints,
    CounterfactualScenarioType,
)

# Operational Policy Profiles (Sum of weights strictly normalized to 1.0)
POLICY_PROFILES: Dict[PolicyProfileType, CriteriaWeights] = {
    PolicyProfileType.BALANCED: CriteriaWeights(
        risk_weight=0.25,
        cost_weight=0.15,
        production_weight=0.20,
        downtime_weight=0.15,
        recovery_weight=0.10,
        health_weight=0.15,
    ),
    PolicyProfileType.SAFETY_FIRST: CriteriaWeights(
        risk_weight=0.40,
        cost_weight=0.05,
        production_weight=0.10,
        downtime_weight=0.10,
        recovery_weight=0.10,
        health_weight=0.25,
    ),
    PolicyProfileType.PRODUCTION_FIRST: CriteriaWeights(
        risk_weight=0.15,
        cost_weight=0.15,
        production_weight=0.40,
        downtime_weight=0.15,
        recovery_weight=0.05,
        health_weight=0.10,
    ),
}

# Domain Safety and Operational Constraint Defaults
DEFAULT_CONSTRAINTS = DomainConstraints(
    max_safe_temperature=90.0,              # Peak core operating temperature threshold (°C)
    critical_failure_probability=0.70,       # Hazard rate limit for continuing operation [0, 1]
    max_allowed_downtime_hours=8.0,         # Maximum allowable unplanned/planned downtime
    min_acceptable_rul_hours=1.0,            # Minimum allowable projected RUL
)

# Standardized Estimated Operational/Intervention Costs in RM (Malaysian Ringgit)
INTERVENTION_COST_MAP: Dict[CounterfactualScenarioType, float] = {
    CounterfactualScenarioType.DO_NOTHING: 0.0,
    CounterfactualScenarioType.LOAD_MODULATION: 80.0,      # Inverter torque/rpm tuning & recalibration
    CounterfactualScenarioType.COOLING_BOOST: 120.0,       # Auxiliary chiller energy & coolant fluid
    CounterfactualScenarioType.SCHEDULED_SHUTDOWN: 450.0,  # Scheduled technicians & off-peak turnaround
    CounterfactualScenarioType.EMERGENCY_STOP: 1200.0,     # Emergency call-out, triage & immediate reset
}

# Normalization Maximum Scales (for Bounded Min-Max Utility Functions)
MAX_COST_RM = 2000.0
MAX_DOWNTIME_HOURS = 12.0
MAX_RECOVERY_HOURS = 6.0
MAX_RUL_HOURS = 48.0

ENGINE_VERSION = "v1.0.0-mcdm"
DECISION_RULE_VERSION = "v1.0.0"
