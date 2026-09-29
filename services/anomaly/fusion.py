"""
NEXUS Anomaly Fusion & Explainability Engine
Fuses evidence from Statistical, Rolling Trend, and Isolation Forest detectors
into a unified, explainable anomaly score and assigns operational severity.
"""

from typing import Dict, List, Any
from services.schemas import SeverityLevel, AnomalyType
from services.anomaly.config import get_anomaly_config


class AnomalyFusionEngine:
    def __init__(self):
        self.config = get_anomaly_config()

    def fuse(
        self,
        statistical_evidence: Dict[str, Any],
        trend_evidence: Dict[str, Any],
        isolation_evidence: Dict[str, Any],
        classification: Dict[str, Any],
        pct_deviations: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Fuses detector scores via weighted consensus, maps to severity,
        and constructs transparent explainability evidence.
        """
        s_stat = statistical_evidence.get("score", 0.0)
        s_trend = trend_evidence.get("score", 0.0)
        s_iforest = isolation_evidence.get("score", 0.0)

        # Weighted combination
        raw_unified = (
            self.config.weight_statistical * s_stat +
            self.config.weight_rolling_trend * s_trend +
            self.config.weight_isolation_forest * s_iforest
        )

        # Multi-detector consensus bonus:
        # If all 3 detectors indicate anomaly (> 0.40), increase confidence
        if s_stat >= 0.40 and s_trend >= 0.40 and s_iforest >= 0.40:
            raw_unified = min(1.0, raw_unified * 1.10)

        # Sensor Anomaly adjustment:
        # Isolated sensor spikes should not trigger false CRITICAL machine panic
        anomaly_type: AnomalyType = classification["type"]
        if anomaly_type == AnomalyType.SENSOR_ANOMALY:
            # Dampen score to MEDIUM or LOW ceiling
            unified_score = min(0.65, round(raw_unified, 3))
        else:
            unified_score = min(1.0, max(0.0, round(raw_unified, 3)))

        # Severity Mapping
        if unified_score < self.config.severity_normal_max:
            severity = SeverityLevel.NORMAL
        elif unified_score < self.config.severity_low_max:
            severity = SeverityLevel.LOW
        elif unified_score < self.config.severity_medium_max:
            severity = SeverityLevel.MEDIUM
        elif unified_score < self.config.severity_high_max:
            severity = SeverityLevel.HIGH
        else:
            severity = SeverityLevel.CRITICAL

        # Identify all triggered signals
        stat_triggered = statistical_evidence.get("triggered_signals", [])
        trend_triggered = trend_evidence.get("trending_signals", [])
        all_triggered = sorted(list(set(stat_triggered + trend_triggered)))

        # Detectors that contributed meaningfully
        active_detectors = []
        if s_stat >= 0.35:
            active_detectors.append("Statistical Z-Score")
        if s_trend >= 0.35:
            active_detectors.append("Rolling Trend")
        if s_iforest >= 0.50:
            active_detectors.append("Isolation Forest")

        # Explainability text generation
        explanation_lines = [
            f"Unified Anomaly Score: {unified_score:.2f} ({severity.value}).",
            f"Classification: {anomaly_type.value} — {classification['reason']}",
        ]
        if all_triggered:
            dev_str = ", ".join(f"{s}: {pct_deviations.get(s, 0.0):+.1f}%" for s in all_triggered)
            explanation_lines.append(f"Baseline Deviations: [{dev_str}].")
        if active_detectors:
            explanation_lines.append(f"Contributing Detectors: {', '.join(active_detectors)}.")
        else:
            explanation_lines.append("No detectors crossed anomalous threshold.")

        explanation = " ".join(explanation_lines)

        evidence_dict = {
            "statistical": statistical_evidence,
            "rolling_trend": trend_evidence,
            "isolation_forest": isolation_evidence,
            "classification": classification,
            "active_detectors": active_detectors,
            "pct_deviations": {k: v for k, v in pct_deviations.items() if abs(v) > 5.0},
        }

        return {
            "unified_score": unified_score,
            "severity": severity,
            "anomaly_type": anomaly_type,
            "all_triggered_signals": all_triggered,
            "evidence": evidence_dict,
            "explanation": explanation,
            "is_anomaly": severity != SeverityLevel.NORMAL,
        }
