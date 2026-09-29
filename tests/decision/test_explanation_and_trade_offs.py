"""
Tests for Decision Narrative & Trade-Off Matrix Generator
Verifies deterministic benefit/risk generation, comparative trade-off logic against DO_NOTHING,
and executive explanation synthesis.
"""

import pytest
from services.schemas import (
    CandidateActionEvaluation,
    CounterfactualScenarioType,
    ActionFeasibilityStatus,
    DomainConstraints,
    RawCriteriaValues,
    NormalizedUtilities,
)
from services.decision.explanation import (
    generate_candidate_trade_offs,
    generate_decision_narrative,
)


def test_trade_offs_against_baseline():
    baseline_raw = RawCriteriaValues(
        risk=0.65,
        cost_rm=0.0,
        production_loss_pct=0.0,
        downtime_hours=0.0,
        recovery_time_hours=0.0,
        rul_hours=6.0,
        final_health=50.0,
    )
    action_raw = RawCriteriaValues(
        risk=0.20,
        cost_rm=80.0,
        production_loss_pct=8.0,
        downtime_hours=0.0,
        recovery_time_hours=0.0,
        rul_hours=14.0,
        final_health=75.0,
    )

    benefits, risks, trade_offs = generate_candidate_trade_offs(
        action=CounterfactualScenarioType.LOAD_MODULATION,
        raw=action_raw,
        baseline_raw=baseline_raw,
    )

    assert any("Maintains low residual failure hazard" in b for b in benefits)
    assert any("Economical intervention cost" in b for b in benefits)
    assert any("45.0 percentage points" in t for t in trade_offs)
    assert any("8.0 hours" in t for t in trade_offs)


def test_decision_narrative_generation():
    raw = RawCriteriaValues(
        risk=0.15, cost_rm=80.0, production_loss_pct=6.0, downtime_hours=0.0,
        recovery_time_hours=0.0, rul_hours=20.0, final_health=85.0
    )
    c1 = CandidateActionEvaluation(
        rank=1,
        action=CounterfactualScenarioType.LOAD_MODULATION,
        action_label="Load Modulation (-20%)",
        parameters={"load_reduction": 0.20},
        decision_score=0.8450,
        feasibility=ActionFeasibilityStatus.FEASIBLE,
        feasibility_reasons=[],
        raw_criteria=raw,
        utilities=NormalizedUtilities(
            risk_utility=0.85, cost_utility=0.96, production_utility=0.94,
            downtime_utility=1.0, recovery_utility=1.0, health_utility=0.85
        ),
        key_benefits=["Low risk"],
        key_risks=[],
        trade_offs=["Slight throughput drop for big safety gain."],
        near_tie=False,
        near_tie_with=None,
    )

    constraints = DomainConstraints()
    narrative, confidence, reasons = generate_decision_narrative(
        ranked_candidates=[c1],
        constraints=constraints,
        baseline_raw=raw,
    )

    assert "RECOMMENDED ACTION: Load Modulation (-20%)" in narrative
    assert confidence == "HIGH"
    assert len(reasons) > 0


def test_narrative_when_all_infeasible():
    raw = RawCriteriaValues(
        risk=0.95, cost_rm=0.0, production_loss_pct=0.0, downtime_hours=0.0,
        recovery_time_hours=0.0, rul_hours=0.1, final_health=10.0
    )
    c_inf = CandidateActionEvaluation(
        rank=1,
        action=CounterfactualScenarioType.DO_NOTHING,
        action_label="Do Nothing",
        parameters={},
        decision_score=0.30,
        feasibility=ActionFeasibilityStatus.INFEASIBLE,
        feasibility_reasons=["Risk exceeds critical safety threshold."],
        raw_criteria=raw,
        utilities=NormalizedUtilities(
            risk_utility=0.05, cost_utility=1.0, production_utility=1.0,
            downtime_utility=1.0, recovery_utility=1.0, health_utility=0.1
        ),
        key_benefits=[],
        key_risks=["Catastrophic failure hazard"],
        trade_offs=[],
        near_tie=False,
        near_tie_with=None,
    )

    constraints = DomainConstraints()
    narrative, confidence, reasons = generate_decision_narrative(
        ranked_candidates=[c_inf],
        constraints=constraints,
    )

    assert "CRITICAL ALERT: No evaluated action satisfies all operational safety constraints" in narrative
    assert confidence == "LOW"
