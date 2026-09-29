"""
NEXUS Multi-Criteria Decision Engine Orchestrator
Coordinates evidence gathering (telemetry, predictive intelligence, root cause analysis),
executes isolated counterfactual scenario simulations, performs multi-attribute utility analysis,
enforces hard constraints, conducts sensitivity analysis, and persists auditable decisions.
"""

from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional, Any, Tuple
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.models.models import (
    DecisionModel,
    MachineModel,
    PredictionModel,
    AnomalyModel,
    DiagnosticModel,
)
from services.schemas import (
    DecisionAnalysisRequest,
    DecisionAnalysisResponse,
    DecisionEngineStatus,
    PolicyProfileType,
    CounterfactualScenarioType,
    CandidateActionEvaluation,
    RawCriteriaValues,
    ActionFeasibilityStatus,
    EvidenceReferences,
    DataProvenance,
    WhatIfSimulationRequest,
    WhatIfSimulationResponse,
)
from services.decision.config import (
    POLICY_PROFILES,
    DEFAULT_CONSTRAINTS,
    INTERVENTION_COST_MAP,
    ENGINE_VERSION,
    DECISION_RULE_VERSION,
)
from services.decision.criteria import normalize_weights, calculate_utilities
from services.decision.constraints import evaluate_action_feasibility
from services.decision.ranking import calculate_decision_score, rank_candidate_actions
from services.decision.sensitivity import run_sensitivity_analysis
from services.decision.explanation import (
    generate_candidate_trade_offs,
    generate_decision_narrative,
)
from services.simulation.config import get_default_factory_spec, FactorySpec
from services.simulation.counterfactual import get_what_if_engine, WhatIfSimulationEngine
from services.simulation.snapshot import get_snapshot_manager, DigitalTwinSnapshotManager

logger = logging.getLogger("nexus.decision.engine")


