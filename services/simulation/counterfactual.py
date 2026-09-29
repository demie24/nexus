"""
NEXUS What-If Counterfactual Simulation Engine
Executes isolated, physics-grounded counterfactual simulations branched from immutable Digital Twin snapshots.
Evaluates interventions, tracks outcome metrics, enforces determinism, and computes baseline comparisons.
"""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import logging
import math
from typing import Dict, List, Optional, Any, Tuple
import uuid
import numpy as np
from sqlalchemy.orm import Session

from database.models.models import SimulationModel
from services.schemas import (
    CounterfactualScenarioType,
    SimulationStatus,
    OutcomeMetrics,
    BaselineComparison,
    WhatIfSimulationRequest,
    WhatIfSimulationResponse,
    DigitalTwinSnapshot,
    DataProvenance,
    OperatingStatus,
)
from services.simulation.config import get_default_factory_spec, MachineSpec, FactorySpec
from services.simulation.machine import SimulatedMachine
from services.simulation.snapshot import get_snapshot_manager, DigitalTwinSnapshotManager
from services.simulation.cascade import MultiMachineCascadeAnalyzer
from services.simulation.metrics import validate_metrics_sanity, build_baseline_comparison, SimulationSanityError

logger = logging.getLogger("nexus.simulation.counterfactual")

ENGINE_VERSION = "v1.0.0"
PHYSICS_MODEL_VERSION = "v2.0.0-thermo-mechanical"
SCENARIO_VERSION = "v1.0.0"


