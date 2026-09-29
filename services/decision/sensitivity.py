"""
NEXUS Policy Sensitivity & Rank Stability Analysis
Evaluates candidate ranking stability across alternative operational policies (Balanced, Safety-First, Production-First).
Quantifies whether the recommended action is robust or sensitive to weight adjustments.
"""

from typing import List, Tuple, Dict, Any
from services.schemas import (
    CandidateActionEvaluation,
    DecisionSensitivityProfile,
    PolicyProfileType,
    RankStabilityLevel,
    ActionFeasibilityStatus,
)
from services.decision.config import POLICY_PROFILES
from services.decision.ranking import calculate_decision_score, rank_candidate_actions


def run_sensitivity_analysis(
    candidates: List[CandidateActionEvaluation],
) -> Tuple[List[DecisionSensitivityProfile], RankStabilityLevel, str]:
    """
    Evaluates candidate action performance across BALANCED, SAFETY_FIRST, and PRODUCTION_FIRST policies.
    Returns:
    - List of DecisionSensitivityProfile per policy
    - Overall RankStabilityLevel (HIGH_STABILITY, MODERATE_STABILITY, LOW_STABILITY)
    - Human-readable stability rationale
    """
    if not candidates:
        return (
            [],
            RankStabilityLevel.LOW_STABILITY,
            "No candidate actions available to evaluate rank stability.",
        )

    sensitivity_profiles: List[DecisionSensitivityProfile] = []
    top_actions: List[str] = []

    core_policies = [
        PolicyProfileType.BALANCED,
        PolicyProfileType.SAFETY_FIRST,
        PolicyProfileType.PRODUCTION_FIRST,
    ]

    for policy in core_policies:
        weights = POLICY_PROFILES[policy]

        # Re-score candidates under this policy's weights
        re_evaluated: List[CandidateActionEvaluation] = []
        for c in candidates:
            c_copy = c.model_copy()
            c_copy.decision_score = calculate_decision_score(c_copy.utilities, weights)
            re_evaluated.append(c_copy)

        re_ranked = rank_candidate_actions(re_evaluated)

        # Find top feasible action (or top action if none feasible)
        top_feasible = next(
            (c for c in re_ranked if c.feasibility == ActionFeasibilityStatus.FEASIBLE),
            re_ranked[0] if re_ranked else None,
        )

        rankings_summary: List[Dict[str, Any]] = [
            {
                "rank": c.rank,
                "action": c.action.value,
                "action_label": c.action_label,
                "score": c.decision_score,
                "feasibility": c.feasibility.value,
            }
            for c in re_ranked
        ]

        if top_feasible:
            top_action_type = top_feasible.action
            top_score = top_feasible.decision_score
            top_actions.append(top_feasible.action.value)
        else:
            top_action_type = candidates[0].action
            top_score = 0.0
            top_actions.append(candidates[0].action.value)

        sensitivity_profiles.append(
            DecisionSensitivityProfile(
                profile=policy,
                top_action=top_action_type,
                top_score=top_score,
                rankings=rankings_summary,
            )
        )

    # Determine stability
    unique_top_actions = set(top_actions)
    if len(unique_top_actions) == 1:
        stability = RankStabilityLevel.HIGH_STABILITY
        action_name = top_actions[0]
        reason = (
            f"Action '{action_name}' is optimal across all operational policies "
            "(Balanced, Safety-First, Production-First). Recommendation is structurally robust."
        )
    elif len(unique_top_actions) == 2:
        stability = RankStabilityLevel.MODERATE_STABILITY
        # Find the majority action
        majority_action = max(set(top_actions), key=top_actions.count)
        divergent_policy = [
            core_policies[i].value
            for i, act in enumerate(top_actions)
            if act != majority_action
        ]
        reason = (
            f"Action '{majority_action}' is favored in 2 of 3 policies, but changes under "
            f"{', '.join(divergent_policy)} policy. Decision is moderately sensitive to operating priorities."
        )
    else:
        stability = RankStabilityLevel.LOW_STABILITY
        reason = (
            "Top recommendation changes under each policy profile. "
            "High policy sensitivity: executive stakeholder alignment on operating priorities is required."
        )

    return sensitivity_profiles, stability, reason
