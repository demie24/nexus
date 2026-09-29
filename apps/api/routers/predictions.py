"""
NEXUS Predictive Intelligence API Endpoints
Provides multi-horizon risk forecasts, RUL estimations, trajectory projections, and on-demand predictive analysis.
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.session import get_db
from database.models.models import PredictionModel, MachineModel, MachineStateModel
from services.schemas import (
    Prediction,
    PredictionAnalysisRequest,
    PredictionAnalysisResponse,
    RiskForecastResponse,
    RULResponse,
)
from services.prediction.engine import get_prediction_engine

router = APIRouter(prefix="/predictions", tags=["Predictive Intelligence"])


@router.get("", response_model=List[Prediction], status_code=status.HTTP_200_OK)
def list_predictions(
    machine_id: Optional[str] = Query(None, description="Filter by machine ID"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level (LOW, MEDIUM, HIGH, CRITICAL)"),
    prediction_status: Optional[str] = Query(None, description="Filter by status (ESTIMATED, INSUFFICIENT_DATA, etc.)"),
    start_time: Optional[datetime] = Query(None, description="Filter records starting from timestamp"),
    end_time: Optional[datetime] = Query(None, description="Filter records up to timestamp"),
    limit: int = Query(50, ge=1, le=500, description="Max predictions to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    """
    Retrieves historical prediction records with flexible filtering.
    """
    query = db.query(PredictionModel)
    if machine_id:
        query = query.filter(PredictionModel.machine_id == machine_id)
    if risk_level:
        query = query.filter(PredictionModel.risk_level == risk_level.upper())
    if prediction_status:
        query = query.filter(PredictionModel.prediction_status == prediction_status.upper())
    if start_time:
        query = query.filter(PredictionModel.timestamp >= start_time)
    if end_time:
        query = query.filter(PredictionModel.timestamp <= end_time)

    records = query.order_by(desc(PredictionModel.timestamp)).offset(offset).limit(limit).all()
    return records


@router.get("/{prediction_id}", response_model=Prediction, status_code=status.HTTP_200_OK)
def get_prediction_detail(prediction_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a single prediction record with its complete multi-horizon forecasts and explanation factors.
    """
    record = db.query(PredictionModel).filter_by(id=prediction_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prediction record #{prediction_id} not found"
        )
    return record


@router.post("/analyze", response_model=PredictionAnalysisResponse, status_code=status.HTTP_200_OK)
def analyze_machine_predictive_state(
    request: PredictionAnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    Executes on-demand predictive inference for a machine.
    Generates multi-horizon failure risk, projected health trajectory, RUL confidence interval, and explanatory factors.
    """
    machine = db.query(MachineModel).filter_by(id=request.machine_id).first()
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine '{request.machine_id}' is not registered"
        )

    # Fetch latest known health score from Digital Twin state
    state = db.query(MachineStateModel).filter_by(machine_id=request.machine_id).first()
    curr_health = state.health_score if state else 100.0

    engine = get_prediction_engine()
    horizon = request.horizon_minutes or 120
    analysis = engine.predict(
        machine_id=request.machine_id,
        current_health=curr_health,
        horizon_minutes=horizon
    )

    if request.persist:
        engine.persist_prediction(analysis, db)

    return analysis
