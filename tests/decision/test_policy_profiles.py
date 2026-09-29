"""
Tests for Operational Policy Profiles & Policy Behavior
Verifies that POLICY_PROFILES weights represent the intended operational policies
and that rankings respond coherently to changes in policy preferences.
"""

import pytest
from services.schemas import (
    PolicyProfileType,
    CandidateActionEvaluation,
    CounterfactualScenarioType,
    ActionFeasibilityStatus,
    NormalizedUtilities,
    RawCriteriaValues,
)
from services.decision.config import POLICY_PROFILES
from services.decision.criteria import normalize_weights
from services.decision.ranking import calculate_decision_score


def test_policy_weights_sum_to_one():
    for profile, weights in POLICY_PROFILES.items():
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


def test_safety_first_prioritizes_risk_and_health():
    safety_weights = POLICY_PROFILES[PolicyProfileType.SAFETY_FIRST]
    assert safety_weights.risk_weight == 0.40
    assert safety_weights.health_weight == 0.25
    assert safety_weights.production_weight == 0.10


def test_production_first_prioritizes_throughput():
    prod_weights = POLICY_PROFILES[PolicyProfileType.PRODUCTION_FIRST]
    assert prod_weights.production_weight == 0.40
    assert prod_weights.risk_weight == 0.15


def test_policy_shift_changes_preferred_candidate():
    """
    Candidate A: High safety (low risk, high health), but high production loss.
    Candidate B: High throughput (0 loss), but moderate risk.
    Under SAFETY_FIRST, Candidate A should win.
    Under PRODUCTION_FIRST, Candidate B should win.
    """
    # Candidate A: Emergency stop / heavy throttle
    u_a = NormalizedUtilities(
        risk_utility=0.95, cost_utility=0.4, production_utility=0.2,
        downtime_utility=0.3, recovery_utility=0.3, health_utility=0.9
    )
    # Candidate B: Keep running / ignore degradation (high throughput, poor safety)
    u_b = NormalizedUtilities(
        risk_utility=0.4, cost_utility=0.8, production_utility=0.95,
        downtime_utility=0.95, recovery_utility=0.95, health_utility=0.4
    )

    score_a_safety = calculate_decision_score(u_a, POLICY_PROFILES[PolicyProfileType.SAFETY_FIRST])
    score_b_safety = calculate_decision_score(u_b, POLICY_PROFILES[PolicyProfileType.SAFETY_FIRST])
    assert score_a_safety > score_b_safety

    score_a_prod = calculate_decision_score(u_a, POLICY_PROFILES[PolicyProfileType.PRODUCTION_FIRST])
    score_b_prod = calculate_decision_score(u_b, POLICY_PROFILES[PolicyProfileType.PRODUCTION_FIRST])
    assert score_b_prod > score_a_prod