class WhatIfSimulationEngine:
    """
    Core engine orchestrating counterfactual What-If simulations on forked sandbox machines.
    """

    def __init__(
        self,
        snapshot_manager: Optional[DigitalTwinSnapshotManager] = None,
        factory_spec: Optional[FactorySpec] = None,
    ):
        self.snapshot_manager = snapshot_manager or get_snapshot_manager()
        self.factory_spec = factory_spec or get_default_factory_spec()
        self.cascade_analyzer = MultiMachineCascadeAnalyzer(self.factory_spec)

    def validate_request(self, request: WhatIfSimulationRequest) -> None:
        """
        Validates scenario parameters. Rejects invalid configurations with controlled ValueError.
        """
        spec = self.factory_spec.get_machine(request.machine_id)
        if not spec:
            raise ValueError(f"Machine '{request.machine_id}' is not registered in the factory topology.")

        if request.horizon_hours <= 0.0 or request.horizon_hours > 48.0:
            raise ValueError(f"Horizon hours must be between 0.5 and 48.0 hours. Got {request.horizon_hours}.")

        params = request.parameters or {}

        if request.scenario_type == CounterfactualScenarioType.LOAD_MODULATION:
            load_reduction = params.get("load_reduction", 0.20)
            if not isinstance(load_reduction, (int, float)) or load_reduction < 0.0 or load_reduction > 1.0:
                raise ValueError(f"load_reduction must be a float between 0.0 and 1.0. Got {load_reduction}.")

        elif request.scenario_type == CounterfactualScenarioType.COOLING_BOOST:
            cooling_mult = params.get("cooling_multiplier", 1.25)
            if not isinstance(cooling_mult, (int, float)) or cooling_mult <= 0.0:
                raise ValueError(f"cooling_multiplier must be a positive number > 0. Got {cooling_mult}.")

        elif request.scenario_type == CounterfactualScenarioType.SCHEDULED_SHUTDOWN:
            delay = params.get("shutdown_delay_hours", request.horizon_hours / 2.0)
            if not isinstance(delay, (int, float)) or delay < 0.0 or delay > request.horizon_hours:
                raise ValueError(
                    f"shutdown_delay_hours must be between 0.0 and horizon ({request.horizon_hours}h). Got {delay}."
                )

    def _fork_machine_from_state(
        self,
        spec: MachineSpec,
        state: Dict[str, Any],
        seed: int
    ) -> Tuple[SimulatedMachine, float, float]:
        """
        Constructs an isolated, sandboxed SimulatedMachine strictly calibrated to the snapshot state.
        Returns (machine, initial_bearing_deg, initial_cooling_deg).
        """
        rng = np.random.default_rng(seed)
        machine = SimulatedMachine(spec=spec, rng=rng)
        machine.sensor_noise_enabled = False  # Deterministic counterfactual trajectory

        # Calibrate state
        curr_load = float(state.get("load_factor", 1.0))
        machine.current_load = curr_load
        machine.internal_temperature = float(state.get("temperature", spec.nominal_temp_c))

        # Estimate internal degradation levels from snapshot telemetry
        obs_vib = float(state.get("vibration", spec.nominal_vib_mms))
        base_vib = spec.nominal_vib_mms * (0.85 + 0.30 * curr_load)
        vib_excess = max(0.0, obs_vib - base_vib)
        inferred_bearing_deg = min(1.0, math.sqrt(vib_excess / 8.5))

        # Reconcile with health score if available
        health_score = float(state.get("health_score", 100.0))
        if health_score < 95.0:
            penalty_deg = (100.0 - health_score) / 55.0
            inferred_bearing_deg = max(inferred_bearing_deg, min(0.95, penalty_deg))

        # Inferred cooling degradation from thermal excess
        exp_temp = spec.nominal_temp_c * (curr_load ** 1.3) * (1.0 + 0.35 * inferred_bearing_deg)
        obs_temp = float(state.get("temperature", spec.nominal_temp_c))
        inferred_cooling_deg = 0.0
        if obs_temp > exp_temp + 2.0:
            ratio = obs_temp / max(exp_temp, 1.0)
            inferred_cooling_deg = max(0.0, min(0.95, (1.0 - 1.0 / ratio) / 0.75))

        machine.bearing_degradation = inferred_bearing_deg
        machine.cooling_degradation = inferred_cooling_deg

        # Operational status
        status_str = state.get("status", "OPERATING")
        try:
            machine.operating_status = OperatingStatus(status_str)
        except Exception:
            machine.operating_status = OperatingStatus.OPERATING

        return machine, inferred_bearing_deg, inferred_cooling_deg

    def _estimate_rul(
        self,
        machine: SimulatedMachine,
        wear_rate_per_sec: float,
        is_stopped: bool,
        elapsed_hours: float,
        initial_rul: Optional[float]
    ) -> float:
        """
        Estimates Remaining Useful Life (RUL) in hours until health hits critical failure (< 20.0 or wear > 0.85).
        """
        if machine.health_score <= 20.0:
            return 0.0

        if is_stopped:
            # When stopped, wear was frozen; RUL preserved minus any operation time
            if initial_rul is not None:
                return round(max(0.0, initial_rul - elapsed_hours), 2)
            return 48.0

        remaining_wear_margin = max(0.0, 0.85 - machine.bearing_degradation)
        if wear_rate_per_sec <= 1e-9 or remaining_wear_margin <= 0.0:
            return 0.0

        rul_hours = remaining_wear_margin / (wear_rate_per_sec * 3600.0)
        return round(float(min(48.0, max(0.0, rul_hours))), 2)

    def run_simulation(
        self,
        request: WhatIfSimulationRequest,
        db: Optional[Session] = None,
        snapshot: Optional[DigitalTwinSnapshot] = None,
    ) -> WhatIfSimulationResponse:
        """
        Executes a single counterfactual scenario on an isolated sandbox machine forked from snapshot.
        """
        # 1. Validation
        self.validate_request(request)

        # 2. Snapshot capture / retrieval
        if snapshot is None:
            if request.snapshot_id:
                snapshot = self.snapshot_manager.get_snapshot(request.snapshot_id, db=db)
                if not snapshot:
                    raise ValueError(f"Snapshot '{request.snapshot_id}' not found.")
            else:
                snapshot = self.snapshot_manager.create_snapshot(db=db)

        target_state = self.snapshot_manager.fork_machine_state(snapshot, request.machine_id)
        if not target_state:
            raise ValueError(f"Machine '{request.machine_id}' is not present in snapshot '{snapshot.snapshot_id}'.")

        spec = self.factory_spec.get_machine(request.machine_id)
        if not spec:
            raise ValueError(f"Machine spec '{request.machine_id}' not found.")

        # 3. Fork sandbox machine
        machine, initial_bearing_deg, initial_cooling_deg = self._fork_machine_from_state(
            spec, target_state, seed=request.seed
        )

        init_health = round(machine.health_score, 2)
        init_failure_prob = round(machine.failure_probability, 3)

        # Baseline nominal wear rate
        base_wear_rate = 2.5e-6  # calibrated degradation per second (realistic multi-hour progression)
        init_rul = self._estimate_rul(
            machine=machine,
            wear_rate_per_sec=base_wear_rate * (machine.current_load ** 1.5),
            is_stopped=(machine.operating_status in [OperatingStatus.SHUTDOWN, OperatingStatus.FAILED, OperatingStatus.IDLE]),
            elapsed_hours=0.0,
            initial_rul=None
        )

        # 4. Simulation horizon and step configuration
        horizon_seconds = request.horizon_hours * 3600.0
        dt_seconds = 60.0  # 1-minute discrete physical integration step
        total_steps = int(horizon_seconds / dt_seconds)

        params = request.parameters or {}
        scenario_type = request.scenario_type

        # Intervention parameters
        load_factor_mod = 1.0
        cooling_mult = 1.0
        shutdown_step = -1
        is_emergency = False
        recovery_time = None

        if scenario_type == CounterfactualScenarioType.LOAD_MODULATION:
            load_reduction = float(params.get("load_reduction", 0.20))
            load_factor_mod = max(0.0, min(1.0, 1.0 - load_reduction))
            machine.set_load(machine.current_load * load_factor_mod)

        elif scenario_type == CounterfactualScenarioType.COOLING_BOOST:
            cooling_mult = float(params.get("cooling_multiplier", 1.25))

        elif scenario_type == CounterfactualScenarioType.SCHEDULED_SHUTDOWN:
            delay_h = float(params.get("shutdown_delay_hours", request.horizon_hours / 2.0))
            shutdown_step = int((delay_h * 3600.0) / dt_seconds)
            recovery_time = 1.5

        elif scenario_type == CounterfactualScenarioType.EMERGENCY_STOP:
            is_emergency = True
            machine.set_load(0.0)
            machine.operating_status = OperatingStatus.SHUTDOWN
            recovery_time = 3.0

        # State tracking during simulation
        peak_temp = machine.internal_temperature
        t_ref = datetime(2026, 9, 29, 12, 0, 0, tzinfo=timezone.utc)
        peak_vib = machine.generate_telemetry(t_ref).vibration
        cumulative_output = 0.0
        downtime_seconds = 0.0

        sim_now = t_ref
        final_wear_rate = base_wear_rate

        # 5. Forward Simulation Loop
        for step in range(total_steps):
            # Check scheduled shutdown transition
            if shutdown_step >= 0 and step >= shutdown_step:
                machine.set_load(0.0)
                machine.operating_status = OperatingStatus.SHUTDOWN

            is_active = machine.operating_status not in [OperatingStatus.SHUTDOWN, OperatingStatus.FAILED, OperatingStatus.IDLE]

            if is_active:
                # Active thermal dissipation with optional cooling multiplier
                eff_cooling = max(0.15, (1.0 - 0.75 * machine.cooling_degradation) * cooling_mult)
                load_heat = machine.current_load ** 1.3
                bearing_heat = 1.0 + 0.35 * machine.bearing_degradation
                target_temp = spec.nominal_temp_c * load_heat * bearing_heat / eff_cooling

                # Advance thermal lag
                alpha = min(1.0, dt_seconds / 120.0)
                machine.internal_temperature += alpha * (target_temp - machine.internal_temperature)

                # Advance mechanical wear progression
                thermal_stress = math.exp(max(0.0, machine.internal_temperature - spec.nominal_temp_c) / 25.0)
                load_stress = machine.current_load ** 1.5
                wear_escalation = 1.0 + 2.0 * machine.bearing_degradation
                step_wear_rate = base_wear_rate * load_stress * thermal_stress * wear_escalation / max(0.5, cooling_mult)
                final_wear_rate = step_wear_rate

                machine.bearing_degradation = min(1.0, machine.bearing_degradation + step_wear_rate * dt_seconds)

                # Output rate accumulation
                # Output = nominal_rate * load * efficiency%
                eff = max(0.0, min(100.0, 100.0 - 28.0 * machine.bearing_degradation - 20.0 * machine.cooling_degradation))
                step_output = spec.nominal_output_rate * machine.current_load * (eff / 100.0) * (dt_seconds / 3600.0)
                cumulative_output += max(0.0, step_output)

            else:
                # Cooldown towards ambient 24C
                t_ambient = 24.0
                cooling_rate = 0.015 * dt_seconds
                machine.internal_temperature += (t_ambient - machine.internal_temperature) * min(1.0, cooling_rate)
                downtime_seconds += dt_seconds
                final_wear_rate = 0.0

            # Telemetry snapshot for vibration & sanity
            sim_now += np.timedelta64(int(dt_seconds), 's').astype(object)
            tel = machine.generate_telemetry(sim_now)

            peak_temp = max(peak_temp, machine.internal_temperature)
            peak_vib = max(peak_vib, tel.vibration)

        # 6. Final outcome metrics calculation
        final_health = round(machine.health_score, 2)
        final_fail_prob = round(machine.failure_probability, 3)
        final_rul = self._estimate_rul(
            machine=machine,
            wear_rate_per_sec=final_wear_rate,
            is_stopped=(machine.operating_status in [OperatingStatus.SHUTDOWN, OperatingStatus.FAILED]),
            elapsed_hours=request.horizon_hours,
            initial_rul=init_rul
        )

        nominal_expected_output = spec.nominal_output_rate * request.horizon_hours
        throughput_loss = round(
            max(0.0, (nominal_expected_output - cumulative_output) / max(nominal_expected_output, 1.0)),
            4
        )

        outcome = OutcomeMetrics(
            initial_health=init_health,
            final_health=final_health,
            health_delta=round(final_health - init_health, 2),
            initial_failure_probability=init_failure_prob,
            final_failure_probability=final_fail_prob,
            risk_delta=round(final_fail_prob - init_failure_prob, 3),
            initial_rul=init_rul,
            final_rul=final_rul,
            rul_delta=round(final_rul - init_rul, 2) if (final_rul is not None and init_rul is not None) else None,
            peak_temperature=round(float(peak_temp), 2),
            peak_vibration=round(float(peak_vib), 3),
            total_output=round(float(cumulative_output), 2),
            throughput_loss=throughput_loss,
            downtime=round(downtime_seconds / 3600.0, 2),
            recovery_time=recovery_time
        )

        # Enforce sanity checks
        validate_metrics_sanity(outcome)

        # 7. Multi-machine cascade evaluation
        is_shut = machine.operating_status in [OperatingStatus.SHUTDOWN, OperatingStatus.FAILED]
        avg_output_rate = cumulative_output / max(0.1, request.horizon_hours)
        cascade_report = self.cascade_analyzer.evaluate_cascade(
            target_machine_id=request.machine_id,
            simulated_output_rate=avg_output_rate,
            nominal_output_rate=spec.nominal_output_rate,
            is_shutdown=is_shut,
            all_machine_states=snapshot.machine_states
        )

        # 8. Baseline comparison against DO_NOTHING
        baseline_comp = None
        if scenario_type != CounterfactualScenarioType.DO_NOTHING:
            baseline_req = WhatIfSimulationRequest(
                machine_id=request.machine_id,
                scenario_type=CounterfactualScenarioType.DO_NOTHING,
                parameters={},
                horizon_hours=request.horizon_hours,
                seed=request.seed,
                snapshot_id=snapshot.snapshot_id,
                persist=False
            )
            # Run baseline under identical snapshot
            baseline_resp = self.run_simulation(baseline_req, db=db, snapshot=snapshot)
            baseline_comp = build_baseline_comparison(baseline_resp.result, outcome)
        else:
            # Self-comparison for baseline
            baseline_comp = build_baseline_comparison(outcome, outcome)

        # 9. Response construction
        sim_id = f"SIM-{request.machine_id}-{scenario_type.value[:4].upper()}-{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc)

        metadata_info = {
            "engine_version": ENGINE_VERSION,
            "physics_model_version": PHYSICS_MODEL_VERSION,
            "scenario_version": SCENARIO_VERSION,
            "random_seed": request.seed,
            "horizon_hours": request.horizon_hours,
            "sim_wall_clock_relation": "240 discrete 60s physical steps per 4h horizon; executed in memory",
            "state_hash": snapshot.state_hash,
            "target_machine_id": request.machine_id,
        }

        response = WhatIfSimulationResponse(
            simulation_id=sim_id,
            snapshot_id=snapshot.snapshot_id,
            machine_id=request.machine_id,
            scenario=scenario_type,
            parameters=params,
            horizon_hours=request.horizon_hours,
            status=SimulationStatus.COMPLETED,
            result=outcome,
            baseline_comparison=baseline_comp,
            affected_cascade_machines=cascade_report.get("affected_cascade_machines", []),
            cascade_impact=cascade_report,
            provenance=DataProvenance.SIMULATED,
            metadata_info=metadata_info,
            created_at=now
        )

        # 10. Persistence
        if request.persist and db is not None:
            try:
                db_record = SimulationModel(
                    simulation_id=response.simulation_id,
                    snapshot_id=response.snapshot_id,
                    scenario_name=f"{request.scenario_type.value}_{request.machine_id}",
                    target_machine_id=request.machine_id,
                    action_type=request.scenario_type.value,
                    status=response.status.value,
                    horizon_hours=response.horizon_hours,
                    parameters=request.parameters,
                    baseline_production_units=baseline_comp.baseline_output if baseline_comp else outcome.total_output,
                    simulated_production_units=outcome.total_output,
                    production_loss_pct=baseline_comp.throughput_loss_pct if baseline_comp else 0.0,
                    simulated_failure_probability=outcome.final_failure_probability,
                    risk_reduction_pct=baseline_comp.risk_reduction_pct or 0.0 if baseline_comp else 0.0,
                    affected_cascade_machines={"machines": response.affected_cascade_machines},
                    recovery_time_hours=outcome.recovery_time,
                    outcome_metrics=outcome.model_dump(),
                    baseline_comparison=baseline_comp.model_dump() if baseline_comp else {},
                    random_seed=request.seed,
                    state_hash=snapshot.state_hash,
                    provenance="SIMULATED",
                    created_at=now
                )
                db.add(db_record)
                db.commit()
            except Exception as err:
                db.rollback()
                logger.warning(f"Could not persist simulation record to DB: {err}")

        return response


_global_rca_simulation_engine: Optional[WhatIfSimulationEngine] = None


def get_what_if_engine() -> WhatIfSimulationEngine:
    global _global_rca_simulation_engine
    if _global_rca_simulation_engine is None:
        _global_rca_simulation_engine = WhatIfSimulationEngine()
    return _global_rca_simulation_engine
