"""
NEXUS Decision Explanation & Trade-Off Generator
Produces deterministic, auditable engineering explanations for multi-criteria rankings.
Strictly rule-based and mathematical—zero non-deterministic generative models.
"""

from typing import List, Tuple, Dict, Any, Optional
from services.schemas import (
    CandidateActionEvaluation,
    CounterfactualScenarioType,
    ActionFeasibilityStatus,
    DomainConstraints,
    RawCriteriaValues,
)


def generate_candidate_trade_offs(
    action: CounterfactualScenarioType,
    raw: RawCriteriaValues,
    baseline_raw: Optional[RawCriteriaValues] = None,
) -> Tuple[List[str], List[str], List[str]]:
    """
    Generates deterministic key benefits, key risks, and trade-off statements
    for a candidate action based on simulated engineering outcomes.
    """
    benefits: List[str] = []
    risks: List[str] = []
    trade_offs: List[str] = []

    # 1. Benefits analysis
    if raw.risk <= 0.20:
        benefits.append(f"Maintains low residual failure hazard ({raw.risk * 100:.1f}%).")
    if raw.production_loss_pct <= 5.0:
        benefits.append(f"Near-zero throughput penalty ({raw.production_loss_pct:.1f}% loss).")
    if raw.cost_rm <= 100.0:
        benefits.append(f"Economical intervention cost (RM {raw.cost_rm:.2f}).")
    if raw.downtime_hours == 0.0:
        benefits.append("Zero operational downtime incurred.")
    if raw.rul_hours >= 24.0:
        benefits.append(f"Sustains healthy component life expectancy ({raw.rul_hours:.1f}h RUL).")

    # 2. Risks analysis
    if raw.risk >= 0.50:
        risks.append(f"Elevated failure probability ({raw.risk * 100:.1f}%) during projection horizon.")
    if raw.production_loss_pct >= 20.0:
        risks.append(f"Substantial production loss ({raw.production_loss_pct:.1f}% throughput penalty).")
    if raw.cost_rm >= 500.0:
        risks.append(f"High intervention cost (RM {raw.cost_rm:.2f}).")
    if raw.downtime_hours >= 4.0:
        risks.append(f"Extended machine downtime ({raw.downtime_hours:.1f} hours).")
    if raw.rul_hours < 8.0:
        risks.append(f"Critically shortened remaining useful life ({raw.rul_hours:.1f} hours).")

    # 3. Action-specific narratives
    if action == CounterfactualScenarioType.DO_NOTHING:
        if not benefits:
            benefits.append("Requires zero immediate capital outlay or maintenance coordination.")
        if not risks:
            risks.append("Unmitigated degradation trajectory may accelerate thermal/vibration stress.")
        trade_offs.append("Maximum production preservation at the expense of unmanaged equipment risk.")

    elif action == CounterfactualScenarioType.LOAD_MODULATION:
        trade_offs.append(
            f"Accepts {raw.production_loss_pct:.1f}% throughput reduction in exchange for "
            f"{(1.0 - raw.risk) * 100:.1f}% risk mitigation and thermal stabilization."
        )

    elif action == CounterfactualScenarioType.COOLING_BOOST:
        trade_offs.append(
            f"Invests RM {raw.cost_rm:.2f} in auxiliary cooling to suppress thermal escalation "
            "without penalizing production output."
        )

    elif action == CounterfactualScenarioType.SCHEDULED_SHUTDOWN:
        trade_offs.append(
            f"Trades {raw.downtime_hours:.1f}h planned downtime and RM {raw.cost_rm:.2f} maintenance "
            "cost to completely halt degradation progression."
        )

    elif action == CounterfactualScenarioType.EMERGENCY_STOP:
        trade_offs.append(
            f"Incurs severe downtime ({raw.downtime_hours:.1f}h) and restart cost (RM {raw.cost_rm:.2f}) "
            "as a last-resort intervention to prevent catastrophic plant-level damage."
        )

    # 4. Comparative trade-off against DO_NOTHING baseline
    if baseline_raw and action != CounterfactualScenarioType.DO_NOTHING:
        risk_diff = baseline_raw.risk - raw.risk
        if risk_diff > 0.05:
            trade_offs.append(
                f"Reduces projected failure probability by {risk_diff * 100:.1f} percentage points "
                f"relative to the DO_NOTHING baseline."
            )
        rul_diff = raw.rul_hours - baseline_raw.rul_hours
        if rul_diff > 1.0:
            trade_offs.append(
                f"Extends machine RUL by {rul_diff:.1f} hours relative to baseline."
            )

    return benefits, risks, trade_offs


