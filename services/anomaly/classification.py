"""
NEXUS Anomaly Classification Engine
Strictly distinguishes between isolated SENSOR_ANOMALY, coherent MACHINE_BEHAVIOR,
and joint MULTIVARIATE_ANOMALY using physical thermodynamic/electrical correlation rules.
"""

from typing import Dict, List, Any
from services.schemas import AnomalyType


class AnomalyClassifier:
    @staticmethod
    def classify(
        statistical_evidence: Dict[str, Any],
        trend_evidence: Dict[str, Any],
        isolation_evidence: Dict[str, Any],
        pct_deviations: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Classifies anomaly into SENSOR_ANOMALY, MACHINE_BEHAVIOR, or MULTIVARIATE_ANOMALY.
        """
        triggered_signals = statistical_evidence.get("triggered_signals", [])
        trending_signals = trend_evidence.get("trending_signals", [])
        z_scores = statistical_evidence.get("z_scores", {})
        iforest_score = isolation_evidence.get("score", 0.0)

        # 1. Evaluate Sensor Anomaly:
        # Exactly ONE signal has an extreme spike, while other physically coupled signals remain nominal.
        if len(triggered_signals) == 1:
            spike_signal = triggered_signals[0]
            # Check remaining core signals: none should have significant deviation (Z < 1.8)
            other_z = [z for sig, z in z_scores.items() if sig != spike_signal and sig in ["temperature", "current", "power_kw", "efficiency"]]
            max_other_z = max(other_z) if other_z else 0.0

            if max_other_z < 1.8:
                return {
                    "type": AnomalyType.SENSOR_ANOMALY,
                    "reason": f"Isolated sensor spike on '{spike_signal}' (Z={z_scores.get(spike_signal)}) while all correlated machine parameters remain completely nominal (max coupled Z={max_other_z})."
                }

        # 2. Evaluate Machine Behavior Anomaly:
        # Cross-signal physical correlations indicating actual mechanical or thermal asset degradation:
        # a. Bearing/Mechanical: Vibration elevated + Efficiency degraded
        vib_high = z_scores.get("vibration", 0.0) >= 2.0 or "vibration" in trending_signals
        eff_low = z_scores.get("efficiency", 0.0) >= 1.5 or pct_deviations.get("efficiency", 0.0) < -3.0
        # b. Thermal: Temperature elevated + Efficiency degraded
        temp_high = z_scores.get("temperature", 0.0) >= 2.0 or "temperature" in trending_signals
        # c. Overload: Current elevated + Power elevated
        curr_high = z_scores.get("current", 0.0) >= 2.0
        pwr_high = z_scores.get("power_kw", 0.0) >= 2.0

        if (vib_high and eff_low) or (temp_high and eff_low) or (curr_high and pwr_high) or len(triggered_signals) >= 2:
            coupled_signals = list(set(triggered_signals + trending_signals))
            return {
                "type": AnomalyType.MACHINE_BEHAVIOR,
                "reason": f"Coherent multi-signal physical degradation detected across coupled parameters: {coupled_signals}. Consistent with mechanical, thermal, or electrical stress."
            }

        # 3. Multivariate Anomaly (default or subtle joint outlier detected by Isolation Forest)
        if iforest_score >= 0.60:
            return {
                "type": AnomalyType.MULTIVARIATE_ANOMALY,
                "reason": f"Joint multi-dimensional density outlier detected by Isolation Forest (score={iforest_score}) across high-dimensional feature space."
            }

        return {
            "type": AnomalyType.MULTIVARIATE_ANOMALY,
            "reason": "Multivariate behavioral drift detected across system operational metrics."
        }
