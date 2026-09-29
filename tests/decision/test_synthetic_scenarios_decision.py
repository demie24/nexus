"""
End-to-End Synthetic Scenario Tests for DecisionEngine
Evaluates decision analysis on actual simulated machinery across nominal, moderate stress,
and severe failure states.
"""

import pytest
from sqlalchemy.orm import Session
from services.schemas import (
    DecisionAnalysisRequest,
    PolicyProfileType,
    ActionFeasibilityStatus,
    CounterfactualScenarioType,
    CriteriaWeights,
)
from services.decision.engine import get_decision_engine
from database.models.models import DecisionModel


def test_decision_engine_nominal_machine(db_session: Session):
    engine = get_decision_engine()

    request = DecisionAnalysisRequest(
        machine_id="M01",
        policy_profile=PolicyProfileType.BALANCED,
        horizon_hours=4.0,
        persist=True,
    )

    response = engine.analyze(request=request, db=db_session)

    assert response.machine_id == "M01"
    assert response.decision_id.startswith("DEC-M01-")
    assert response.policy_profile == PolicyProfileType.BALANCED
    assert len(response.ranked_candidates) == 6
    assert response.top_recommended_candidate is not None
    assert response.top_recommended_candidate.feasibility == ActionFeasibilityStatus.FEASIBLE

    # Verify all 5 core action categories evaluated
    action_types = {c.action for c in response.ranked_candidates}
    assert CounterfactualScenarioType.DO_NOTHING in action_types
    assert CounterfactualScenarioType.LOAD_MODULATION in action_types
    assert CounterfactualScenarioType.COOLING_BOOST in action_types
    assert CounterfactualScenarioType.SCHEDULED_SHUTDOWN in action_types
    assert CounterfactualScenarioType.EMERGENCY_STOP in action_types

    # Verify DB persistence
    db_record = db_session.query(DecisionModel).filter(DecisionModel.decision_id == response.decision_id).first()
    assert db_record is not None
    assert db_record.machine_id == "M01"
    assert len(db_record.candidate_actions) == 6


def test_decision_engine_with_custom_weights(db_session: Session):
    engine = get_decision_engine()

    custom_weights = CriteriaWeights(
        risk_weight=0.50,
        cost_weight=0.00,
        production_weight=0.00,
        downtime_weight=0.00,
        recovery_weight=0.00,
        health_weight=0.50,
    )

    request = DecisionAnalysisRequest(
        machine_id="M02",
        custom_weights=custom_weights,
        horizon_hours=2.0,
        persist=False,
    )

    response = engine.analyze(request=request, db=db_session)
    assert response.policy_profile == PolicyProfileType.CUSTOM
    assert response.criteria_weights.risk_weight == 0.50
    assert response.criteria_weights.health_weight == 0.50


def test_decision_engine_all_policies_sensitivity(db_session: Session):
    engine = get_decision_engine()

    request = DecisionAnalysisRequest(
        machine_id="M03",
        policy_profile=PolicyProfileType.SAFETY_FIRST,
        horizon_hours=4.0,
        persist=False,
    )

    response = engine.analyze(request=request, db=db_session)
    assert len(response.sensitivity_analysis) == 3
    profiles = {p.profile: p for p in response.sensitivity_analysis}
    assert PolicyProfileType.BALANCED in profiles
    assert PolicyProfileType.SAFETY_FIRST in profiles
    assert PolicyProfileType.PRODUCTION_FIRST in profiles
