"""
NEXUS Telemetry Ingestion API Endpoints
Receives, validates, deduplicates, and stores operational telemetry with strict provenance tagging.
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc

from database.session import get_db
from database.models.models import TelemetryModel, MachineModel
from services.schemas import (
    Telemetry,
    TelemetryCreate,
    BatchIngestionResult,
    IngestionItemStatus,
)
from services.ingestion.pipeline import get_ingestion_service
from services.ingestion.validator import TelemetryValidationError

router = APIRouter(prefix="/telemetry", tags=["Telemetry"])


@router.post("", response_model=Telemetry, status_code=status.HTTP_201_CREATED)
def ingest_telemetry(payload: TelemetryCreate, db: Session = Depends(get_db)):
    """
    Ingest a single telemetry frame.
    Validates machine registration and physical bounds, handles deduplication,
    persists record, and updates the Digital Twin.
    """
    machine = db.query(MachineModel).filter(MachineModel.id == payload.machine_id).first()
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cannot ingest telemetry: Machine '{payload.machine_id}' is not registered."
        )

    service = get_ingestion_service()
    result = service.ingest(payload, db)

    if result.status == IngestionItemStatus.REJECTED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.message
        )

    # If duplicate, retrieve existing record
    if result.is_duplicate and result.idempotency_hash:
        existing = db.query(TelemetryModel).filter_by(idempotency_hash=result.idempotency_hash).first()
        if existing:
            return existing

    record = db.query(TelemetryModel).filter_by(id=result.telemetry_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve persisted telemetry record"
        )
    return record


@router.post("/batch", response_model=BatchIngestionResult, status_code=status.HTTP_200_OK)
def ingest_telemetry_batch(
    payloads: List[TelemetryCreate],
    db: Session = Depends(get_db)
):
    """
    Ingests a batch of telemetry records with partial acceptance support.
    Valid records are committed and persisted; invalid records or duplicates are reported.
    """
    service = get_ingestion_service()
    return service.ingest_batch(payloads, db)


@router.get("/{machine_id}/latest", response_model=Telemetry)
def get_latest_telemetry(machine_id: str, db: Session = Depends(get_db)):
    """Retrieve the most recent telemetry packet for a specific machine."""
    latest = (
        db.query(TelemetryModel)
        .filter(TelemetryModel.machine_id == machine_id)
        .order_by(desc(TelemetryModel.timestamp))
        .first()
    )
    if not latest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No telemetry found for machine '{machine_id}'"
        )
    return latest


@router.get("/{machine_id}", response_model=List[Telemetry])
def query_machine_telemetry(
    machine_id: str,
    start_time: Optional[datetime] = Query(None, description="Start timestamp filter (ISO 8601)"),
    end_time: Optional[datetime] = Query(None, description="End timestamp filter (ISO 8601)"),
    limit: int = Query(100, ge=1, le=1000, description="Max telemetry records to return"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order: 'asc' or 'desc'"),
    db: Session = Depends(get_db)
):
    """
    Queries historical time-series telemetry for a specific machine with range and ordering filters.
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