class DecisionEngine:
    """
    Core orchestrator of NEXUS Phase 8 Multi-Criteria Decision Analysis.
    Strictly deterministic and auditable. Operates as an advisory decision-support system.
    """

    def __init__(
        self,
        simulation_engine: Optional[WhatIfSimulationEngine] = None,
        snapshot_manager: Optional[DigitalTwinSnapshotManager] = None,
        factory_spec: Optional[FactorySpec] = None,
    ):
        self.simulation_engine = simulation_engine or get_what_if_engine()
        self.snapshot_manager = snapshot_manager or get_snapshot_manager()
        self.factory_spec = factory_spec or get_default_factory_spec()

    def analyze(
        self,
        request: DecisionAnalysisRequest,
        db: Optional[Session] = None,
    ) -> DecisionAnalysisResponse:
        """
        Executes a complete multi-criteria decision evaluation for the specified machine.
        """
        # 1. Machine existence verification
        spec = self.factory_spec.get_machine(request.machine_id)
        if not spec and db is not None:
            # Check database machine registry as fallback
            db_machine = db.query(MachineModel).filter(MachineModel.id == request.machine_id).first()
            if not db_machine:
                raise ValueError(f"Machine '{request.machine_id}' is not registered in the factory topology.")
        elif not spec:
            raise ValueError(f"Machine '{request.machine_id}' is not registered in the factory topology.")

        # 2. Resolve Criteria Weights & Operational Policy
        if request.custom_weights is not None:
            weights = normalize_weights(request.custom_weights)
            policy_profile = PolicyProfileType.CUSTOM
        else:
            profile_enum = request.policy_profile or PolicyProfileType.BALANCED
            raw_weights = POLICY_PROFILES.get(profile_enum, POLICY_PROFILES[PolicyProfileType.BALANCED])
            weights = normalize_weights(raw_weights)
            policy_profile = profile_enum

        # 3. Resolve Domain Constraints
        constraints = request.custom_constraints or DEFAULT_CONSTRAINTS

        # 4. Acquire Immutable Digital Twin Snapshot
        if request.snapshot_id:
            snapshot = self.snapshot_manager.get_snapshot(request.snapshot_id, db=db)
            if not snapshot:
                raise ValueError(f"Snapshot '{request.snapshot_id}' not found.")
        else:
            snapshot = self.snapshot_manager.create_snapshot(db=db)

        # 5. Define Candidate Counterfactual Scenarios
        # Minimum required actions: DO_NOTHING, LOAD_MODULATION (-20%, -40%), COOLING_BOOST, SCHEDULED_SHUTDOWN, EMERGENCY_STOP
        scenario_configs = [
            {
                "type": CounterfactualScenarioType.DO_NOTHING,
                "label": "Do Nothing (Baseline)",
                "params": {},
            },
            {
                "type": CounterfactualScenarioType.LOAD_MODULATION,
                "label": "Load Modulation (-20%)",
                "params": {"load_reduction": 0.20},
            },
            {
                "type": CounterfactualScenarioType.LOAD_MODULATION,
                "label": "Load Modulation (-40%)",
                "params": {"load_reduction": 0.40},
            },
            {
                "type": CounterfactualScenarioType.COOLING_BOOST,
                "label": "Cooling Boost (+25%)",
                "params": {"cooling_multiplier": 1.25},
            },
            {
                "type": CounterfactualScenarioType.SCHEDULED_SHUTDOWN,
                "label": "Scheduled Off-Peak Shutdown",
                "params": {"shutdown_delay_hours": round(request.horizon_hours / 2.0, 1)},
            },
            {
                "type": CounterfactualScenarioType.EMERGENCY_STOP,
                "label": "Immediate Emergency Stop",
                "params": {},
            },
        ]

        # 6. Execute Counterfactual Simulations Branched from Identical Snapshot
        sim_results: List[Tuple[Dict[str, Any], WhatIfSimulationResponse]] = []
        baseline_sim_resp: Optional[WhatIfSimulationResponse] = None

        for cfg in scenario_configs:
            sim_req = WhatIfSimulationRequest(
                machine_id=request.machine_id,
                scenario_type=cfg["type"],
                parameters=cfg["params"],
                horizon_hours=request.horizon_hours,
                seed=42,
                snapshot_id=snapshot.snapshot_id,
                persist=request.persist,
            )
            sim_resp = self.simulation_engine.run_simulation(sim_req, db=db, snapshot=snapshot)
            sim_results.append((cfg, sim_resp))
            if cfg["type"] == CounterfactualScenarioType.DO_NOTHING and baseline_sim_resp is None:
                baseline_sim_resp = sim_resp

        # 7. Collect Evidence References from Prior Phases
        prediction_id: Optional[str] = None
        diagnostic_id: Optional[str] = None
        anomaly_id: Optional[str] = None

        if db is not None:
            try:
                latest_pred = (
                    db.query(PredictionModel)
                    .filter(PredictionModel.machine_id == request.machine_id)
                    .order_by(desc(PredictionModel.created_at))
                    .first()
                )
                if latest_pred:
                    prediction_id = latest_pred.prediction_id

                latest_diag = (
                    db.query(DiagnosticModel)
                    .filter(DiagnosticModel.machine_id == request.machine_id)
                    .order_by(desc(DiagnosticModel.created_at))
                    .first()
                )
                if latest_diag:
                    diagnostic_id = latest_diag.diagnostic_id

                latest_anom = (
                    db.query(AnomalyModel)
                    .filter(AnomalyModel.machine_id == request.machine_id)
                    .order_by(desc(AnomalyModel.created_at))
                    .first()
                )
                if latest_anom:
                    anomaly_id = latest_anom.anomaly_id
            except Exception as e:
                logger.warning(f"Could not load historical evidence references from DB: {e}")

        evidence_refs = EvidenceReferences(
            snapshot_id=snapshot.snapshot_id,
            simulation_ids=[resp.simulation_id for _, resp in sim_results],
            prediction_id=prediction_id,
            diagnostic_id=diagnostic_id,
            anomaly_id=anomaly_id,
        )

        # 8. Extract Baseline Metrics for Comparative Analysis
        baseline_raw: Optional[RawCriteriaValues] = None
        if baseline_sim_resp:
            b_res = baseline_sim_resp.result
            baseline_raw = RawCriteriaValues(
                risk=b_res.final_failure_probability,
                cost_rm=INTERVENTION_COST_MAP.get(CounterfactualScenarioType.DO_NOTHING, 0.0),
                production_loss_pct=0.0,
                downtime_hours=b_res.downtime,
                recovery_time_hours=b_res.recovery_time if b_res.recovery_time is not None else 0.0,
                rul_hours=b_res.final_rul if b_res.final_rul is not None else 24.0,
                final_health=b_res.final_health,
            )

        # 9. Evaluate Criteria, Feasibility & Utilities for All Candidates
        unevaluated_candidates: List[CandidateActionEvaluation] = []

        for cfg, sim_resp in sim_results:
            scenario_type: CounterfactualScenarioType = cfg["type"]
            label: str = cfg["label"]
            params: Dict[str, Any] = cfg["params"]
            res = sim_resp.result
            comp = sim_resp.baseline_comparison

            # Determine operational / intervention cost
            base_cost = INTERVENTION_COST_MAP.get(scenario_type, 0.0)
            if scenario_type == CounterfactualScenarioType.LOAD_MODULATION and params.get("load_reduction") == 0.40:
                cost_rm = 100.0
            else:
                cost_rm = base_cost

            # Production throughput loss %
            loss_pct = comp.throughput_loss_pct if comp else 0.0

            # Expected downtime and recovery duration
            downtime_h = res.downtime
            recovery_h = res.recovery_time if res.recovery_time is not None else (0.5 if downtime_h > 0 else 0.0)
            rul_h = res.final_rul if res.final_rul is not None else 24.0
            final_health = res.final_health

            raw_criteria = RawCriteriaValues(
                risk=res.final_failure_probability,
                cost_rm=cost_rm,
                production_loss_pct=loss_pct,
                downtime_hours=downtime_h,
                recovery_time_hours=recovery_h,
                rul_hours=rul_h,
                final_health=final_health,
            )

            # Evaluate Hard Constraints
            feasibility, feasibility_reasons = evaluate_action_feasibility(
                action=scenario_type,
                raw=raw_criteria,
                peak_temperature=res.peak_temperature,
                constraints=constraints,
            )

            # Compute Normalized Utilities
            utilities = calculate_utilities(raw_criteria)

            # Compute Weighted Decision Score
            score = calculate_decision_score(utilities, weights)

            # Generate Engineering Trade-offs
            benefits, risks, trade_offs = generate_candidate_trade_offs(
                action=scenario_type,
                raw=raw_criteria,
                baseline_raw=baseline_raw,
            )

            candidate = CandidateActionEvaluation(
                rank=1,  # Placeholder, assigned by rank_candidate_actions
                action=scenario_type,
                action_label=label,
                parameters=params,
                decision_score=score,
                feasibility=feasibility,
                feasibility_reasons=feasibility_reasons,
                raw_criteria=raw_criteria,
                utilities=utilities,
                key_benefits=benefits,
                key_risks=risks,
                trade_offs=trade_offs,
                near_tie=False,
                near_tie_with=None,
            )
            unevaluated_candidates.append(candidate)

        # 10. Multi-Attribute Ranking & Near-Tie Detection
        ranked_candidates = rank_candidate_actions(unevaluated_candidates)

        # Identify top recommendation (first feasible candidate, or top overall)
        top_rec = next(
            (c for c in ranked_candidates if c.feasibility == ActionFeasibilityStatus.FEASIBLE),
            ranked_candidates[0] if ranked_candidates else None,
        )

        # 11. Policy Sensitivity & Rank Stability Analysis
        sensitivity_profiles, rank_stability, rank_stability_reason = run_sensitivity_analysis(ranked_candidates)

        # 12. Deterministic Narrative & Explainability Generation
        narrative, confidence, confidence_reasons = generate_decision_narrative(
            ranked_candidates=ranked_candidates,
            constraints=constraints,
            baseline_raw=baseline_raw,
        )

        # 13. Construct Response
        decision_id = f"DEC-{request.machine_id}-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)

        response = DecisionAnalysisResponse(
            decision_id=decision_id,
            machine_id=request.machine_id,
            created_at=now,
            status=DecisionEngineStatus.COMPLETED,
            policy_profile=policy_profile,
            criteria_weights=weights,
            constraints=constraints,
            ranked_candidates=ranked_candidates,
            top_recommended_candidate=top_rec,
            decision_explanation=narrative,
            decision_confidence=confidence,
            confidence_reasons=confidence_reasons,
            rank_stability=rank_stability,
            rank_stability_reason=rank_stability_reason,
            sensitivity_analysis=sensitivity_profiles,
            evidence_references=evidence_refs,
            provenance=DataProvenance.RECOMMENDED,
        )

        # 14. Persistence to Database
        if request.persist and db is not None:
            try:
                db_record = DecisionModel(
                    decision_id=response.decision_id,
                    machine_id=response.machine_id,
                    snapshot_id=snapshot.snapshot_id,
                    policy_profile=response.policy_profile.value,
                    criteria_weights=response.criteria_weights.model_dump(),
                    constraints=response.constraints.model_dump(),
                    candidate_actions=[c.model_dump() for c in response.ranked_candidates],
                    decision_scores={c.action_label: c.decision_score for c in response.ranked_candidates},
                    feasibility={c.action_label: c.feasibility.value for c in response.ranked_candidates},
                    rank_stability=response.rank_stability.value,
                    confidence=response.decision_confidence,
                    evidence_references=response.evidence_references.model_dump(),
                    decision_explanation=response.decision_explanation,
                    status=response.status.value,
                    provenance=response.provenance.value,
                    created_at=now,
                )
                db.add(db_record)
                db.commit()
            except Exception as err:
                db.rollback()
                logger.warning(f"Could not persist decision analysis record to DB: {err}")

        return response


_global_decision_engine: Optional[DecisionEngine] = None


def get_decision_engine() -> DecisionEngine:
    global _global_decision_engine
    if _global_decision_engine is None:
        _global_decision_engine = DecisionEngine()
    return _global_decision_engine
