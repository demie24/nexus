"""
Tests for Domain Hard Constraints & Action Feasibility Layer
Verifies differentiation of infeasible actions from low-scoring actions,
proper violation logging, and halt action exemption rules.
"""

import pytest
from services.schemas import (
    ActionFeasibilityStatus,
    CounterfactualScenarioType,
    DomainConstraints,
    RawCriteriaValues,
)
from services.decision.constraints import evaluate_action_feasibility


@pytest.fixture
def default_constraints():
    return DomainConstraints(
        max_safe_temperature=90.0,
        critical_failure_probability=0.70,
        max_allowed_downtime_hours=8.0,
        min_acceptable_rul_hours=1.0,
    )


def test_feasible_action(default_constraints):
    raw = RawCriteriaValues(
        risk=0.25,
        cost_rm=80.0,
        production_loss_pct=10.0,
        downtime_hours=0.0,
        recovery_time_hours=0.0,
        rul_hours=18.0,
        final_health=85.0,
    )
    status, reasons = evaluate_action_feasibility(
        action=CounterfactualScenarioType.LOAD_MODULATION,
        raw=raw,
        peak_temperature=72.0,
        constraints=default_constraints,
    )
    assert status == ActionFeasibilityStatus.FEASIBLE
    assert len(reasons) == 0


def test_critical_risk_violation(default_constraints):
    raw = RawCriteriaValues(
        risk=0.85,  # Exceeds 0.70 critical limit
        cost_rm=0.0,
        production_loss_pct=0.0,
        downtime_hours=0.0,
        recovery_time_hours=0.0,
        rul_hours=12.0,
        final_health=60.0,
    )
    status, reasons = evaluate_action_feasibility(
        action=CounterfactualScenarioType.DO_NOTHING,
        raw=raw,
        peak_temperature=78.0,
        constraints=default_constraints,
    )
    assert status == ActionFeasibilityStatus.INFEASIBLE
    assert any("critical safety threshold" in r for r in reasons)


def test_temperature_limit_violation(default_constraints):
    raw = RawCriteriaValues(
        risk=0.30,
        cost_rm=120.0,
        production_loss_pct=0.0,
        downtime_hours=0.0,
        recovery_time_hours=0.0,
        rul_hours=15.0,
        final_health=70.0,
    )
    status, reasons = evaluate_action_feasibility(
        action=CounterfactualScenarioType.COOLING_BOOST,
        raw=raw,
        peak_temperature=96.5,  # Exceeds 90°C
        constraints=default_constraints,
    )
    assert status == ActionFeasibilityStatus.INFEASIBLE
    assert any("maximum allowable safety limit" in r for r in reasons)


def test_max_downtime_violation(default_constraints):
    raw = RawCriteriaValues(
        risk=0.05,
        cost_rm=1200.0,
        production_loss_pct=80.0,
        downtime_hours=10.0,  # Exceeds 8.0h allowed window
        recovery_time_hours=2.0,
        rul_hours=30.0,
        final_health=90.0,
    )
    status, reasons = evaluate_action_feasibility(
        action=CounterfactualScenarioType.EMERGENCY_STOP,
        raw=raw,
        peak_temperature=45.0,
        constraints=default_constraints,
    )
    assert status == ActionFeasibilityStatus.INFEASIBLE
    assert any("maximum allowed downtime window" in r for r in reasons)


def test_min_rul_margin_violation(default_constraints):
    raw = RawCriteriaValues(
        risk=0.45,
        cost_rm=80.0,
        production_loss_pct=15.0,
        downtime_hours=0.0,
        recovery_time_hours=0.0,
        rul_hours=0.4,  # Below 1.0h margin
        final_health=20.0,
    )
    status, reasons = evaluate_action_feasibility(
        action=CounterfactualScenarioType.LOAD_MODULATION,
        raw=raw,
        peak_temperature=75.0,
        constraints=default_constraints,
    )
    assert status == ActionFeasibilityStatus.INFEASIBLE
    assert any("minimum acceptable operational margin" in r for r in reasons)


def test_halt_action_exempt_from_risk_and_temp_constraints(default_constraints):
    """
    Emergency Stop or Scheduled Shutdown is taken specifically to HALT an extreme hazard.
    Therefore high risk or high temperature during onset cannot invalidate the stop intervention itself.
    """
    raw = RawCriteriaValues(
        risk=0.92,
        cost_rm=1200.0,
        production_loss_pct=40.0,
        downtime_hours=4.0,  # Within 8.0h limit
        recovery_time_hours=1.5,
        rul_hours=0.2,
        final_health=15.0,
    )
    status, reasons = evaluate_action_feasibility(
        action=CounterfactualScenarioType.EMERGENCY_STOP,
        raw=raw,
        peak_temperature=98.0,
        constraints=default_constraints,
    )
    assert status == ActionFeasibilityStatus.FEASIBLE
    assert len(reasons) == 0
