"""
NEXUS Multi-Criteria Scoring, Ranking & Tie-Break Engine
Computes multi-attribute utility scores, ranks candidate actions respecting feasibility,
and detects near-tie scenarios within decision threshold.
"""

from typing import List, Optional
from services.schemas import (
    CandidateActionEvaluation,
    CriteriaWeights,
    NormalizedUtilities,
    ActionFeasibilityStatus,
)
from services.decision.criteria import normalize_weights

NEAR_TIE_THRESHOLD = 0.015


def calculate_decision_score(
    utilities: NormalizedUtilities,
    weights: CriteriaWeights,
) -> float:
    """
    Computes weighted multi-criteria score from normalized utilities and weights.
    Score = sum(w_i * u_i), bounded in [0.0, 1.0].
    """
    norm_w = normalize_weights(weights)

    score = (
        norm_w.risk_weight * utilities.risk_utility +
        norm_w.cost_weight * utilities.cost_utility +
        norm_w.production_weight * utilities.production_utility +
        norm_w.downtime_weight * utilities.downtime_utility +
        norm_w.recovery_weight * utilities.recovery_utility +
        norm_w.health_weight * utilities.health_utility
    )

    return round(max(0.0, min(1.0, score)), 4)


def rank_candidate_actions(
    candidates: List[CandidateActionEvaluation],
    tie_threshold: float = NEAR_TIE_THRESHOLD,
) -> List[CandidateActionEvaluation]:
    """
    Ranks candidate actions according to:
    1. Feasibility status: FEASIBLE candidates are prioritized above INFEASIBLE / UNKNOWN.
    2. Decision score: Descending order (highest utility first).

    Detects near-ties (|score_i - score_{i+1}| <= tie_threshold) among feasible candidates.
    """
    if not candidates:
        return []

    # Partition candidates by feasibility
    feasible = [c for c in candidates if c.feasibility == ActionFeasibilityStatus.FEASIBLE]
    infeasible = [c for c in candidates if c.feasibility == ActionFeasibilityStatus.INFEASIBLE]
    unknown = [c for c in candidates if c.feasibility == ActionFeasibilityStatus.UNKNOWN]

    # Sort each partition descending by decision_score
    feasible.sort(key=lambda c: c.decision_score, reverse=True)
    infeasible.sort(key=lambda c: c.decision_score, reverse=True)
    unknown.sort(key=lambda c: c.decision_score, reverse=True)

    ordered = feasible + unknown + infeasible

    # Assign ranks and detect near-ties
    ranked: List[CandidateActionEvaluation] = []
    total = len(ordered)

    for i, candidate in enumerate(ordered):
        c_copy = candidate.model_copy()
        c_copy.rank = i + 1

        # Near-tie detection among feasible candidates
        if c_copy.feasibility == ActionFeasibilityStatus.FEASIBLE:
            # Check previous
            if i > 0 and ordered[i - 1].feasibility == ActionFeasibilityStatus.FEASIBLE:
                diff_prev = abs(ordered[i - 1].decision_score - c_copy.decision_score)
                if diff_prev <= tie_threshold:
                    c_copy.near_tie = True
                    c_copy.near_tie_with = ordered[i - 1].action_label

            # Check next
            if i < total - 1 and ordered[i + 1].feasibility == ActionFeasibilityStatus.FEASIBLE:
                diff_next = abs(c_copy.decision_score - ordered[i + 1].decision_score)
                if diff_next <= tie_threshold:
                    c_copy.near_tie = True
                    if not c_copy.near_tie_with:
                        c_copy.near_tie_with = ordered[i + 1].action_label

        ranked.append(c_copy)

    return ranked
