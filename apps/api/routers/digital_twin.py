"""
NEXUS Digital Twin & Factory State API Endpoints
Provides system-level Digital Twin snapshots and holistic factory state evaluations.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database.session import get_db
from services.schemas import FactorySnapshot
from services.digital_twin.engine import get_digital_twin_engine
from services.simulation.engine import get_simulator

router = APIRouter(prefix="/factory", tags=["Digital Twin & Factory"])


@router.get("/state", response_model=FactorySnapshot, status_code=status.HTTP_200_OK)
def get_factory_state_snapshot(db: Session = Depends(get_db)):
    """
    Returns a unified Digital Twin snapshot for the factory.
    Aggregates operational health, counts of operating, degraded, high-risk, failed,
    and stale machinery, and includes all individual machine Digital Twin states.
    """
    dt_engine = get_digital_twin_engine()
    simulator = get_simulator()
    active_scenarios_count = len(simulator.active_scenarios) if simulator else 0
    return dt_engine.get_factory_snapshot(db, active_scenarios_count=active_scenarios_count)
