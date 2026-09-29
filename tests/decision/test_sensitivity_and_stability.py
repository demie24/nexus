"""
Tests for Policy Sensitivity Analysis & Rank Stability Evaluation
Verifies detection of HIGH_STABILITY, MODERATE_STABILITY, and LOW_STABILITY scenarios,
and verifies output format of sensitivity profiles.
"""

import pytest
from services.schemas import (
    CandidateActionEvaluation,
    CounterfactualScenarioType,
    ActionFeasibilityStatus,
    NormalizedUtilities,
    RawCriteriaValues,
    RankStabilityLevel,
    PolicyProfileType,
)
from services.decision.sensitivity import run_sensitivity_analysis


def _make_candidate(action: CounterfactualScenarioType, label: str, utilities: NormalizedUtilities):
    return CandidateActionEvaluation(
        rank=1,
        action=action,
        action_label=label,
        parameters={},
        decision_score=0.5,
        feasibility=ActionFeasibilityStatus.FEASIBLE,
        feasibility_reasons=[],
        raw_criteria=RawCriteriaValues(
            risk=0.1, cost_rm=50.0, production_loss_pct=5.0,
            downtime_hours=0.0, recovery_time_hours=0.0, rul_hours=30.0, final_health=90.0
        ),
        utilities=utilities,
        key_benefits=[],
        key_risks=[],
        trade_offs=[],
        near_tie=False,
        near_tie_with=None,
    )


def test_high_stability_dominant_action():
    # Candidate 1 is superior across ALL utilities (dominant)
    c1 = _make_candidate(
        CounterfactualScenarioType.LOAD_MODULATION,
        "Load Modulation (-20%)",
        NormalizedUtilities(
            risk_utility=0.95, cost_utility=0.90, production_utility=0.90,
            downtime_utility=1.0, recovery_utility=1.0, health_utility=0.95
        )
    )
    c2 = _make_candidate(
        CounterfactualScenarioType.COOLING_BOOST,
        "Cooling Boost",
        NormalizedUtilities(
            risk_utility=0.60, cost_utility=0.70, production_utility=0.80,
            downtime_utility=0.9, recovery_utility=0.9, health_utility=0.60
        )
    )

    profiles, stability, reason = run_sensitivity_analysis([c1, c2])
    assert stability == RankStabilityLevel.HIGH_STABILITY
    assert len(profiles) == 3
    assert all(p.top_action == CounterfactualScenarioType.LOAD_MODULATION for p in profiles)
    assert "optimal across all operational policies" in reason


def test_moderate_or_low_stability_trade_off():
    # Action 1 excels in safety, Action 2 excels in production
    c1 = _make_candidate(
        CounterfactualScenarioType.EMERGENCY_STOP,
        "Emergency Stop",
        NormalizedUtilities(
            risk_utility=0.99, cost_utility=0.20, production_utility=0.10,
            downtime_utility=0.20, recovery_utility=0.20, health_utility=0.99
        )
    )
    c2 = _make_candidate(
        CounterfactualScenarioType.DO_NOTHING,
        "Do Nothing",
        NormalizedUtilities(
            risk_utility=0.20, cost_utility=1.0, production_utility=1.0,
            downtime_utility=1.0, recovery_utility=1.0, health_utility=0.20
        )
    )

    profiles, stability, reason = run_sensitivity_analysis([c1, c2])
    # Under SAFETY_FIRST c1 wins, under PRODUCTION_FIRST c2 wins -> Not HIGH_STABILITY
    assert stability in [RankStabilityLevel.MODERATE_STABILITY, RankStabilityLevel.LOW_STABILITY]
    assert len(profiles) == 3
