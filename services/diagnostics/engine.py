"""
NEXUS Root Cause Analysis (RCA) Engine Orchestrator
Coordinates dependency graph reasoning, physical consistency validation,
correlation analysis, temporal dynamics, evidence fusion, and persistence.
"""

from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional, Tuple, Any
import uuid
import numpy as np

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from database.models.models import (
    DiagnosticModel,
    TelemetryModel,
    MachineModel,
    MachineStateModel,
    AnomalyModel,
    PredictionModel,
)
from services.schemas import (
    TelemetryCreate,
    DiagnosticReport,
    DiagnosticAnalysisRequest,
    DiagnosticAnalysisResponse,
    RootCauseType,
    PhysicalConsistencyStatus,
    CauseCandidate,
    EvidenceItem,
    DataProvenance,
)
from services.diagnostics.config import (
    DIAGNOSTIC_VERSION,
    FEATURE_VERSION,
    RULE_VERSION,
    MODEL_VERSION,
    CAUSE_TAXONOMY,
)
from services.diagnostics.graph import get_dependency_graph, DiagnosticDependencyGraph
from services.diagnostics.correlation import CorrelationEngine
from services.diagnostics.temporal import TemporalReasoningEngine
from services.diagnostics.fusion import EvidenceFusionEngine
from services.diagnostics.report import DiagnosticReportGenerator

logger = logging.getLogger("nexus.diagnostics")


