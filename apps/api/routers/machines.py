"""
NEXUS Machine Registry & Digital Twin State Endpoints
Handles querying and registering industrial assets, inspecting Digital Twin states,
and querying machine time-series telemetry.
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc

from database.session import get_db
from database.models.models import MachineModel, TelemetryModel, AnomalyModel, PredictionModel, MachineStateModel
from services.schemas import (
    Machine,
    MachineCreate,
    DigitalTwinState,
    Telemetry,
    Anomaly,
    MachineAnomalyStatus,
    Prediction,
    RiskForecastResponse,
    RULResponse,
)
from services.digital_twin.engine import get_digital_twin_engine
from services.anomaly.engine import get_anomaly_engine
from services.prediction.engine import get_prediction_engine

router = APIRouter(prefix="/machines", tags=["Machines"])


@router.get("", response_model=List[Machine])
def list_machines(db: Session = Depends(get_db)):
    """Retrieve all registered machines across all production lines."""
    machines = db.query(MachineModel).all()
    return machines


@router.get("/states", response_model=List[DigitalTwinState])
def get_all_machine_states(db: Session = Depends(get_db)):
    """
    Retrieve current Digital Twin operational states for all registered machines.
    Dynamically assesses data freshness (FRESH vs STALE).
    """
    dt_engine = get_digital_twin_engine()
    return dt_engine.get_all_machine_states(db)


@router.get("/{machine_id}", response_model=Machine)
def get_machine(machine_id: str, db: Session = Depends(get_db)):
    """Retrieve machine metadata by unique machine ID."""
    machine = db.query(MachineModel).filter(MachineModel.id == machine_id).first()
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine '{machine_id}' not found in registry"
        )
    return machine


@router.get("/{machine_id}/state", response_model=DigitalTwinState)
def get_machine_state(machine_id: str, db: Session = Depends(get_db)):
    """
    Retrieve current Digital Twin state for a specific machine.
    Dynamically computes freshness status and health metrics.
    """
    dt_engine = get_digital_twin_engine()
    state = dt_engine.get_machine_state(machine_id, db)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine '{machine_id}' not found in registry"
        )
    return state


@router.get("/{machine_id}/telemetry", response_model=List[Telemetry])
def get_machine_telemetry_series(
    machine_id: str,
    start_time: Optional[datetime] = Query(None, description="Start timestamp filter (ISO 8601)"),
    end_time: Optional[datetime] = Query(None, description="End timestamp filter (ISO 8601)"),
    limit: int = Query(100, ge=1, le=1000, description="Max telemetry records to return"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order: 'asc' or 'desc'"),
    db: Session = Depends(get_db)
):
    """
    Retrieves historical time-series telemetry records for a specific machine.
    Supports start_time, end_time, limit, and ordering filters.
    """
    machine = db.query(MachineModel).filter(MachineModel.id == machine_id).first()
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine '{machine_id}' not found in registry"
        )

    query = db.query(TelemetryModel).filter(TelemetryModel.machine_id == machine_id)
    if start_time:
        query = query.filter(TelemetryModel.timestamp >= start_time)
    if end_time:
        query = query.filter(TelemetryModel.timestamp <= end_time)

    if order == "asc":
        query = query.order_by(asc(TelemetryModel.timestamp))
    else:
        query = query.order_by(desc(TelemetryModel.timestamp))

    return query.limit(limit).all()


@router.get("/{machine_id}/anomalies", response_model=List[Anomaly])
def get_machine_anomalies(
    machine_id: str,
    resolved: Optional[bool] = Query(None, description="Filter by resolved status"),
    limit: int = Query(50, ge=1, le=500, description="Max anomalies to return"),
    db: Session = Depends(get_db)
):
    """Retrieves anomaly history for a specific machine."""
    machine = db.query(MachineModel).filter(MachineModel.id == machine_id).first()
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine '{machine_id}' not found in registry"
        )
    query = db.query(AnomalyModel).filter(AnomalyModel.machine_id == machine_id)
    if resolved is not None:
        query = query.filter(AnomalyModel.resolved == resolved)
    return query.order_by(desc(AnomalyModel.timestamp)).limit(limit).all()


@router.get("/{machine_id}/anomaly-status", response_model=MachineAnomalyStatus)
def get_machine_anomaly_status(machine_id: str, db: Session = Depends(get_db)):
    """Retrieves real-time active anomaly status, baseline health, and latest severity for a machine."""
    machine = db.query(MachineModel).filter(MachineModel.id == machine_id).first()
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine '{machine_id}' not found in registry"
        )
    engine = get_anomaly_engine()
    return engine.get_machine_anomaly_status(machine_id, db)


@router.post("", response_model=Machine, status_code=status.HTTP_201_CREATED)
def register_machine(machine_in: MachineCreate, db: Session = Depends(get_db)):
    """Register a new machine in the industrial registry."""
    existing = db.query(MachineModel).filter(MachineModel.id == machine_in.id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Machine '{machine_in.id}' already exists"
        )
    new_machine = MachineModel(**machine_in.model_dump())
    db.add(new_machine)
    db.commit()
    db.refresh(new_machine)
    return new_machine


@router.get("/{machine_id}/predictions", response_model=List[Prediction])
def get_machine_predictions(
    machine_id: str,
    limit: int = Query(50, ge=1, le=500, description="Max predictions to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    """Retrieves prediction history for a specific machine."""
    machine = db.query(MachineModel).filter(MachineModel.id == machine_id).first()
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine '{machine_id}' not found in registry"
        )
    return (
        db.query(PredictionModel)
        .filter(PredictionModel.machine_id == machine_id)
        .order_by(desc(PredictionModel.timestamp))
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/{machine_id}/risk-forecast", response_model=RiskForecastResponse)
def get_machine_risk_forecast(machine_id: str, db: Session = Depends(get_db)):
    """Retrieves real-time multi-horizon failure risk forecast for a machine."""
    machine = db.query(MachineModel).filter(MachineModel.id == machine_id).first()
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine '{machine_id}' not found in registry"
        )
    state = db.query(MachineStateModel).filter_by(machine_id=machine_id).first()
    curr_health = state.health_score if state else 100.0

    engine = get_prediction_engine()
    analysis = engine.predict(machine_id=machine_id, current_health=curr_health)
    return analysis.risk_forecast


@router.get("/{machine_id}/rul", response_model=RULResponse)
def get_machine_rul(machine_id: str, db: Session = Depends(get_db)):
    """Retrieves remaining useful life (RUL) estimation with uncertainty bounds for a machine."""
    machine = db.query(MachineModel).filter(MachineModel.id == machine_id).first()
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine '{machine_id}' not found in registry"
        )
    state = db.query(MachineStateModel).filter_by(machine_id=machine_id).first()
    curr_health = state.health_score if state else 100.0

    engine = get_prediction_engine()
    analysis = engine.predict(machine_id=machine_id, current_health=curr_health)
    return analysis.rul
