"""
Tests for Multi-Criteria Weight Normalization & Dimensionless Utility Functions
Verifies that weights sum to 1.0, utilities are strictly bounded in [0.0, 1.0],
and monotonicity/directionality rules are strictly respected.
"""

import pytest
from services.schemas import CriteriaWeights, RawCriteriaValues
from services.decision.criteria import normalize_weights, calculate_utilities
from services.decision.config import (
    MAX_COST_RM,
    MAX_DOWNTIME_HOURS,
    MAX_RECOVERY_HOURS,
    MAX_RUL_HOURS,
)


def test_weight_normalization_proportional():
    weights = CriteriaWeights(
        risk_weight=0.5,
        cost_weight=0.5,
        production_weight=0.5,
        downtime_weight=0.5,
        recovery_weight=0.0,
        health_weight=0.0,
    )
    norm = normalize_weights(weights)
    total = (
        norm.risk_weight +
        norm.cost_weight +
        norm.production_weight +
        norm.downtime_weight +
        norm.recovery_weight +
        norm.health_weight
    )
    assert abs(total - 1.0) < 0.001
    assert norm.risk_weight == 0.25
    assert norm.cost_weight == 0.25
    assert norm.production_weight == 0.25
    assert norm.downtime_weight == 0.25


def test_weight_normalization_zero_fallback():
    zero_weights = CriteriaWeights(
        risk_weight=0.0,
        cost_weight=0.0,
        production_weight=0.0,
        downtime_weight=0.0,
        recovery_weight=0.0,
        health_weight=0.0,
    )
    norm = normalize_weights(zero_weights)
    total = (
        norm.risk_weight +
        norm.cost_weight +
        norm.production_weight +
        norm.downtime_weight +
        norm.recovery_weight +
        norm.health_weight
    )
    assert abs(total - 1.0) < 0.001
    assert abs(norm.risk_weight - 1.0 / 6.0) < 0.001


def test_utility_calculation_best_case():
    raw_best = RawCriteriaValues(
        risk=0.0,
        cost_rm=0.0,
        production_loss_pct=0.0,
        downtime_hours=0.0,
        recovery_time_hours=0.0,
        rul_hours=MAX_RUL_HOURS,
        final_health=100.0,
    )
    u = calculate_utilities(raw_best)
    assert u.risk_utility == 1.0
    assert u.cost_utility == 1.0
    assert u.production_utility == 1.0
    assert u.downtime_utility == 1.0
    assert u.recovery_utility == 1.0
    assert u.health_utility == 1.0


def test_utility_calculation_worst_case():
    raw_worst = RawCriteriaValues(
        risk=1.0,
        cost_rm=MAX_COST_RM,
        production_loss_pct=100.0,
        downtime_hours=MAX_DOWNTIME_HOURS,
        recovery_time_hours=MAX_RECOVERY_HOURS,
        rul_hours=0.0,
        final_health=0.0,
    )
    u = calculate_utilities(raw_worst)
    assert u.risk_utility == 0.0
    assert u.cost_utility == 0.0
    assert u.production_utility == 0.0
    assert u.downtime_utility == 0.0
    assert u.recovery_utility == 0.0
    assert u.health_utility == 0.0


def test_utility_clamping_on_extreme_values():
    raw_extreme = RawCriteriaValues(
        risk=1.5,
        cost_rm=5000.0,
        production_loss_pct=150.0,
        downtime_hours=24.0,
        recovery_time_hours=12.0,
        rul_hours=100.0,
        final_health=150.0,
    )
    u = calculate_utilities(raw_extreme)
    # Check bounds strictly in [0.0, 1.0]
    for val in [
        u.risk_utility,
        u.cost_utility,
        u.production_utility,
        u.downtime_utility,
        u.recovery_utility,
        u.health_utility,
    ]:
        assert 0.0 <= val <= 1.0


def test_utility_monotonicity():
    # Lower risk must yield higher utility
    r1 = RawCriteriaValues(risk=0.2, cost_rm=100, production_loss_pct=5, downtime_hours=0, recovery_time_hours=0, rul_hours=30, final_health=80)
    r2 = RawCriteriaValues(risk=0.6, cost_rm=100, production_loss_pct=5, downtime_hours=0, recovery_time_hours=0, rul_hours=30, final_health=80)
    u1 = calculate_utilities(r1)
    u2 = calculate_utilities(r2)
    assert u1.risk_utility > u2.risk_utility
