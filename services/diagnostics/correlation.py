"""
NEXUS Correlation & Lagged Relationship Analysis Engine
Analyzes statistical associations, cross-correlations, and delayed responses between machine signals.

IMPORTANT SCIENTIFIC & ETHICAL NOTICE:
Correlation does NOT imply causation. In the NEXUS diagnostics framework, all correlation metrics
are treated strictly as statistical associations and supporting observational evidence,
NEVER as definitive or proven causal mechanisms.
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from scipy import stats

from services.schemas import CorrelationEvidence


class CorrelationEngine:
    """
    Computes pairwise Pearson and Spearman correlations, along with lagged cross-correlations.
    """

    LIMITATIONS_NOTICE = (
        "Statistical correlation measures linear or monotonic association across the observed time window. "
        "It does not establish causal direction or eliminate unobserved confounding factors. "
        "Correlations are supporting evidence only."
    )

    @staticmethod
    def calculate_correlations(
        data: Dict[str, List[float]],
        method: str = "spearman"
    ) -> Dict[Tuple[str, str], float]:
        """
        Calculates pairwise correlation coefficient between series of identical lengths.
        Spearman is default as it captures non-linear monotonic physical relationships and is robust to outliers.
        """
        keys = list(data.keys())
        results: Dict[Tuple[str, str], float] = {}

        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                k1, k2 = keys[i], keys[j]
                s1 = np.array(data[k1], dtype=float)
                s2 = np.array(data[k2], dtype=float)

                if len(s1) < 4 or len(s2) < 4:
                    continue
                if np.std(s1) == 0 or np.std(s2) == 0:
                    continue

                try:
                    if method == "pearson":
                        coeff, _ = stats.pearsonr(s1, s2)
                    else:
                        coeff, _ = stats.spearmanr(s1, s2)

                    if not np.isnan(coeff):
                        results[(k1, k2)] = float(coeff)
                except Exception:
                    continue

        return results

    @staticmethod
    def calculate_lagged_cross_correlation(
        series_leader: List[float],
        series_follower: List[float],
        max_lag: int = 5
    ) -> Tuple[int, float]:
        """
        Finds the lag k in [0, max_lag] that maximizes the cross-correlation where
        series_leader at t correlates with series_follower at t + k.
        Returns:
            optimal_lag: positive integer representing lag delay in discrete ticks
            max_corr: maximum correlation coefficient found
        """
        a = np.array(series_leader, dtype=float)
        b = np.array(series_follower, dtype=float)

        n = min(len(a), len(b))
        if n < max_lag + 4:
            return 0, 0.0

        std_a = np.std(a[:n])
        std_b = np.std(b[:n])
        if std_a == 0 or std_b == 0:
            return 0, 0.0

        best_lag = 0
        best_corr = 0.0

        for lag in range(0, max_lag + 1):
            if lag == 0:
                sub_a = a[:n]
                sub_b = b[:n]
            else:
                sub_a = a[:n - lag]
                sub_b = b[lag:n]

            if len(sub_a) < 4 or np.std(sub_a) == 0 or np.std(sub_b) == 0:
                continue

            try:
                corr, _ = stats.spearmanr(sub_a, sub_b)
                if not np.isnan(corr) and abs(corr) > abs(best_corr):
                    best_corr = float(corr)
                    best_lag = lag
            except Exception:
                continue

        return best_lag, best_corr

    @classmethod
    def analyze_signal_relationships(
        cls,
        series_map: Dict[str, List[float]],
        max_lag: int = 5
    ) -> List[CorrelationEvidence]:
        """
        Extracts salient physical cross-correlations and lagged relationships for reporting.
        """
        evidence_list: List[CorrelationEvidence] = []
        # Key coupled physical pairs of interest:
        key_pairs = [
            ("load", "current", "Load increase directly demands higher electrical current"),
            ("load", "temperature", "Elevated mechanical load leads internal temperature rise with thermal inertia"),
            ("current", "power_kw", "Active electrical current drives real power consumption"),
            ("vibration", "efficiency", "Elevated mechanical vibration correlates with mechanical drag and efficiency loss"),
            ("temperature", "efficiency", "Elevated operating temperature is consistent with thermal degradation of efficiency"),
        ]

        for s1, s2, physical_meaning in key_pairs:
            if s1 in series_map and s2 in series_map:
                v1 = series_map[s1]
                v2 = series_map[s2]
                lag, corr = cls.calculate_lagged_cross_correlation(v1, v2, max_lag=max_lag)

                if abs(corr) >= 0.50:
                    rel_text = (
                        f"'{s1}' is strongly correlated with '{s2}' (r={corr:.2f}, lag={lag} ticks)"
                        if lag > 0 else
                        f"'{s1}' is concurrently correlated with '{s2}' (r={corr:.2f})"
                    )
                    evidence_list.append(CorrelationEvidence(
                        signal_a=s1,
                        signal_b=s2,
                        method="spearman",
                        coefficient=round(corr, 3),
                        lag_ticks=lag,
                        relationship=rel_text,
                        interpretation=f"Consistent with domain physics: {physical_meaning}."
                    ))

        return evidence_list
