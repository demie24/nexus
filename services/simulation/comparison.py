"""
NEXUS Multi-Scenario Comparison & Matrix Evaluator
Evaluates multiple counterfactual scenarios side-by-side branched from the same snapshot.
Provides an objective evidence comparison matrix without automatic action ranking.
"""

from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional, Any
import uuid
from sqlalchemy.orm import Session

from services.schemas import (
    ScenarioCompareRequest,
    ScenarioCompareResponse,
    WhatIfSimulationRequest,
    WhatIfSimulationResponse,
    CounterfactualScenarioType,
)
from services.simulation.counterfactual import get_what_if_engine, WhatIfSimulationEngine
from services.simulation.snapshot import get_snapshot_manager, DigitalTwinSnapshotManager

logger = logging.getLogger("nexus.simulation.comparison")


class ScenarioComparisonEngine:
    """
    Orchestrates fair, multi-branch scenario comparison starting from an identical snapshot.
    """

    def __init__(
        self,
        engine: Optional[WhatIfSimulationEngine] = None,
        snapshot_manager: Optional[DigitalTwinSnapshotManager] = None
    ):
        self.engine = engine or get_what_if_engine()
        self.snapshot_manager = snapshot_manager or get_snapshot_manager()

    def compare(
        self,
        request: ScenarioCompareRequest,
        db: Optional[Session] = None
    ) -> ScenarioCompareResponse:
        """
        Executes and compiles side-by-side comparison for multiple intervention scenarios.
        Guarantees that all branches execute from the exact same snapshot.
        """
        # 1. Acquire or create shared snapshot
        if request.snapshot_id:
            snapshot = self.snapshot_manager.get_snapshot(request.snapshot_id, db=db)
            if not snapshot:
                raise ValueError(f"Snapshot '{request.snapshot_id}' not found.")
        else:
            snapshot = self.snapshot_manager.create_snapshot(db=db)

        # 2. Build scenario request list
        scenarios_to_run: List[WhatIfSimulationRequest] = []

        if request.scenarios:
            scenarios_to_run = list(request.scenarios)
        else:
            # Default standard evaluation suite: DO_NOTHING, Load -20%, Load -40%, Cooling Boost, Emergency Stop
            scenarios_to_run = [
                WhatIfSimulationRequest(
                    machine_id=request.machine_id,
                    scenario_type=CounterfactualScenarioType.DO_NOTHING,
                    parameters={},
                    horizon_hours=request.horizon_hours,
                    seed=request.seed,
                    snapshot_id=snapshot.snapshot_id,
                    persist=request.persist
                ),
                WhatIfSimulationRequest(
                    machine_id=request.machine_id,
                    scenario_type=CounterfactualScenarioType.LOAD_MODULATION,
                    parameters={"load_reduction": 0.20},
                    horizon_hours=request.horizon_hours,
                    seed=request.seed,
                    snapshot_id=snapshot.snapshot_id,
                    persist=request.persist
                ),
                WhatIfSimulationRequest(
                    machine_id=request.machine_id,
                    scenario_type=CounterfactualScenarioType.LOAD_MODULATION,
                    parameters={"load_reduction": 0.40},
                    horizon_hours=request.horizon_hours,
                    seed=request.seed,
                    snapshot_id=snapshot.snapshot_id,
                    persist=request.persist
                ),
                WhatIfSimulationRequest(
                    machine_id=request.machine_id,
                    scenario_type=CounterfactualScenarioType.COOLING_BOOST,
                    parameters={"cooling_multiplier": 1.25},
                    horizon_hours=request.horizon_hours,
                    seed=request.seed,
                    snapshot_id=snapshot.snapshot_id,
                    persist=request.persist
                ),
                WhatIfSimulationRequest(
                    machine_id=request.machine_id,
                    scenario_type=CounterfactualScenarioType.EMERGENCY_STOP,
                    parameters={},
                    horizon_hours=request.horizon_hours,
                    seed=request.seed,
                    snapshot_id=snapshot.snapshot_id,
                    persist=request.persist
                ),
            ]

        # Ensure DO_NOTHING is present for baseline comparison
        has_baseline = any(s.scenario_type == CounterfactualScenarioType.DO_NOTHING for s in scenarios_to_run)
        if not has_baseline:
            scenarios_to_run.insert(
                0,
                WhatIfSimulationRequest(
                    machine_id=request.machine_id,
                    scenario_type=CounterfactualScenarioType.DO_NOTHING,
                    parameters={},
                    horizon_hours=request.horizon_hours,
                    seed=request.seed,
                    snapshot_id=snapshot.snapshot_id,
                    persist=request.persist
                )
            )

        # 3. Execute all branches from identical snapshot
        responses: List[WhatIfSimulationResponse] = []
        for scen_req in scenarios_to_run:
            scen_req.snapshot_id = snapshot.snapshot_id
            scen_req.seed = request.seed
            scen_resp = self.engine.run_simulation(scen_req, db=db, snapshot=snapshot)
            responses.append(scen_resp)

        # 4. Construct comparison matrix
        baseline_resp = next(r for r in responses if r.scenario == CounterfactualScenarioType.DO_NOTHING)
        matrix: List[Dict[str, Any]] = []

        for r in responses:
            is_baseline = (r.scenario == CounterfactualScenarioType.DO_NOTHING)
            risk_pp = 0.0
            if r.baseline_comparison:
                risk_pp = r.baseline_comparison.risk_delta_percentage_points

            throughput_loss_pct = 0.0
            if r.baseline_comparison:
                throughput_loss_pct = r.baseline_comparison.throughput_loss_pct

            row = {
                "scenario": r.scenario.value,
                "parameters": r.parameters,
                "rul_hours": r.result.final_rul,
                "rul_delta_vs_baseline_hours": r.baseline_comparison.rul_delta_hours if r.baseline_comparison else 0.0,
                "failure_risk_pct": round(r.result.final_failure_probability * 100.0, 1),
                "risk_delta_percentage_points": risk_pp,
                "total_output_units": r.result.total_output,
                "throughput_loss_vs_baseline_pct": throughput_loss_pct,
                "peak_temperature_c": r.result.peak_temperature,
                "peak_vibration_mms": r.result.peak_vibration,
                "downtime_hours": r.result.downtime,
                "recovery_time_hours": r.result.recovery_time,
                "affected_cascade_machines": r.affected_cascade_machines,
            }
            matrix.append(row)

        comp_id = f"COMP-{request.machine_id}-{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc)

        return ScenarioCompareResponse(
            comparison_id=comp_id,
            snapshot_id=snapshot.snapshot_id,
            machine_id=request.machine_id,
            horizon_hours=request.horizon_hours,
            scenarios=responses,
            matrix=matrix,
            created_at=now
        )


_global_comparison_engine: Optional[ScenarioComparisonEngine] = None


def get_comparison_engine() -> ScenarioComparisonEngine:
    global _global_comparison_engine
    if _global_comparison_engine is None:
        _global_comparison_engine = ScenarioComparisonEngine()
    return _global_comparison_engine