class RootCauseAnalysisEngine:
    """
    Core engine orchestrating Root Cause Analysis across telemetry streams and incident windows.
    """

    def __init__(self, graph: Optional[DiagnosticDependencyGraph] = None):
        self.graph = graph or get_dependency_graph()
        self.correlation_engine = CorrelationEngine()
        self.temporal_engine = TemporalReasoningEngine()
        self.fusion_engine = EvidenceFusionEngine(self.graph)
        self.report_generator = DiagnosticReportGenerator()

    def analyze_from_telemetry(
        self,
        telemetry_records: List[TelemetryCreate],
        baseline_stats: Dict[str, Tuple[float, float]],
        machine_id: str,
        incident_id: Optional[str] = None,
        analysis_timestamp: Optional[datetime] = None,
        anomaly_context: Optional[Dict[str, Any]] = None,
        prediction_context: Optional[Dict[str, Any]] = None,
    ) -> DiagnosticReport:
        """
        Pure in-memory execution of Root Cause Analysis on a telemetry window.
        Safe from data leakage; strictly enforces records <= analysis_timestamp.
        """
        timestamp = analysis_timestamp or datetime.now(timezone.utc)
        # Ensure UTC timezone awareness if naive
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        # 1. Enforce temporal leakage protection
        valid_records = self.temporal_engine.enforce_no_future_leakage(telemetry_records, timestamp)

        diagnostic_id = f"RCA-{machine_id}-{timestamp.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        metadata_info = {
            "diagnostic_version": DIAGNOSTIC_VERSION,
            "feature_version": FEATURE_VERSION,
            "rule_version": RULE_VERSION,
            "model_version": MODEL_VERSION,
            "analysis_timestamp": timestamp.isoformat(),
            "input_window": len(valid_records),
            "machine_id": machine_id,
            "incident_id": incident_id,
        }

        # Insufficient telemetry guard (Cold-start / empty window)
        if len(valid_records) < 3:
            unknown_candidate = CauseCandidate(
                cause=RootCauseType.UNKNOWN,
                rank=1,
                evidence_score=0.0,
                confidence="LOW",
                physical_consistency_status=PhysicalConsistencyStatus.AMBIGUOUS,
                evidence=[],
                summary="Insufficient telemetry observations in specified analysis window (minimum 3 records required)."
            )
            return self.report_generator.generate_report(
                diagnostic_id=diagnostic_id,
                machine_id=machine_id,
                incident_id=incident_id,
                timestamp=timestamp,
                likely_cause=RootCauseType.UNKNOWN,
                evidence_score=0.0,
                confidence="LOW",
                ranking=[unknown_candidate],
                evidence_summary=[],
                correlations=[],
                graph_paths={},
                metadata_info=metadata_info,
            )

        # 2. Extract series per signal
        signal_names = ["temperature", "vibration", "current", "power_kw", "load", "efficiency", "pressure", "rpm"]
        series_map: Dict[str, List[float]] = {sig: [] for sig in signal_names}
        for rec in valid_records:
            for sig in signal_names:
                val = getattr(rec, sig, None)
                if val is not None:
                    series_map[sig].append(float(val))

        # Recent snapshot values (mean of last 3 ticks or last tick)
        observed_values: Dict[str, float] = {}
        for sig, vals in series_map.items():
            if vals:
                observed_values[sig] = float(np.mean(vals[-max(1, min(3, len(vals))):]))

        # 3. Temporal reasoning & signal dynamics
        dynamics: Dict[str, Dict[str, Any]] = {}
        for sig, vals in series_map.items():
            if sig in baseline_stats:
                b_mean, b_std = baseline_stats[sig]
                dynamics[sig] = self.temporal_engine.evaluate_signal_dynamics(vals, b_mean, b_std)

        # 4. Correlation and lagged cross-correlation
        correlations = self.correlation_engine.analyze_signal_relationships(series_map, max_lag=5)

        # 5. Extract explainable graph paths for all causes
        graph_paths: Dict[str, List[str]] = {}
        for cause in CAUSE_TAXONOMY:
            if cause != RootCauseType.UNKNOWN:
                paths = []
                for sig in ["vibration", "temperature", "current", "load", "efficiency"]:
                    p = self.graph.explain_path(cause, sig)
                    if p:
                        paths.extend(p)
                if paths:
                    graph_paths[cause.value] = paths[:3]

        # 6. Multi-source evidence fusion & scoring
        likely_cause, top_score, confidence, ranking, evidence_summary = self.fusion_engine.fuse_evidence(
            observed_values=observed_values,
            baseline_stats=baseline_stats,
            dynamics=dynamics,
            anomaly_context=anomaly_context,
            prediction_context=prediction_context,
        )

        # 7. Synthesize comprehensive report
        return self.report_generator.generate_report(
            diagnostic_id=diagnostic_id,
            machine_id=machine_id,
            incident_id=incident_id,
            timestamp=timestamp,
            likely_cause=likely_cause,
            evidence_score=top_score,
            confidence=confidence,
            ranking=ranking,
            evidence_summary=evidence_summary,
            correlations=correlations,
            graph_paths=graph_paths,
            metadata_info=metadata_info,
        )

    def analyze_machine(
        self,
        machine_id: str,
        db: Session,
        incident_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        window_size: int = 30,
        persist: bool = True,
    ) -> DiagnosticReport:
        """
        Executes end-to-end database-backed Root Cause Analysis for a machine or specific incident.
        """
        machine = db.query(MachineModel).filter_by(id=machine_id).first()
        if not machine:
            raise ValueError(f"Machine '{machine_id}' is not registered in system.")

        now_utc = datetime.now(timezone.utc)
        analysis_timestamp = end_time if end_time else now_utc
        if analysis_timestamp.tzinfo is None:
            analysis_timestamp = analysis_timestamp.replace(tzinfo=timezone.utc)

        # Retrieve telemetry records within window
        tel_query = db.query(TelemetryModel).filter(
            TelemetryModel.machine_id == machine_id,
            TelemetryModel.timestamp <= analysis_timestamp
        )
        if start_time:
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
            tel_query = tel_query.filter(TelemetryModel.timestamp >= start_time)

        # Order chronologically ascending for analysis
        tel_records_db = (
            tel_query.order_by(desc(TelemetryModel.timestamp))
            .limit(window_size)
            .all()
        )
        tel_records_db.reverse()

        # Convert to TelemetryCreate schemas
        telemetry_creates = [
            TelemetryCreate(
                machine_id=t.machine_id,
                timestamp=t.timestamp,
                temperature=t.temperature,
                vibration=t.vibration,
                pressure=t.pressure,
                current=t.current,
                voltage=t.voltage,
                rpm=t.rpm,
                power_kw=t.power_kw,
                load=t.load,
                output_rate=t.output_rate,
                efficiency=t.efficiency,
                quality_indicator=t.quality_indicator,
            )
            for t in tel_records_db
        ]

        # Formulate baseline statistics from machine specs and machine state
        baselines = self._resolve_machine_baselines(machine, db)

        # Retrieve recent anomaly context
        anomaly_context = {}
        recent_anomaly = (
            db.query(AnomalyModel)
            .filter(
                AnomalyModel.machine_id == machine_id,
                AnomalyModel.timestamp <= analysis_timestamp
            )
            .order_by(desc(AnomalyModel.timestamp))
            .first()
        )
        if recent_anomaly:
            anomaly_context = {
                "anomaly_type": recent_anomaly.anomaly_type,
                "anomaly_score": recent_anomaly.anomaly_score,
                "triggered_signals": recent_anomaly.triggered_signals or [],
                "detector_evidence": recent_anomaly.detector_evidence or {},
            }

        # Retrieve recent prediction context
        prediction_context = {}
        recent_pred = (
            db.query(PredictionModel)
            .filter(
                PredictionModel.machine_id == machine_id,
                PredictionModel.timestamp <= analysis_timestamp
            )
            .order_by(desc(PredictionModel.timestamp))
            .first()
        )
        if recent_pred:
            prediction_context = {
                "risk_level": recent_pred.risk_level,
                "remaining_useful_life_hours": recent_pred.remaining_useful_life_hours,
                "predicted_failure_probability": recent_pred.predicted_failure_probability,
            }

        # Run pure RCA inference
        report = self.analyze_from_telemetry(
            telemetry_records=telemetry_creates,
            baseline_stats=baselines,
            machine_id=machine_id,
            incident_id=incident_id,
            analysis_timestamp=analysis_timestamp,
            anomaly_context=anomaly_context,
            prediction_context=prediction_context,
        )

        # Persist if requested
        if persist:
            self.persist_diagnostic(report, db)

        return report

    def persist_diagnostic(self, report: DiagnosticReport, db: Session) -> DiagnosticModel:
        """
        Saves diagnostic result to PostgreSQL database.
        """
        ranking_dicts = [c.model_dump() for c in report.ranking]
        evidence_dicts = [e.model_dump() for e in report.evidence_summary]

        model = DiagnosticModel(
            diagnostic_id=report.diagnostic_id,
            machine_id=report.machine_id,
            incident_id=report.incident_id,
            timestamp=report.timestamp,
            likely_cause=report.likely_cause.value,
            evidence_score=report.evidence_score,
            confidence=report.confidence,
            ranking=ranking_dicts,
            evidence_summary=evidence_dicts,
            text_report=report.text_report,
            metadata_info=report.metadata_info,
            provenance="DIAGNOSED",
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        return model

    @staticmethod
    def _resolve_machine_baselines(
        machine: MachineModel,
        db: Session
    ) -> Dict[str, Tuple[float, float]]:
        """
        Constructs baseline (mean, std) for each signal from machine parameters.
        """
        # Nominal reference values from machine specs
        nom_power = machine.nominal_power_kw or 15.0
        nom_rpm = machine.nominal_rpm or 1500.0
        nom_temp = 45.0
        nom_vib = 1.80
        nom_curr = nom_power * 1000.0 / (1.732 * 400.0 * 0.88)

        # Expected baseline std based on typical sensor noise
        return {
            "temperature": (nom_temp, 1.2),
            "vibration": (nom_vib, 0.15),
            "current": (nom_curr, 0.8),
            "power_kw": (nom_power, 0.4),
            "load": (1.00, 0.05),
            "efficiency": (100.0, 1.5),
            "pressure": (2.5, 0.1),
            "rpm": (nom_rpm, 15.0),
        }


# Singleton engine instance
_rca_engine_instance: Optional[RootCauseAnalysisEngine] = None


def get_rca_engine() -> RootCauseAnalysisEngine:
    global _rca_engine_instance
    if _rca_engine_instance is None:
        _rca_engine_instance = RootCauseAnalysisEngine()
    return _rca_engine_instance
