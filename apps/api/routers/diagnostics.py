"""
NEXUS Root Cause Analysis (RCA) & Diagnostics API Endpoints
Provides historical diagnostic query, incident-level RCA retrieval, and on-demand diagnostic analysis.
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.session import get_db
from database.models.models import DiagnosticModel, MachineModel
from services.schemas import (
    Diagnostic,
    DiagnosticAnalysisRequest,
    DiagnosticAnalysisResponse,
)
from services.diagnostics.engine import get_rca_engine

router = APIRouter(prefix="/diagnostics", tags=["Root Cause Analysis & Diagnostics"])


@router.get("", response_model=List[Diagnostic], status_code=status.HTTP_200_OK)
def list_diagnostics(
    machine_id: Optional[str] = Query(None, description="Filter by machine ID"),
    likely_cause: Optional[str] = Query(None, description="Filter by likely root cause (BEARING_DEGRADATION, etc.)"),
    confidence: Optional[str] = Query(None, description="Filter by confidence (HIGH, MEDIUM, LOW)"),
    incident_id: Optional[str] = Query(None, description="Filter by incident ID"),
    start_time: Optional[datetime] = Query(None, description="Filter records starting from timestamp"),
    end_time: Optional[datetime] = Query(None, description="Filter records up to timestamp"),
    limit: int = Query(50, ge=1, le=500, description="Max diagnostics to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    """
    Retrieves historical root cause analysis diagnostic reports with flexible filtering.
    """
    query = db.query(DiagnosticModel)
    if machine_id:
        query = query.filter(DiagnosticModel.machine_id == machine_id)
    if likely_cause:
        query = query.filter(DiagnosticModel.likely_cause == likely_cause.upper())
    if confidence:
        query = query.filter(DiagnosticModel.confidence == confidence.upper())
    if incident_id:
        query = query.filter(DiagnosticModel.incident_id == incident_id)
    if start_time:
        query = query.filter(DiagnosticModel.timestamp >= start_time)
    if end_time:
        query = query.filter(DiagnosticModel.timestamp <= end_time)

    records = query.order_by(desc(DiagnosticModel.timestamp)).offset(offset).limit(limit).all()
    return records


@router.get("/{diagnostic_id}", response_model=Diagnostic, status_code=status.HTTP_200_OK)
def get_diagnostic_detail(diagnostic_id: str, db: Session = Depends(get_db)):
    """
    Retrieves a single root cause analysis report by its unique diagnostic ID or database ID.
    """
    # Allow lookup by string diagnostic_id (e.g. RCA-M01-...) or numeric id
    record = None
    if diagnostic_id.isdigit():
        record = db.query(DiagnosticModel).filter_by(id=int(diagnostic_id)).first()
    if not record:
        record = db.query(DiagnosticModel).filter_by(diagnostic_id=diagnostic_id).first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic report '{diagnostic_id}' not found"
        )
    return record


@router.post("/analyze", response_model=DiagnosticAnalysisResponse, status_code=status.HTTP_200_OK)
def analyze_root_cause(
    request: DiagnosticAnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    Executes on-demand or incident-level Root Cause Analysis for a machine.
    Synthesizes dependency graph paths, physical consistency checks, temporal sequence order,
    and multi-source evidence fusion.
    """
    machine = db.query(MachineModel).filter_by(id=request.machine_id).first()
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine '{request.machine_id}' is not registered"
        )

    engine = get_rca_engine()
    try:
        report = engine.analyze_machine(
            machine_id=request.machine_id,
            db=db,
            incident_id=request.incident_id,
            start_time=request.start_time,
            end_time=request.end_time,
            window_size=request.window_size or 30,
            persist=request.persist
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Root Cause Analysis execution failed: {str(exc)}"
        )

    return DiagnosticAnalysisResponse(
        diagnostic_id=report.diagnostic_id,
        machine_id=report.machine_id,
        incident_id=report.incident_id,
        timestamp=report.timestamp,
        likely_cause=report.likely_cause,
        evidence_score=report.evidence_score,
        confidence=report.confidence,
        ranking=report.ranking,
        evidence_summary=report.evidence_summary,
        text_report=report.text_report,
        metadata_info=report.metadata_info,
    )
