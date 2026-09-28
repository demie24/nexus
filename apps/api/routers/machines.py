"""
NEXUS Machine Registry Endpoints
Handles querying and registering industrial assets across production lines.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.session import get_db
from database.models.models import MachineModel
from services.schemas import Machine, MachineCreate

router = APIRouter(prefix="/machines", tags=["Machines"])


@router.get("", response_model=List[Machine])
def list_machines(db: Session = Depends(get_db)):
    """Retrieve all registered machines across all production lines."""
    machines = db.query(MachineModel).all()
    return machines


@router.get("/{machine_id}", response_model=Machine)
def get_machine(machine_id: str, db: Session = Depends(get_db)):
    """Retrieve machine details by unique machine ID."""
    machine = db.query(MachineModel).filter(MachineModel.id == machine_id).first()
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine '{machine_id}' not found in registry"
        )
    return machine


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
