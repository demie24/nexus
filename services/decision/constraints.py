"""
NEXUS Hard Constraints & Action Feasibility Evaluator
Evaluates physical boundaries and operational policies to determine action feasibility.
Distinguishes infeasible actions from low-scoring actions.
"""

from typing import List, Tuple
from services.schemas import (
    ActionFeasibilityStatus,
    CounterfactualScenarioType,
    DomainConstraints,
    RawCriteriaValues,
)


def evaluate_action_feasibility(
    action: CounterfactualScenarioType,
    raw: RawCriteriaValues,
    peak_temperature: float,
    constraints: DomainConstraints,
) -> Tuple[ActionFeasibilityStatus, List[str]]:
    """
    Evaluates hard constraints on an action.
    If constraints are violated, marks action as INFEASIBLE with specific domain violation reasons.
    """
    violations: List[str] = []
    is_halt_action = (action in [CounterfactualScenarioType.EMERGENCY_STOP, CounterfactualScenarioType.SCHEDULED_SHUTDOWN])

    # 1. Critical Failure Probability Limit
    # Continuing operation under critical failure risk is infeasible
    if not is_halt_action and raw.risk > constraints.critical_failure_probability:
        violations.append(
            f"Projected failure probability ({raw.risk * 100:.1f}%) violates critical safety threshold "
            f"({constraints.critical_failure_probability * 100:.1f}%)."
        )

    # 2. Maximum Safe Operating Temperature Limit
    # Operating above thermal runaway threshold without halting is strictly infeasible
    if not is_halt_action and peak_temperature > constraints.max_safe_temperature:
        violations.append(
            f"Peak core temperature ({peak_temperature:.1f}°C) exceeds maximum allowable safety limit "
            f"({constraints.max_safe_temperature:.1f}°C)."
        )

    # 3. Maximum Allowed Downtime Limit
    # Any action that exceeds the allowable maintenance downtime window is infeasible
    if raw.downtime_hours > constraints.max_allowed_downtime_hours:
        violations.append(
            f"Required downtime ({raw.downtime_hours:.1f}h) exceeds maximum allowed downtime window "
            f"({constraints.max_allowed_downtime_hours:.1f}h)."
        )

    # 4. Minimum Acceptable RUL Margin
    # Continuing operation when RUL has expired (< threshold) without immediate repair is infeasible
    if not is_halt_action and raw.rul_hours < constraints.min_acceptable_rul_hours:
        violations.append(
            f"Projected RUL ({raw.rul_hours:.1f}h) is below the minimum acceptable operational margin "
            f"({constraints.min_acceptable_rul_hours:.1f}h)."
        )

    if violations:
        return ActionFeasibilityStatus.INFEASIBLE, violations

    return ActionFeasibilityStatus.FEASIBLE, []
