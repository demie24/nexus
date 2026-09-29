"""
NEXUS Counterfactual Outcome Metrics & Baseline Comparison Engine
Calculates physics-consistent outcome metrics, delta changes, and comparative metrics against DO_NOTHING.
"""

from typing import Optional, Dict, Any
from services.schemas import OutcomeMetrics, BaselineComparison


class SimulationSanityError(ValueError):
    """Raised when simulation physics produce invalid/impossible physical values."""
    pass


def validate_metrics_sanity(metrics: OutcomeMetrics) -> None:
    """
    Validates physical consistency and boundary bounds.
    Rejects impossible physics with a controlled error rather than silently clamping.
    """
    if metrics.peak_temperature < 15.0:
        raise SimulationSanityError(f"Impossible physical temperature: {metrics.peak_temperature}°C is below ambient minimum.")
    if metrics.peak_temperature > 250.0:
        raise SimulationSanityError(f"Catastrophic unphysical thermal runaway: {metrics.peak_temperature}°C.")
    if metrics.initial_health < 0.0 or metrics.initial_health > 100.0 or metrics.final_health < 0.0 or metrics.final_health > 100.0:
        raise SimulationSanityError(f"Health score out of bounds [0, 100]: init={metrics.initial_health}, final={metrics.final_health}.")
    if not (0.0 <= metrics.initial_failure_probability <= 1.0) or not (0.0 <= metrics.final_failure_probability <= 1.0):
        raise SimulationSanityError(f"Failure probability out of probability bounds [0, 1]: init={metrics.initial_failure_probability}, final={metrics.final_failure_probability}.")
    if metrics.total_output < 0.0:
        raise SimulationSanityError(f"Negative production output: {metrics.total_output}.")
    if metrics.initial_rul is not None and metrics.initial_rul < 0.0:
        raise SimulationSanityError(f"Negative RUL: {metrics.initial_rul}.")
    if metrics.final_rul is not None and metrics.final_rul < 0.0:
        raise SimulationSanityError(f"Negative final RUL: {metrics.final_rul}.")


def build_baseline_comparison(
    baseline_metrics: OutcomeMetrics,
    scenario_metrics: OutcomeMetrics
) -> BaselineComparison:
    """
    Constructs an explicit, mathematically rigorous comparison against DO_NOTHING.
    Strictly distinguishes between percentage points (pp) and relative percentage reduction (%).
    """
    rul_delta = None
    if scenario_metrics.final_rul is not None and baseline_metrics.final_rul is not None:
        rul_delta = round(scenario_metrics.final_rul - baseline_metrics.final_rul, 2)

    # Percentage points difference: e.g. 76% (0.76) -> 41% (0.41) = -35.0 percentage points
    pp_diff = round((scenario_metrics.final_failure_probability - baseline_metrics.final_failure_probability) * 100.0, 2)

    # Relative percentage reduction: (0.76 - 0.41) / 0.76 * 100 = 46.05%
    rel_reduction = None
    if baseline_metrics.final_failure_probability > 0.001:
        rel_reduction = round(
            max(0.0, (baseline_metrics.final_failure_probability - scenario_metrics.final_failure_probability)
                / baseline_metrics.final_failure_probability * 100.0),
            2
        )

    # Throughput loss relative to baseline output
    throughput_loss_pct = 0.0
    if baseline_metrics.total_output > 0.001:
        throughput_loss_pct = round(
            max(0.0, (baseline_metrics.total_output - scenario_metrics.total_output) / baseline_metrics.total_output * 100.0),
            2
        )

    peak_temp_delta = round(scenario_metrics.peak_temperature - baseline_metrics.peak_temperature, 2)

    return BaselineComparison(
        baseline_rul=baseline_metrics.final_rul,
        scenario_rul=scenario_metrics.final_rul,
        rul_delta_hours=rul_delta,
        baseline_failure_probability=baseline_metrics.final_failure_probability,
        scenario_failure_probability=scenario_metrics.final_failure_probability,
        risk_delta_percentage_points=pp_diff,
        risk_reduction_pct=rel_reduction,
        baseline_output=round(baseline_metrics.total_output, 2),
        scenario_output=round(scenario_metrics.total_output, 2),
        throughput_loss_pct=throughput_loss_pct,
        peak_temp_delta=peak_temp_delta
    )
