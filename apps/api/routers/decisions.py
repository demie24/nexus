"""
NEXUS Multi-Criteria Decision Engine API Endpoints
Provides on-demand multi-criteria decision analysis, policy configuration retrieval,
and historical decision trace records.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.session import get_db
from database.models.models import DecisionModel, MachineModel
from services.schemas import (
    DecisionAnalysisRequest,
    DecisionAnalysisResponse,
    DecisionEngineStatus,
    PolicyProfileType,
    CandidateActionEvaluation,
    CriteriaWeights,
    DomainConstraints,
    EvidenceReferences,
    RankStabilityLevel,
    ActionFeasibilityStatus,
    DataProvenance,
)
from services.decision.config import POLICY_PROFILES, DEFAULT_CONSTRAINTS
from services.decision.engine import get_decision_engine, DecisionEngine

router = APIRouter(tags=["Multi-Criteria Decision Engine"])


def _model_to_response(m: DecisionModel) -> DecisionAnalysisResponse:
    candidates = [CandidateActionEvaluation(**c) for c in m.candidate_actions]
    top_cand = next(
        (c for c in candidates if c.feasibility == ActionFeasibilityStatus.FEASIBLE),
        candidates[0] if candidates else None,
    )
    return DecisionAnalysisResponse(
        decision_id=m.decision_id,
        machine_id=m.machine_id,
        created_at=m.created_at,
        status=DecisionEngineStatus(m.status),
        policy_profile=PolicyProfileType(m.policy_profile),
        criteria_weights=CriteriaWeights(**m.criteria_weights),
        constraints=DomainConstraints(**m.constraints),
        ranked_candidates=candidates,
        top_recommended_candidate=top_cand,
        decision_explanation=m.decision_explanation,
        decision_confidence=m.confidence,
        confidence_reasons=["Retrieved from immutable historical decision record."],
        rank_stability=RankStabilityLevel(m.rank_stability),
        rank_stability_reason="Retrieved from immutable historical record.",
        sensitivity_analysis=[],
        evidence_references=EvidenceReferences(**m.evidence_references),
        provenance=DataProvenance(m.provenance),
    )


@router.get("/decisions/policies", status_code=status.HTTP_200_OK)
@router.get("/decision-policies", status_code=status.HTTP_200_OK)
def get_decision_policies():
    """
    Returns available operational policy profiles, their multi-criteria weight distributions,
    and default domain safety constraints.
    """
    return {
        "policies": {
            profile.value: weights.model_dump()
            for profile, weights in POLICY_PROFILES.items()
        },
        "default_constraints": DEFAULT_CONSTRAINTS.model_dump(),
        "criteria_definitions": {
            "risk": "Future failure probability (lower-is-better, bounded [0, 1])",
            "cost": "Intervention operational expenditure in RM (lower-is-better, normalized to RM 2,000)",
            "production": "Throughput loss percentage (lower loss is better, bounded [0, 100%])",
            "downtime": "Operational downtime duration in hours (lower-is-better, normalized to 12h)",
            "recovery": "Maintenance & recovery duration in hours (lower-is-better, normalized to 6h)",
            "health": "Health score & RUL preservation (higher-is-better, composite [0, 1])",
        },
    }


@router.post("/decisions/analyze", response_model=DecisionAnalysisResponse, status_code=status.HTTP_200_OK)
def analyze_decision(
    request: DecisionAnalysisRequest,
    db: Session = Depends(get_db),
):
    """
    Executes on-demand multi-criteria decision analysis across all intervention candidates
    using counterfactual simulations branched from an immutable Digital Twin snapshot.
    """
    engine = get_decision_engine()
    try:
        response = engine.analyze(request=request, db=db)
        return response
    except ValueError as val_err:
        err_msg = str(val_err)
        if "not registered" in err_msg or "not found" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Decision Engine evaluation failed: {str(exc)}",
        )


@router.get("/decisions", response_model=List[DecisionAnalysisResponse], status_code=status.HTTP_200_OK)
def list_decisions(
    machine_id: Optional[str] = Query(None, description="Filter decisions by machine ID"),
    policy_profile: Optional[str] = Query(None, description="Filter by policy profile"),
    limit: int = Query(50, ge=1, le=500, description="Max decisions to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
):
    """
    Retrieves historical multi-criteria decision analysis records.
    """
    query = db.query(DecisionModel)
    if machine_id:
        query = query.filter(DecisionModel.machine_id == machine_id)
    if policy_profile:
        query = query.filter(DecisionModel.policy_profile == policy_profile.upper())

    records = query.order_by(desc(DecisionModel.created_at)).offset(offset).limit(limit).all()
    return [_model_to_response(r) for r in records]


@router.get("/decisions/{decision_id}", response_model=DecisionAnalysisResponse, status_code=status.HTTP_200_OK)
def get_decision_detail(
    decision_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieves a single decision analysis record by its unique decision ID.
    """
    record = db.query(DecisionModel).filter(DecisionModel.decision_id == decision_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision record '{decision_id}' not found.",
        )
    return _model_to_response(record)


@router.get("/machines/{machine_id}/decisions", response_model=List[DecisionAnalysisResponse], status_code=status.HTTP_200_OK)
def get_machine_decisions(
    machine_id: str,
    limit: int = Query(20, ge=1, le=200, description="Max decisions to return"),
    db: Session = Depends(get_db),
):
    """
    Retrieves recent decision records for a specific machine.
    """
    # Verify machine exists
    machine = db.query(MachineModel).filter(MachineModel.id == machine_id).first()
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine '{machine_id}' not found.",
        )

    records = (
        db.query(DecisionModel)
        .filter(DecisionModel.machine_id == machine_id)
        .order_by(desc(DecisionModel.created_at))
        .limit(limit)
        .all()
    )
    return [_model_to_response(r) for r in records]
