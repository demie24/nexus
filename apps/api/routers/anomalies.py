"""
NEXUS Anomaly Detection API Endpoints
Provides querying, detailed inspection, real-time status, and on-demand analysis of industrial anomalies.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.session import get_db
from database.models.models import AnomalyModel, MachineModel
from services.schemas import (
    Anomaly,
    AnomalyCreate,
    TelemetryCreate,
    AnomalyAnalysisResponse,
    MachineAnomalyStatus,
)
from services.anomaly.engine import get_anomaly_engine

router = APIRouter(prefix="/anomalies", tags=["Anomaly Detection"])


@router.get("", response_model=List[Anomaly], status_code=status.HTTP_200_OK)
def list_anomalies(
    machine_id: Optional[str] = Query(None, description="Filter by machine ID"),
    severity: Optional[str] = Query(None, description="Filter by severity (LOW, MEDIUM, HIGH, CRITICAL)"),
    anomaly_type: Optional[str] = Query(None, description="Filter by anomaly type"),
    resolved: Optional[bool] = Query(None, description="Filter by resolved status"),
    limit: int = Query(50, ge=1, le=500, description="Max anomalies to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    """
    Retrieves historical and active anomaly records with flexible filtering.
    """
    query = db.query(AnomalyModel)
    if machine_id:
        query = query.filter(AnomalyModel.machine_id == machine_id)
    if severity:
        query = query.filter(AnomalyModel.severity == severity.upper())
    if anomaly_type:
        query = query.filter(AnomalyModel.anomaly_type == anomaly_type.upper())
    if resolved is not None:
        query = query.filter(AnomalyModel.resolved == resolved)

    records = query.order_by(desc(AnomalyModel.timestamp)).offset(offset).limit(limit).all()
    return records


@router.get("/{anomaly_id}", response_model=Anomaly, status_code=status.HTTP_200_OK)
def get_anomaly_detail(anomaly_id: int, db: Session = Depends(get_db)):
    """
    Retrieves complete details, evidence breakdown, and explanation for an anomaly record.
    """
    record = db.query(AnomalyModel).filter_by(id=anomaly_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anomaly record #{anomaly_id} not found"
        )
    return record


@router.post("/analyze", response_model=AnomalyAnalysisResponse, status_code=status.HTTP_200_OK)
def analyze_telemetry_frame(
    telemetry: TelemetryCreate,
    persist: bool = Query(True, description="Whether to persist if an anomaly is detected"),
    db: Session = Depends(get_db)
):
    """
    Executes on-demand multi-layered anomaly analysis on an incoming telemetry frame.
    Returns unified score, classification, explainability evidence, and component latencies.
    """
    machine = db.query(MachineModel).filter_by(id=telemetry.machine_id).first()
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine '{telemetry.machine_id}' is not registered in registry"
        )

    engine = get_anomaly_engine()
    result = engine.analyze(telemetry, db, persist_if_detected=persist)
    return result
