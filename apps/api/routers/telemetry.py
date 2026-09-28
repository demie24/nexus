"""
NEXUS Telemetry Ingestion API Endpoints
Receives and stores operational telemetry with strict validation and provenance tagging.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.session import get_db
from database.models.models import TelemetryModel, MachineModel
from services.schemas import Telemetry, TelemetryCreate

router = APIRouter(prefix="/telemetry", tags=["Telemetry"])


@router.post("", response_model=Telemetry, status_code=status.HTTP_201_CREATED)
def ingest_telemetry(payload: TelemetryCreate, db: Session = Depends(get_db)):
    """
    Ingest a telemetry packet. Validates machine registration and sensor bounds.
    """
    machine = db.query(MachineModel).filter(MachineModel.id == payload.machine_id).first()
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cannot ingest telemetry: Machine '{payload.machine_id}' is not registered."
        )

    # Convert Pydantic model to SQLAlchemy model
    telemetry_data = payload.model_dump()
    # Normalize provenance enum to string
    telemetry_data["provenance"] = payload.provenance.value if hasattr(payload.provenance, "value") else str(payload.provenance)

    record = TelemetryModel(**telemetry_data)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


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
