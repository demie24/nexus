"""
Simulator API Endpoints
Enables programmatic inspection and control of the Virtual Factory simulation environment.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from services.simulation.engine import get_simulator
from services.simulation.scenarios import ScenarioType
from services.schemas import Telemetry

router = APIRouter(prefix="/simulator", tags=["Simulator"])


class TriggerScenarioRequest(BaseModel):
    scenario_type: ScenarioType
    machine_id: str = Field(..., description="Target machine ID (e.g. M01-M06)")
    severity: float = Field(default=0.75, ge=0.1, le=1.0)
    duration_sim_seconds: float = Field(default=300.0, ge=10.0)
    parameters: Optional[Dict[str, Any]] = None


class StepSimulationRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=100)
    dt_seconds: float = Field(default=1.0, ge=0.1, le=60.0)


@router.get("/status")
def get_simulator_status():
    """Returns runtime state, clock dilation, and metrics for the Virtual Factory."""
    sim = get_simulator()
    return sim.get_status()


@router.get("/machines")
def list_simulated_machines():
    """Returns current operational status and health of all virtual machines."""
    sim = get_simulator()
    return sim.get_machines_summary()


@router.get("/scenarios")
def list_active_scenarios():
    """Lists currently active abnormal failure scenarios."""
    sim = get_simulator()
    return [scen.to_dict() for scen in sim.active_scenarios.values()]


@router.post("/scenarios/trigger", status_code=status.HTTP_201_CREATED)
def trigger_scenario(payload: TriggerScenarioRequest):
    """Triggers an abnormal or failure scenario on a simulated machine."""
    sim = get_simulator()
    try:
        instance = sim.trigger_scenario(
            scenario_type=payload.scenario_type,
            machine_id=payload.machine_id,
            severity=payload.severity,
            duration_sim_seconds=payload.duration_sim_seconds,
            parameters=payload.parameters
        )
        return instance.to_dict()
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post("/scenarios/{scenario_id}/recover")
def recover_scenario(scenario_id: str):
    """Triggers recovery or maintenance for an active scenario."""
    sim = get_simulator()
    success = sim.recover_scenario(scenario_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active scenario '{scenario_id}' not found"
        )
    return {"message": f"Scenario '{scenario_id}' recovery initiated."}


@router.post("/scenarios/{scenario_id}/stop")
def stop_scenario(scenario_id: str):
    """Forces immediate cessation of an active scenario."""
    sim = get_simulator()
    success = sim.stop_scenario(scenario_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active scenario '{scenario_id}' not found"
        )
    return {"message": f"Scenario '{scenario_id}' stopped."}


@router.post("/step", response_model=List[Telemetry])
def step_simulation(payload: StepSimulationRequest):
    """Advances simulation clock by specified steps and returns generated telemetry frames."""
    sim = get_simulator()
    all_telemetries = []
    for _ in range(payload.count):
        batch = sim.step(payload.dt_seconds)
        all_telemetries.extend(batch)
    return all_telemetries
