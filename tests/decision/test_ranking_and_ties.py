"""
Tests for Multi-Criteria Action Ranking & Near-Tie Detection
Verifies score computation, strict sorting of feasible before infeasible candidates,
and near-tie alerting when score delta is within the tolerance threshold (<= 0.015).
"""

import pytest
from services.schemas import (
    CandidateActionEvaluation,
    CounterfactualScenarioType,
    ActionFeasibilityStatus,
    CriteriaWeights,
    NormalizedUtilities,
    RawCriteriaValues,
)
from services.decision.ranking import calculate_decision_score, rank_candidate_actions


def _make_candidate(
    action: CounterfactualScenarioType,
    label: str,
    score: float,
    feasibility: ActionFeasibilityStatus,
) -> CandidateActionEvaluation:
    return CandidateActionEvaluation(
        rank=1,
        action=action,
        action_label=label,
        parameters={},
        decision_score=score,
        feasibility=feasibility,
        feasibility_reasons=[] if feasibility == ActionFeasibilityStatus.FEASIBLE else ["Constraint violated"],
        raw_criteria=RawCriteriaValues(
            risk=0.2, cost_rm=100.0, production_loss_pct=5.0, downtime_hours=0.0,
            recovery_time_hours=0.0, rul_hours=24.0, final_health=80.0
        ),
        utilities=NormalizedUtilities(
            risk_utility=0.8, cost_utility=0.9, production_utility=0.95,
            downtime_utility=1.0, recovery_utility=1.0, health_utility=0.8
        ),
        key_benefits=[],
        key_risks=[],
        trade_offs=[],
        near_tie=False,
        near_tie_with=None,
    )


def test_calculate_decision_score_weighted_sum():
    utilities = NormalizedUtilities(
        risk_utility=1.0,
        cost_utility=1.0,
        production_utility=1.0,
        downtime_utility=1.0,
        recovery_utility=1.0,
        health_utility=1.0,
    )
    weights = CriteriaWeights(
        risk_weight=0.25,
        cost_weight=0.15,
        production_weight=0.20,
        downtime_weight=0.15,
        recovery_weight=0.10,
        health_weight=0.15,
    )
    score = calculate_decision_score(utilities, weights)
    assert score == 1.0


def test_feasible_ranked_above_infeasible_regardless_of_score():
    """
    An infeasible candidate with a higher raw score (e.g. Do Nothing with 0 downtime/cost)
    MUST NOT be ranked above a feasible candidate that meets all safety constraints.
    """
    c_infeasible = _make_candidate(
        action=CounterfactualScenarioType.DO_NOTHING,
        label="Do Nothing",
        score=0.92,
        feasibility=ActionFeasibilityStatus.INFEASIBLE,
    )
    c_feasible = _make_candidate(
        action=CounterfactualScenarioType.LOAD_MODULATION,
        label="Load Modulation (-20%)",
        score=0.78,
        feasibility=ActionFeasibilityStatus.FEASIBLE,
    )

    ranked = rank_candidate_actions([c_infeasible, c_feasible])
    assert ranked[0].action_label == "Load Modulation (-20%)"
    assert ranked[0].rank == 1
    assert ranked[0].feasibility == ActionFeasibilityStatus.FEASIBLE
    assert ranked[1].action_label == "Do Nothing"
    assert ranked[1].rank == 2
    assert ranked[1].feasibility == ActionFeasibilityStatus.INFEASIBLE


def test_near_tie_detection():
    # Two feasible candidates with score delta = 0.008 (<= 0.015)
    c1 = _make_candidate(
        action=CounterfactualScenarioType.LOAD_MODULATION,
        label="Load Modulation (-20%)",
        score=0.812,
        feasibility=ActionFeasibilityStatus.FEASIBLE,
    )
    c2 = _make_candidate(
        action=CounterfactualScenarioType.COOLING_BOOST,
        label="Cooling Boost",
        score=0.805,
        feasibility=ActionFeasibilityStatus.FEASIBLE,
    )

    ranked = rank_candidate_actions([c1, c2], tie_threshold=0.015)
    assert ranked[0].near_tie is True
    assert ranked[0].near_tie_with == "Cooling Boost"
    assert ranked[1].near_tie is True
    assert ranked[1].near_tie_with == "Load Modulation (-20%)"


def test_no_near_tie_when_delta_large():
    # Two feasible candidates with score delta = 0.15 (> 0.015)
    c1 = _make_candidate(
        action=CounterfactualScenarioType.LOAD_MODULATION,
        label="Load Modulation (-20%)",
        score=0.850,
        feasibility=ActionFeasibilityStatus.FEASIBLE,
    )
    c2 = _make_candidate(
        action=CounterfactualScenarioType.EMERGENCY_STOP,
        label="Emergency Stop",
        score=0.620,
        feasibility=ActionFeasibilityStatus.FEASIBLE,
    )

    ranked = rank_candidate_actions([c1, c2], tie_threshold=0.015)
    assert ranked[0].near_tie is False
    assert ranked[0].near_tie_with is None
    assert ranked[1].near_tie is False
