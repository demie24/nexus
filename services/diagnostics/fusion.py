"""
NEXUS Diagnostics Evidence Fusion Engine
Synthesizes multi-source evidence: observed sensor deviations, dependency graph traversal,
physical consistency checks, temporal dynamics, and model-derived contributions.

Applies a transparent, configuration-driven scoring formula to rank candidate causes
with strict unknown-case fallback and calibrated confidence assessment.
"""

from typing import Dict, List, Optional, Tuple, Any
from services.schemas import (
    RootCauseType,
    EvidenceSource,
    SignalDirection,
    PhysicalConsistencyStatus,
    EvidenceItem,
    CauseCandidate,
)
from services.diagnostics.config import (
    CAUSE_TAXONOMY,
    WEIGHT_OBSERVED,
    WEIGHT_GRAPH,
    WEIGHT_PHYSICAL,
    WEIGHT_TEMPORAL,
    WEIGHT_MODEL,
    MIN_EVIDENCE_THRESHOLD,
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_HIGH_MARGIN,
    CONFIDENCE_MEDIUM_THRESHOLD,
)
from services.diagnostics.graph import DiagnosticDependencyGraph
from services.diagnostics.physical_consistency import PhysicalConsistencyChecker


class EvidenceFusionEngine:
    """
    Computes deterministic evidence scores for candidate causes and ranks them.
    """

    def __init__(self, dependency_graph: DiagnosticDependencyGraph):
        self.graph = dependency_graph
        self.physics_checker = PhysicalConsistencyChecker()

    def fuse_evidence(
        self,
        observed_values: Dict[str, float],
        baseline_stats: Dict[str, Tuple[float, float]],
        dynamics: Dict[str, Dict[str, Any]],
        anomaly_context: Optional[Dict[str, Any]] = None,
        prediction_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[RootCauseType, float, str, List[CauseCandidate], List[EvidenceItem]]:
        """
        Executes end-to-end evidence fusion across all candidate causes in taxonomy.
        Returns:
            likely_cause: top ranked cause (or UNKNOWN)
            top_score: evidence score of top cause
            confidence: HIGH, MEDIUM, LOW
            ranked_candidates: list of CauseCandidate in descending rank order
            global_evidence_summary: itemized list of significant evidence items
        """
        anomaly_context = anomaly_context or {}
        prediction_context = prediction_context or {}
        anomaly_classifier_type = anomaly_context.get("anomaly_type")

        # Prepare directional deviations and evidence items for each signal
        observed_deviations: Dict[str, Tuple[SignalDirection, float]] = {}
        global_evidence_items: List[EvidenceItem] = []

        for sig, (base_mean, base_std) in baseline_stats.items():
            if sig not in observed_values:
                continue

            obs_val = observed_values[sig]
            std_eff = max(0.001, base_std)
            z_score = (obs_val - base_mean) / std_eff
            pct_change = ((obs_val - base_mean) / max(0.001, abs(base_mean))) * 100.0

            dyn = dynamics.get(sig, {})
            direction = dyn.get("direction", SignalDirection.STABLE)
            strength = min(1.0, abs(z_score) / 3.0)

            observed_deviations[sig] = (direction, strength)

            if abs(z_score) >= 1.5 or dyn.get("is_spike", False) or abs(pct_change) >= 5.0:
                dir_label = "increased" if z_score > 0 else "decreased"
                sign_str = "+" if pct_change > 0 else ""
                desc = f"{sig.replace('_', ' ').title()} {dir_label} ({sign_str}{pct_change:.1f}% vs baseline, Z={z_score:.2f})"

                global_evidence_items.append(EvidenceItem(
                    signal=sig,
                    direction=direction,
                    strength=round(strength, 3),
                    source=EvidenceSource.OBSERVED,
                    description=desc,
                    observed_value=round(obs_val, 2),
                    baseline_value=round(base_mean, 2),
                    pct_deviation=round(pct_change, 1)
                ))

        # Evaluate each candidate cause in taxonomy (excluding UNKNOWN which is fallback)
        evaluated_candidates: List[CauseCandidate] = []

        for cause_enum, definition in CAUSE_TAXONOMY.items():
            if cause_enum == RootCauseType.UNKNOWN:
                continue

            candidate_evidence: List[EvidenceItem] = []

            # 1. Observed Evidence Score (S_obs)
            s_obs, obs_items = self._compute_observed_score(
                cause_enum, definition, observed_values, baseline_stats, dynamics
            )
            candidate_evidence.extend(obs_items)

            # 2. Graph Alignment Score (S_graph)
            s_graph, graph_matches = self.graph.evaluate_graph_alignment(cause_enum, observed_deviations)
            for gm in graph_matches:
                candidate_evidence.append(EvidenceItem(
                    signal=gm["signal"],
                    direction=SignalDirection(gm["observed_direction"]),
                    strength=round(min(1.0, gm["weight"]), 3),
                    source=EvidenceSource.GRAPH,
                    description=f"Path verified via dependency graph: {gm['description']}"
                ))

            # 3. Physical Consistency Score (S_phys)
            phys_status, s_phys, phys_reasons = self.physics_checker.check_consistency(
                cause_enum, observed_values,
                {k: v[0] for k, v in baseline_stats.items()},
                dynamics,
                anomaly_classifier_type=anomaly_classifier_type
            )
            for reason in phys_reasons:
                candidate_evidence.append(EvidenceItem(
                    signal=definition.primary_signals[0] if definition.primary_signals else "system",
                    direction=SignalDirection.STABLE,
                    strength=round(s_phys, 3),
                    source=EvidenceSource.PHYSICAL_CONSISTENCY,
                    description=f"Physical check ({phys_status.value}): {reason}"
                ))

            # 4. Temporal Dynamics Score (S_temp)
            s_temp, temp_items = self._compute_temporal_score(definition, dynamics)
            candidate_evidence.extend(temp_items)

            # 5. Model-Derived Score (S_model)
            s_model, model_items = self._compute_model_score(
                cause_enum, definition, anomaly_context, prediction_context
            )
            candidate_evidence.extend(model_items)

            # --- Combined Weighted Evidence Score ---
            raw_score = (
                WEIGHT_OBSERVED * s_obs +
                WEIGHT_GRAPH * s_graph +
                WEIGHT_PHYSICAL * s_phys +
                WEIGHT_TEMPORAL * s_temp +
                WEIGHT_MODEL * s_model
            )

            # Apply domain suppression rules
            final_score = raw_score
            # If sensor anomaly is isolated, suppress physical causes
            if cause_enum != RootCauseType.SENSOR_ANOMALY:
                if anomaly_classifier_type == "SENSOR_ANOMALY" or s_phys < 0.20:
                    final_score *= 0.35
            else:
                # If Sensor Anomaly candidate:
                if anomaly_classifier_type == "SENSOR_ANOMALY":
                    final_score = max(final_score, 0.82)
                elif any(d.get("is_spike") for d in dynamics.values()) and s_phys >= 0.60:
                    final_score = max(final_score, 0.75)

            # Check primary signal existence
            if definition.primary_signals:
                primary_devs = [
                    observed_deviations.get(sig, (SignalDirection.STABLE, 0.0))[1]
                    for sig in definition.primary_signals
                ]
                if max(primary_devs, default=0.0) < 0.20:
                    final_score *= 0.40  # Primary signal didn't deviate

            final_score = round(min(1.0, max(0.0, float(final_score))), 3)

            evaluated_candidates.append(CauseCandidate(
                cause=cause_enum,
                rank=0,  # Will be assigned during sorting
                evidence_score=final_score,
                confidence="LOW",  # Will be assigned after ranking
                physical_consistency_status=phys_status,
                evidence=candidate_evidence,
                summary=f"Evaluated with evidence score {final_score:.2f} ({phys_status.value})."
            ))

        # Sort candidates descending by evidence score
        evaluated_candidates.sort(key=lambda c: c.evidence_score, reverse=True)

        # Determine if top candidate has sufficient evidence
        top_cand = evaluated_candidates[0] if evaluated_candidates else None

        if top_cand is None or top_cand.evidence_score < MIN_EVIDENCE_THRESHOLD:
            # Fallback to UNKNOWN
            likely_cause = RootCauseType.UNKNOWN
            top_score = top_cand.evidence_score if top_cand else 0.0
            overall_confidence = "LOW"

            # Prepend UNKNOWN candidate at rank 1
            unknown_candidate = CauseCandidate(
                cause=RootCauseType.UNKNOWN,
                rank=1,
                evidence_score=round(top_score, 3),
                confidence="LOW",
                physical_consistency_status=PhysicalConsistencyStatus.AMBIGUOUS,
                evidence=global_evidence_items,
                summary="Insufficient or ambiguous supporting evidence. System refuses to guess causality."
            )
            # Reassign ranks
            ranked_candidates = [unknown_candidate]
            for idx, c in enumerate(evaluated_candidates, start=2):
                c.rank = idx
                c.confidence = "LOW"
                ranked_candidates.append(c)

            return likely_cause, top_score, overall_confidence, ranked_candidates, global_evidence_items

        # Top candidate is valid
        likely_cause = top_cand.cause
        top_score = top_cand.evidence_score
        second_score = evaluated_candidates[1].evidence_score if len(evaluated_candidates) > 1 else 0.0
        score_gap = top_score - second_score

        # Calculate confidence
        if (
            top_score >= CONFIDENCE_HIGH_THRESHOLD and
            score_gap >= CONFIDENCE_HIGH_MARGIN and
            top_cand.physical_consistency_status == PhysicalConsistencyStatus.CONSISTENT
        ):
            overall_confidence = "HIGH"
        elif top_score >= CONFIDENCE_MEDIUM_THRESHOLD:
            overall_confidence = "MEDIUM"
        else:
            overall_confidence = "LOW"

        # Assign ranks and confidence
        for idx, c in enumerate(evaluated_candidates, start=1):
            c.rank = idx
            if idx == 1:
                c.confidence = overall_confidence
            elif c.evidence_score >= CONFIDENCE_MEDIUM_THRESHOLD:
                c.confidence = "MEDIUM"
            else:
                c.confidence = "LOW"

        return likely_cause, top_score, overall_confidence, evaluated_candidates, global_evidence_items

    @staticmethod
    def _compute_observed_score(
        cause: RootCauseType,
        definition: Any,
        observed_values: Dict[str, float],
        baseline_stats: Dict[str, Tuple[float, float]],
        dynamics: Dict[str, Dict[str, Any]]
    ) -> Tuple[float, List[EvidenceItem]]:
        if not definition.expected_signals:
            return 0.0, []

        total_weight = sum(definition.signal_weights.get(sig, 0.2) for sig in definition.expected_signals)
        matched_score = 0.0
        items = []

        for sig, exp_dir in definition.expected_signals.items():
            if sig not in observed_values or sig not in baseline_stats:
                continue

            obs_val = observed_values[sig]
            base_mean, base_std = baseline_stats[sig]
            weight = definition.signal_weights.get(sig, 0.2)
            std_eff = max(0.001, base_std)
            z_score = (obs_val - base_mean) / std_eff

            dyn = dynamics.get(sig, {})
            obs_dir = dyn.get("direction", SignalDirection.STABLE)

            # Match criteria
            is_match = False
            strength = 0.0
            if exp_dir == SignalDirection.INCREASING and (z_score >= 1.2 or obs_dir == SignalDirection.INCREASING):
                is_match = True
                strength = min(1.0, max(0.2, z_score / 3.0))
            elif exp_dir == SignalDirection.DECREASING and (z_score <= -1.2 or obs_dir == SignalDirection.DECREASING):
                is_match = True
                strength = min(1.0, max(0.2, abs(z_score) / 3.0))

            if is_match:
                matched_score += weight * strength
                items.append(EvidenceItem(
                    signal=sig,
                    direction=obs_dir,
                    strength=round(strength, 3),
                    source=EvidenceSource.OBSERVED,
                    description=f"{sig.replace('_', ' ').title()} matches expected {exp_dir.value.lower()} trend (observed={obs_val:.2f}, baseline={base_mean:.2f})"
                ))

        score = matched_score / total_weight if total_weight > 0 else 0.0
        return min(1.0, max(0.0, score)), items

    @staticmethod
    def _compute_temporal_score(
        definition: Any,
        dynamics: Dict[str, Dict[str, Any]]
    ) -> Tuple[float, List[EvidenceItem]]:
        if not definition.primary_signals:
            return 0.50, []

        items = []
        persistent_count = 0
        for sig in definition.primary_signals:
            dyn = dynamics.get(sig, {})
            if dyn.get("is_persistent", False):
                persistent_count += 1
                items.append(EvidenceItem(
                    signal=sig,
                    direction=dyn.get("direction", SignalDirection.STABLE),
                    strength=dyn.get("persistence", 0.5),
                    source=EvidenceSource.TEMPORAL,
                    description=f"Persistent drift observed on {sig} across {int(dyn.get('persistence', 0)*100)}% of the analysis window."
                ))

        score = persistent_count / len(definition.primary_signals)
        return float(score), items

    @staticmethod
    def _compute_model_score(
        cause: RootCauseType,
        definition: Any,
        anomaly_context: Dict[str, Any],
        prediction_context: Dict[str, Any]
    ) -> Tuple[float, List[EvidenceItem]]:
        score = 0.50
        items = []

        # 1. Anomaly Model Evidence
        triggered = anomaly_context.get("triggered_signals", [])
        if any(sig in triggered for sig in definition.primary_signals):
            score += 0.25
            items.append(EvidenceItem(
                signal=definition.primary_signals[0] if definition.primary_signals else "telemetry",
                direction=SignalDirection.INCREASING,
                strength=0.75,
                source=EvidenceSource.MODEL_DERIVED,
                description="Anomaly detector statistical layer flagged primary coupled signal."
            ))

        # 2. Predictive Model Evidence (Phase 5)
        risk_level = prediction_context.get("risk_level", "LOW")
        rul_hours = prediction_context.get("remaining_useful_life_hours", 100.0)

        if cause in [RootCauseType.BEARING_DEGRADATION, RootCauseType.COOLING_DEGRADATION, RootCauseType.MOTOR_INEFFICIENCY]:
            if risk_level in ["HIGH", "CRITICAL"] or rul_hours < 30.0:
                score += 0.25
                items.append(EvidenceItem(
                    signal="rul_hours",
                    direction=SignalDirection.DECREASING,
                    strength=0.80,
                    source=EvidenceSource.MODEL_DERIVED,
                    description=f"Predictive Engine forecasts acute failure risk ({risk_level}) with degraded RUL ({rul_hours:.1f}h)."
                ))

        return min(1.0, max(0.0, score)), items
