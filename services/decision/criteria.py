"""
NEXUS Multi-Criteria Normalization & Utility Engine
Transforms multi-unit physical, economic, and operational metrics into dimensionless utility scores [0.0, 1.0].
"""

from services.schemas import RawCriteriaValues, NormalizedUtilities, CriteriaWeights
from services.decision.config import (
    MAX_COST_RM,
    MAX_DOWNTIME_HOURS,
    MAX_RECOVERY_HOURS,
    MAX_RUL_HOURS,
)


def normalize_weights(weights: CriteriaWeights) -> CriteriaWeights:
    """
    Normalizes criteria weights so that sum(w_i) strictly equals 1.0.
    """
    total = (
        weights.risk_weight +
        weights.cost_weight +
        weights.production_weight +
        weights.downtime_weight +
        weights.recovery_weight +
        weights.health_weight
    )
    if total <= 0.0001:
        # Fallback to equal weighting
        return CriteriaWeights(
            risk_weight=1.0 / 6.0,
            cost_weight=1.0 / 6.0,
            production_weight=1.0 / 6.0,
            downtime_weight=1.0 / 6.0,
            recovery_weight=1.0 / 6.0,
            health_weight=1.0 / 6.0,
        )

    return CriteriaWeights(
        risk_weight=round(weights.risk_weight / total, 4),
        cost_weight=round(weights.cost_weight / total, 4),
        production_weight=round(weights.production_weight / total, 4),
        downtime_weight=round(weights.downtime_weight / total, 4),
        recovery_weight=round(weights.recovery_weight / total, 4),
        health_weight=round(weights.health_weight / total, 4),
    )


def calculate_utilities(raw: RawCriteriaValues) -> NormalizedUtilities:
    """
    Computes normalized dimensionless utilities u_i in [0.0, 1.0].
    Higher utility is always better (1.0 = optimal, 0.0 = worst).

    Utility Definitions:
    1. Risk Utility (Lower-is-better):
       u_risk = 1.0 - clamp(risk, 0.0, 1.0)
    2. Cost Utility (Lower-is-better):
       u_cost = 1.0 - clamp(cost_rm / MAX_COST_RM, 0.0, 1.0)
    3. Production Utility (Lower throughput loss is better):
       u_prod = 1.0 - clamp(production_loss_pct / 100.0, 0.0, 1.0)
    4. Downtime Utility (Lower downtime is better):
       u_downtime = 1.0 - clamp(downtime_hours / MAX_DOWNTIME_HOURS, 0.0, 1.0)
    5. Recovery Time Utility (Lower recovery duration is better):
       u_recovery = 1.0 - clamp(recovery_time_hours / MAX_RECOVERY_HOURS, 0.0, 1.0)
    6. Health Preservation Utility (Higher RUL & Health is better):
       u_health = 0.5 * clamp(rul_hours / MAX_RUL_HOURS, 0.0, 1.0) + 0.5 * clamp(final_health / 100.0, 0.0, 1.0)
    """
    # 1. Risk utility
    u_risk = max(0.0, min(1.0, 1.0 - raw.risk))

    # 2. Cost utility
    cost_fraction = raw.cost_rm / MAX_COST_RM
    u_cost = max(0.0, min(1.0, 1.0 - cost_fraction))

    # 3. Production throughput utility
    loss_fraction = raw.production_loss_pct / 100.0
    u_prod = max(0.0, min(1.0, 1.0 - loss_fraction))

    # 4. Downtime utility
    downtime_fraction = raw.downtime_hours / MAX_DOWNTIME_HOURS
    u_downtime = max(0.0, min(1.0, 1.0 - downtime_fraction))

    # 5. Recovery time utility
    recovery_fraction = raw.recovery_time_hours / MAX_RECOVERY_HOURS
    u_recovery = max(0.0, min(1.0, 1.0 - recovery_fraction))

    # 6. Health & RUL preservation utility
    rul_score = min(1.0, max(0.0, raw.rul_hours / MAX_RUL_HOURS))
    health_score = min(1.0, max(0.0, raw.final_health / 100.0))
    u_health = 0.5 * rul_score + 0.5 * health_score

    return NormalizedUtilities(
        risk_utility=round(u_risk, 4),
        cost_utility=round(u_cost, 4),
        production_utility=round(u_prod, 4),
        downtime_utility=round(u_downtime, 4),
        recovery_utility=round(u_recovery, 4),
        health_utility=round(u_health, 4),
    )
