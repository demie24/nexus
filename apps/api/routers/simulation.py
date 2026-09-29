"""
NEXUS What-If Counterfactual Simulation API Endpoints
Provides on-demand scenario execution, comparative multi-scenario matrix evaluations,
and historical counterfactual simulation result queries.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.session import get_db
from database.models.models import SimulationModel, MachineModel
from services.schemas import (
    WhatIfSimulationRequest,
    WhatIfSimulationResponse,
    ScenarioCompareRequest,
    ScenarioCompareResponse,
    CounterfactualScenarioType,
    SimulationStatus,
)
from services.simulation.counterfactual import get_what_if_engine, WhatIfSimulationEngine
from services.simulation.comparison import get_comparison_engine, ScenarioComparisonEngine
from services.simulation.metrics import SimulationSanityError

router = APIRouter(prefix="/simulation", tags=["What-If Counterfactual Simulation"])


@router.get("/scenarios", status_code=status.HTTP_200_OK)
def list_available_scenarios():
    """
    Returns the catalog of supported counterfactual intervention scenarios and their configurable parameters.
    """
    return {
        "supported_scenarios": [
            {
                "type": CounterfactualScenarioType.DO_NOTHING.value,
                "name": "Do Nothing (Baseline)",
                "description": "Baseline degradation trajectory with no intervention. Used as the comparison anchor.",
                "parameters": {}
            },
            {
                "type": CounterfactualScenarioType.LOAD_MODULATION.value,
                "name": "Load Modulation",
                "description": "Reduces mechanical and electrical load to alleviate thermal and vibrational stress.",
                "parameters": {
                    "load_reduction": {
                        "type": "float",
                        "default": 0.20,
                        "min": 0.0,
                        "max": 1.0,
                        "description": "Fractional load reduction (e.g. 0.20 for 20% load cut)"
                    }
                }
            },
            {
                "type": CounterfactualScenarioType.COOLING_BOOST.value,
                "name": "Cooling Boost",
                "description": "Engages auxiliary cooling systems to lower operational temperature and retard thermal wear.",
                "parameters": {
                    "cooling_multiplier": {
                        "type": "float",
                        "default": 1.25,
                        "min": 0.5,
                        "description": "Multiplier on effective heat dissipation coefficient"
                    }
                }
            },
            {
                "type": CounterfactualScenarioType.SCHEDULED_SHUTDOWN.value,
                "name": "Scheduled Off-Peak Shutdown",
                "description": "Runs machine until a designated off-peak cutoff, followed by controlled shutdown and planned maintenance.",
                "parameters": {
                    "shutdown_delay_hours": {
                        "type": "float",
                        "description": "Hours from simulation start before initiating controlled shutdown"
                    }
                }
            },
            {
                "type": CounterfactualScenarioType.EMERGENCY_STOP.value,
                "name": "Immediate Emergency Stop",
                "description": "Immediately halts machine to protect hardware, resulting in full downtime and emergency inspection overhead.",
                "parameters": {}
            }
        ]
    }


@router.post("/what-if", response_model=WhatIfSimulationResponse, status_code=status.HTTP_200_OK)
def execute_what_if_simulation(
    request: WhatIfSimulationRequest,
    db: Session = Depends(get_db)
):
    """
    Executes a counterfactual What-If simulation branched from an immutable snapshot.
    Evaluates physical outcomes, multi-machine cascade effects, and baseline comparisons.
    """
    engine = get_what_if_engine()
    try:
        response = engine.run_simulation(request, db=db)
        return response
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except SimulationSanityError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation execution failed: {str(err)}"
        )


@router.post("/compare", response_model=ScenarioCompareResponse, status_code=status.HTTP_200_OK)
def compare_scenarios(
    request: ScenarioCompareRequest,
    db: Session = Depends(get_db)
):
    """
    Executes and compares multiple scenario branches against an identical Digital Twin snapshot.
    Generates an evidence-backed comparison matrix.
    """
    comparison_engine = get_comparison_engine()
    try:
        response = comparison_engine.compare(request, db=db)
        return response
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scenario comparison failed: {str(err)}"
        )


@router.get("/{simulation_id}", status_code=status.HTTP_200_OK)
def get_simulation_detail(simulation_id: str, db: Session = Depends(get_db)):
    """
    Retrieves metadata and status for a previously executed simulation.
    """
    record = None
    if simulation_id.isdigit():
        record = db.query(SimulationModel).filter_by(id=int(simulation_id)).first()
    if not record:
        record = db.query(SimulationModel).filter_by(simulation_id=simulation_id).first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation '{simulation_id}' not found."
        )

    return {
        "simulation_id": record.simulation_id,
        "snapshot_id": record.snapshot_id,
        "target_machine_id": record.target_machine_id,
        "action_type": record.action_type,
        "status": record.status,
        "horizon_hours": record.horizon_hours,
        "parameters": record.parameters,
        "state_hash": record.state_hash,
        "created_at": record.created_at,
        "provenance": record.provenance,
    }


@router.get("/{simulation_id}/results", status_code=status.HTTP_200_OK)
def get_simulation_results(simulation_id: str, db: Session = Depends(get_db)):
    """
    Retrieves full outcome metrics, baseline comparison, and cascade results for a simulation.
    """
    record = None
    if simulation_id.isdigit():
        record = db.query(SimulationModel).filter_by(id=int(simulation_id)).first()
    if not record:
        record = db.query(SimulationModel).filter_by(simulation_id=simulation_id).first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation '{simulation_id}' not found."
        )

    return {
        "simulation_id": record.simulation_id,
        "snapshot_id": record.snapshot_id,
        "target_machine_id": record.target_machine_id,
        "action_type": record.action_type,
        "status": record.status,
        "outcome_metrics": record.outcome_metrics,
        "baseline_comparison": record.baseline_comparison,
        "affected_cascade_machines": record.affected_cascade_machines,
        "provenance": record.provenance,
        "created_at": record.created_at,
    }
