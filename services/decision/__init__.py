"""
NEXUS Multi-Criteria Decision Engine Package (Phase 8)
"""

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
from services.decision.engine import DecisionEngine, get_decision_engine

__all__ = [
    "POLICY_PROFILES",
    "DEFAULT_CONSTRAINTS",
    "INTERVENTION_COST_MAP",
    "ENGINE_VERSION",
    "DECISION_RULE_VERSION",
    "normalize_weights",
    "calculate_utilities",
    "evaluate_action_feasibility",
    "calculate_decision_score",
    "rank_candidate_actions",
    "run_sensitivity_analysis",
    "generate_candidate_trade_offs",
    "generate_decision_narrative",
    "DecisionEngine",
    "get_decision_engine",
]
