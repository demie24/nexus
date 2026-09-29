"""
NEXUS Explainable Root Cause Analysis (RCA) Report Generator
Formats structured diagnostic findings, itemized evidence bullet points, alternative candidates,
and technical limitations without dependency on Large Language Models (LLMs).
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from services.schemas import (
    DiagnosticReport,
    CauseCandidate,
    EvidenceItem,
    CorrelationEvidence,
    RootCauseType,
    DataProvenance,
)
from services.diagnostics.config import CAUSE_TAXONOMY


class DiagnosticReportGenerator:
    """
    Synthesizes human-readable and structured machine-readable RCA diagnostic reports.
    """

    LIMITATION_DISCLAIMER = (
        "Important limitation: RCA provides evidence-based ranking and physical consistency assessment; "
        "it does not establish definitive or guaranteed causality. Physical inspection by a qualified "
        "reliability engineer is recommended before maintenance intervention."
    )

    @classmethod
    def generate_text_report(
        cls,
        machine_id: str,
        incident_id: Optional[str],
        timestamp: datetime,
        likely_cause: RootCauseType,
        evidence_score: float,
        confidence: str,
        ranking: List[CauseCandidate],
        evidence_summary: List[EvidenceItem],
        correlations: List[CorrelationEvidence],
    ) -> str:
        """
        Builds a structured, human-readable plain text / markdown technical RCA incident report.
        """
        cause_def = CAUSE_TAXONOMY.get(likely_cause)
        cause_name = cause_def.name if cause_def else likely_cause.value

        lines = [
            "=" * 60,
            "NEXUS ROOT CAUSE ANALYSIS (RCA) REPORT",
            "=" * 60,
            f"Machine:             {machine_id}",
            f"Incident ID:         {incident_id or 'N/A (Continuous Monitoring)'}",
            f"Timestamp:           {timestamp.isoformat()}",
            f"Likely Contributor:  {cause_name}",
            f"Evidence Score:      {evidence_score:.2f} / 1.00",
            f"Data Confidence:     {confidence}",
            "-" * 60,
            "OBSERVED EVIDENCE & PHYSICAL DEVIATIONS:",
        ]

        if not evidence_summary:
            lines.append("  • No statistically significant signal deviations observed.")
        else:
            for item in evidence_summary[:8]:
                lines.append(f"  ✓ {item.description}")

        lines.extend([
            "-" * 60,
            "CANDIDATE CAUSE RANKING:",
        ])

        for c in ranking:
            cand_def = CAUSE_TAXONOMY.get(c.cause)
            cand_name = cand_def.name if cand_def else c.cause.value
            lines.append(
                f"  Rank {c.rank}: {cand_name:<26} | Score: {c.evidence_score:.2f} | Confidence: {c.confidence} | Consistency: {c.physical_consistency_status.value}"
            )

        # Alternative possibilities (ranks 2 and 3)
        alternatives = [c for c in ranking if c.rank in [2, 3] and c.cause != RootCauseType.UNKNOWN]
        if alternatives:
            lines.extend([
                "-" * 60,
                "ALTERNATIVE POSSIBILITIES TO INVESTIGATE:",
            ])
            for alt in alternatives:
                cand_def = CAUSE_TAXONOMY.get(alt.cause)
                cand_name = cand_def.name if cand_def else alt.cause.value
                lines.append(f"  • {cand_name} (Evidence score: {alt.evidence_score:.2f}, {alt.physical_consistency_status.value})")

        # Salient correlations
        if correlations:
            lines.extend([
                "-" * 60,
                "OBSERVED SIGNAL CORRELATIONS & DYNAMICS:",
            ])
            for corr in correlations[:4]:
                lines.append(f"  • {corr.relationship} — {corr.interpretation}")

        # Limitations
        lines.extend([
            "=" * 60,
            f"NOTE: {cls.LIMITATION_DISCLAIMER}",
            "=" * 60,
        ])

        return "\n".join(lines)

    @classmethod
    def generate_report(
        cls,
        diagnostic_id: str,
        machine_id: str,
        incident_id: Optional[str],
        timestamp: datetime,
        likely_cause: RootCauseType,
        evidence_score: float,
        confidence: str,
        ranking: List[CauseCandidate],
        evidence_summary: List[EvidenceItem],
        correlations: List[CorrelationEvidence],
        graph_paths: Dict[str, List[str]],
        metadata_info: Dict[str, Any],
    ) -> DiagnosticReport:
        """
        Creates the complete DiagnosticReport schema object.
        """
        text_rep = cls.generate_text_report(
            machine_id=machine_id,
            incident_id=incident_id,
            timestamp=timestamp,
            likely_cause=likely_cause,
            evidence_score=evidence_score,
            confidence=confidence,
            ranking=ranking,
            evidence_summary=evidence_summary,
            correlations=correlations,
        )

        alternative_candidates = [
            c for c in ranking
            if c.rank > 1 and c.cause != RootCauseType.UNKNOWN
        ]

        return DiagnosticReport(
            diagnostic_id=diagnostic_id,
            machine_id=machine_id,
            incident_id=incident_id,
            timestamp=timestamp,
            likely_cause=likely_cause,
            evidence_score=evidence_score,
            confidence=confidence,
            ranking=ranking,
            evidence_summary=evidence_summary,
            alternative_causes=alternative_candidates,
            correlations=correlations,
            graph_paths=graph_paths,
            text_report=text_rep,
            metadata_info=metadata_info,
            provenance=DataProvenance.DIAGNOSED,
        )
