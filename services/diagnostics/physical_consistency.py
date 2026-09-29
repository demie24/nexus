"""
NEXUS Physical Consistency Evaluation Engine
Validates candidate root causes against the known physical equations and thermodynamics
governing the industrial machinery.

Provides evidence of physical plausibility, NOT absolute proof.
"""

from typing import Dict, List, Optional, Tuple, Any
from services.schemas import RootCauseType, PhysicalConsistencyStatus, SignalDirection


class PhysicalConsistencyChecker:
    """
    Applies thermodynamic, electromechanical, and sensor noise consistency checks.
    """

    @classmethod
    def check_consistency(
        cls,
        cause: RootCauseType,
        observed_metrics: Dict[str, float],
        baseline_metrics: Dict[str, float],
        dynamics: Dict[str, Dict[str, Any]],
        anomaly_classifier_type: Optional[str] = None
    ) -> Tuple[PhysicalConsistencyStatus, float, List[str]]:
        """
        Evaluates physical consistency of a candidate cause given observed values and dynamics.
        Returns:
            status: PhysicalConsistencyStatus (CONSISTENT, INCONSISTENT, AMBIGUOUS)
            consistency_score: float in [0.0, 1.0]
            reasons: list of explanatory strings
        """
        if cause == RootCauseType.BEARING_DEGRADATION:
            return cls._check_bearing(observed_metrics, baseline_metrics, dynamics)

        elif cause == RootCauseType.COOLING_DEGRADATION:
            return cls._check_cooling(observed_metrics, baseline_metrics, dynamics)

        elif cause == RootCauseType.OVERLOAD:
            return cls._check_overload(observed_metrics, baseline_metrics, dynamics)

        elif cause == RootCauseType.MOTOR_INEFFICIENCY:
            return cls._check_motor(observed_metrics, baseline_metrics, dynamics)

        elif cause == RootCauseType.SENSOR_ANOMALY:
            return cls._check_sensor(observed_metrics, baseline_metrics, dynamics, anomaly_classifier_type)

        return PhysicalConsistencyStatus.AMBIGUOUS, 0.50, ["No specific physical model defined for UNKNOWN."]

    @staticmethod
    def _check_bearing(
        obs: Dict[str, float],
        base: Dict[str, float],
        dyn: Dict[str, Dict[str, Any]]
    ) -> Tuple[PhysicalConsistencyStatus, float, List[str]]:
        reasons = []
        vib_obs = obs.get("vibration", 0.0)
        vib_base = base.get("vibration", 1.8)
        eff_obs = obs.get("efficiency", 100.0)
        eff_base = base.get("efficiency", 100.0)
        load = obs.get("load", 1.0)

        vib_ratio = vib_obs / max(0.1, vib_base)
        eff_drop = eff_base - eff_obs

        # Normalized vibration by load (rules out simple load-induced vibration)
        norm_vib = vib_obs / max(0.2, load)

        vib_dyn = dyn.get("vibration", {})
        eff_dyn = dyn.get("efficiency", {})

        score = 0.0
        # 1. Primary check: elevated vibration + degraded efficiency
        if vib_ratio >= 1.35 and eff_drop >= 3.0:
            score += 0.50
            reasons.append(f"Vibration is elevated (+{(vib_ratio - 1.0)*100:.1f}%) concurrently with efficiency decline (-{eff_drop:.1f}%).")
        elif vib_ratio >= 1.20:
            score += 0.25
            reasons.append(f"Vibration is moderately elevated (+{(vib_ratio - 1.0)*100:.1f}%).")

        # 2. Load-normalized vibration check
        if norm_vib > 1.4 * vib_base:
            score += 0.25
            reasons.append(f"Load-normalized vibration ({norm_vib:.2f}) significantly exceeds baseline ({vib_base:.2f}), indicating mechanical friction rather than operational load.")

        # 3. Persistence of vibration and efficiency drift
        if vib_dyn.get("is_persistent", False) and eff_dyn.get("direction") == SignalDirection.DECREASING:
            score += 0.25
            reasons.append("Vibration trend demonstrates persistence rather than transient sensor noise.")

        # Contraindications:
        if vib_ratio < 1.05:
            score -= 0.40
            reasons.append("Vibration is nominal, which strongly contradicts mechanical bearing degradation.")
        if eff_obs > eff_base + 2.0:
            score -= 0.30
            reasons.append("Efficiency is higher than baseline, contradicting frictional drag.")

        score = min(1.0, max(0.0, score))
        status = (
            PhysicalConsistencyStatus.CONSISTENT if score >= 0.65
            else (PhysicalConsistencyStatus.INCONSISTENT if score < 0.30 else PhysicalConsistencyStatus.AMBIGUOUS)
        )
        return status, score, reasons

    @staticmethod
    def _check_cooling(
        obs: Dict[str, float],
        base: Dict[str, float],
        dyn: Dict[str, Dict[str, Any]]
    ) -> Tuple[PhysicalConsistencyStatus, float, List[str]]:
        reasons = []
        temp_obs = obs.get("temperature", 45.0)
        temp_base = base.get("temperature", 45.0)
        eff_obs = obs.get("efficiency", 100.0)
        eff_base = base.get("efficiency", 100.0)
        load = obs.get("load", 1.0)
        vib_obs = obs.get("vibration", 1.8)
        vib_base = base.get("vibration", 1.8)

        temp_diff = temp_obs - temp_base
        eff_drop = eff_base - eff_obs
        temp_dyn = dyn.get("temperature", {})

        score = 0.0
        # 1. Thermal rise while load is nominal (< 1.10)
        if temp_diff >= 8.0 and load <= 1.10:
            score += 0.50
            reasons.append(f"Operating temperature is elevated (+{temp_diff:.1f}°C) despite nominal load ({load:.2f}), consistent with heat dissipation impairment.")
        elif temp_diff >= 4.0:
            score += 0.25
            reasons.append(f"Operating temperature is moderately elevated (+{temp_diff:.1f}°C).")

        # 2. Positive thermal trend slope
        if temp_dyn.get("direction") == SignalDirection.INCREASING and temp_dyn.get("is_persistent", False):
            score += 0.30
            reasons.append(f"Persistent positive thermal drift detected (slope={temp_dyn.get('slope', 0):.3f}°C/tick).")

        # 3. Vibration is nominal (rules out severe mechanical seizure)
        if vib_obs <= 1.30 * vib_base:
            score += 0.20
            reasons.append("Vibration remains near nominal, indicating thermal rather than structural mechanical origin.")

        # Contraindications:
        if temp_diff < 2.0:
            score -= 0.50
            reasons.append("Operating temperature is normal, contradicting cooling degradation.")
        if load >= 1.25:
            score -= 0.25
            reasons.append("Machine is under heavy overload, which acts as a primary confounding cause for temperature rise.")

        score = min(1.0, max(0.0, score))
        status = (
            PhysicalConsistencyStatus.CONSISTENT if score >= 0.65
            else (PhysicalConsistencyStatus.INCONSISTENT if score < 0.30 else PhysicalConsistencyStatus.AMBIGUOUS)
        )
        return status, score, reasons

    @staticmethod
    def _check_overload(
        obs: Dict[str, float],
        base: Dict[str, float],
        dyn: Dict[str, Dict[str, Any]]
    ) -> Tuple[PhysicalConsistencyStatus, float, List[str]]:
        reasons = []
        load = obs.get("load", 1.0)
        curr_obs = obs.get("current", 20.0)
        curr_base = base.get("current", 20.0)
        pwr_obs = obs.get("power_kw", 10.0)
        pwr_base = base.get("power_kw", 10.0)
        temp_obs = obs.get("temperature", 45.0)
        temp_base = base.get("temperature", 45.0)

        load_dyn = dyn.get("load", {})
        curr_ratio = curr_obs / max(0.1, curr_base)
        pwr_ratio = pwr_obs / max(0.1, pwr_base)

        score = 0.0
        # 1. Load factor > 1.05
        if load >= 1.15:
            score += 0.40
            reasons.append(f"Measured machine load factor ({load:.2f}) significantly exceeds rated capacity (1.00).")
        elif load > 1.05:
            score += 0.20
            reasons.append(f"Measured machine load factor ({load:.2f}) slightly exceeds rated capacity.")

        # 2. Coupled electrical surge (current & power)
        if curr_ratio >= 1.15 and pwr_ratio >= 1.15:
            score += 0.40
            reasons.append(f"Direct electromechanical coupling observed: Current (+{(curr_ratio-1)*100:.1f}%) and Power (+{(pwr_ratio-1)*100:.1f}%) rise proportionally with demand.")

        # 3. Thermal response
        if temp_obs > temp_base + 3.0:
            score += 0.20
            reasons.append("Thermal dissipation reflects expected Joule heating from sustained electrical overload.")

        # Contraindications:
        if load <= 1.02 and load_dyn.get("direction") != SignalDirection.INCREASING:
            score -= 0.50
            reasons.append("Measured operational load is at or below rated threshold, contradicting active overload.")

        score = min(1.0, max(0.0, score))
        status = (
            PhysicalConsistencyStatus.CONSISTENT if score >= 0.65
            else (PhysicalConsistencyStatus.INCONSISTENT if score < 0.30 else PhysicalConsistencyStatus.AMBIGUOUS)
        )
        return status, score, reasons

    @staticmethod
    def _check_motor(
        obs: Dict[str, float],
        base: Dict[str, float],
        dyn: Dict[str, Dict[str, Any]]
    ) -> Tuple[PhysicalConsistencyStatus, float, List[str]]:
        reasons = []
        eff_obs = obs.get("efficiency", 100.0)
        eff_base = base.get("efficiency", 100.0)
        load = obs.get("load", 1.0)
        pwr_obs = obs.get("power_kw", 10.0)
        pwr_base = base.get("power_kw", 10.0)
        vib_obs = obs.get("vibration", 1.8)
        vib_base = base.get("vibration", 1.8)

        eff_drop = eff_base - eff_obs
        specific_power = pwr_obs / max(0.1, load)
        base_specific_power = pwr_base / max(0.1, base.get("load", 1.0))

        score = 0.0
        # 1. Significant efficiency drop without massive vibration
        if eff_drop >= 5.0 and (vib_obs <= 1.35 * vib_base):
            score += 0.45
            reasons.append(f"Efficiency degraded (-{eff_drop:.1f}%) in the absence of severe mechanical vibration, pointing to internal electrical or drive losses.")

        # 2. Specific power consumption elevated
        if specific_power >= 1.15 * base_specific_power:
            score += 0.35
            reasons.append(f"Specific electrical consumption per unit load (+{(specific_power/base_specific_power - 1)*100:.1f}%) indicates power conversion losses.")

        # 3. Persistent degradation
        eff_dyn = dyn.get("efficiency", {})
        if eff_dyn.get("is_persistent", False):
            score += 0.20
            reasons.append("Efficiency deficit is sustained over time.")

        # Contraindications:
        if eff_drop < 2.0:
            score -= 0.50
            reasons.append("Efficiency remains nominal, contradicting motor degradation.")
        if vib_obs >= 2.0 * vib_base:
            score -= 0.30
            reasons.append("Dominant high vibration strongly favors bearing degradation over isolated motor inefficiency.")

        score = min(1.0, max(0.0, score))
        status = (
            PhysicalConsistencyStatus.CONSISTENT if score >= 0.65
            else (PhysicalConsistencyStatus.INCONSISTENT if score < 0.30 else PhysicalConsistencyStatus.AMBIGUOUS)
        )
        return status, score, reasons

    @staticmethod
    def _check_sensor(
        obs: Dict[str, float],
        base: Dict[str, float],
        dyn: Dict[str, Dict[str, Any]],
        anomaly_classifier_type: Optional[str] = None
    ) -> Tuple[PhysicalConsistencyStatus, float, List[str]]:
        reasons = []
        score = 0.0

        # Check if Phase 4 classifier already flagged SENSOR_ANOMALY
        if anomaly_classifier_type == "SENSOR_ANOMALY":
            score += 0.50
            reasons.append("Phase 4 Anomaly Classifier confirmed isolated single-channel sensor artifact.")

        # Check for isolated deviation: exactly one signal deviates sharply while coupled physical signals remain nominal
        spiking_signals = [sig for sig, d in dyn.items() if d.get("is_spike", False) or abs(d.get("net_dev_z", 0.0)) >= 3.0]
        nominal_signals = [sig for sig, d in dyn.items() if abs(d.get("net_dev_z", 0.0)) < 1.5]

        if len(spiking_signals) == 1 and len(nominal_signals) >= 3:
            score += 0.40
            spike_name = spiking_signals[0]
            reasons.append(f"Isolated anomaly on sensor '{spike_name}' while coupled physical channels ({', '.join(nominal_signals[:3])}) remain completely nominal.")

        # If multiple coupled physical signals are simultaneously degrading, sensor anomaly is highly improbable
        if len(spiking_signals) >= 2 and len(nominal_signals) <= 1:
            score -= 0.40
            reasons.append("Multiple coupled parameters are deviating together, which contradicts isolated sensor malfunction.")

        score = min(1.0, max(0.0, score))
        status = (
            PhysicalConsistencyStatus.CONSISTENT if score >= 0.65
            else (PhysicalConsistencyStatus.INCONSISTENT if score < 0.30 else PhysicalConsistencyStatus.AMBIGUOUS)
        )
        return status, score, reasons