def generate_decision_narrative(
    ranked_candidates: List[CandidateActionEvaluation],
    constraints: DomainConstraints,
    baseline_raw: Optional[RawCriteriaValues] = None,
) -> Tuple[str, str, List[str]]:
    """
    Generates an executive engineering decision explanation, confidence level, and rationale.
    """
    if not ranked_candidates:
        return (
            "No candidate actions evaluated. Insufficient simulation or machine state data.",
            "LOW",
            ["No candidate evaluations found."],
        )

    top = ranked_candidates[0]
    confidence_reasons: List[str] = []

    # Check top feasibility
    if top.feasibility != ActionFeasibilityStatus.FEASIBLE:
        explanation = (
            f"CRITICAL ALERT: No evaluated action satisfies all operational safety constraints. "
            f"Top ranked candidate '{top.action_label}' is flagged as {top.feasibility.value}: "
            f"{'; '.join(top.feasibility_reasons)}. Immediate manual engineering triage is required."
        )
        return explanation, "LOW", ["No candidate actions satisfied all domain safety constraints."]

    # High-confidence indicators
    confidence_reasons.append("Complete 6-criteria physical and economic evaluation performed.")
    confidence_reasons.append(f"Domain constraints verified: Core temp <= {constraints.max_safe_temperature}°C, Risk <= {constraints.critical_failure_probability * 100:.0f}%.")

    # Near tie analysis
    near_tie_note = ""
    if top.near_tie and top.near_tie_with:
        near_tie_note = (
            f" Note: Decision score is closely tied with '{top.near_tie_with}' "
            "(score delta <= 0.015). Both options are viable depending on shift supervisor preference."
        )
        confidence = "MEDIUM"
        confidence_reasons.append(f"Near-tie detected between {top.action_label} and {top.near_tie_with}.")
    else:
        confidence = "HIGH"
        confidence_reasons.append(f"Clear mathematical separation for optimal action '{top.action_label}'.")

    # Infeasible candidates summary
    infeasible_cands = [c for c in ranked_candidates if c.feasibility == ActionFeasibilityStatus.INFEASIBLE]
    infeasible_summary = ""
    if infeasible_cands:
        reasons_list = [f"{c.action_label} ({c.feasibility_reasons[0]})" for c in infeasible_cands if c.feasibility_reasons]
        infeasible_summary = f" Infeasible actions excluded: {'; '.join(reasons_list)}."

    # Baseline comparison summary
    baseline_comparison = ""
    if baseline_raw and top.action != CounterfactualScenarioType.DO_NOTHING:
        p_reduction = (baseline_raw.risk - top.raw_criteria.risk) * 100
        baseline_comparison = (
            f" Compared to taking no action, '{top.action_label}' delivers a {p_reduction:.1f} percentage point "
            f"hazard reduction while preserving {100.0 - top.raw_criteria.production_loss_pct:.1f}% nominal throughput."
        )

    explanation = (
        f"RECOMMENDED ACTION: {top.action_label} (Utility Score: {top.decision_score:.4f}, Feasible). "
        f"{' '.join(top.trade_offs[:2])}.{baseline_comparison}{near_tie_note}{infeasible_summary}"
    )

    return explanation.strip(), confidence, confidence_reasons
