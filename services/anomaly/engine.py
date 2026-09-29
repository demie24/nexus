"""
NEXUS Anomaly Detection Engine Orchestrator
Coordinates feature extraction, multi-layered statistical, trend, and unsupervised ML detectors,
evidence fusion, lifecycle tracking, and asynchronous event bus integration.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import logging
import time
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

from database.session import SessionLocal
from database.models.models import AnomalyModel, MachineModel
from services.schemas import (
    TelemetryCreate,
    AnomalyAnalysisResponse,
    MachineAnomalyStatus,
    AnomalyType,
    AnomalyLifecycleStatus,
    SeverityLevel,
    Anomaly,
)
from services.ingestion.events import get_event_bus, IngestionEventType, IngestionEvent
from services.anomaly.config import get_anomaly_config
from services.anomaly.baseline import get_baseline_manager
from services.anomaly.features import get_feature_extractor
from services.anomaly.detectors import (
    StatisticalAnomalyDetector,
    RollingTrendDetector,
    IsolationForestDetector,
)
from services.anomaly.classification import AnomalyClassifier
from services.anomaly.fusion import AnomalyFusionEngine
from services.anomaly.lifecycle import get_lifecycle_manager

logger = logging.getLogger("nexus.anomaly.engine")


class AnomalyEngine:
    def __init__(self):
        self.config = get_anomaly_config()
        self.baseline_manager = get_baseline_manager()
        self.feature_extractor = get_feature_extractor()
        self.statistical_detector = StatisticalAnomalyDetector()
        self.trend_detector = RollingTrendDetector()
        self.isolation_forest_detector = IsolationForestDetector()
        self.classifier = AnomalyClassifier()
        self.fusion_engine = AnomalyFusionEngine()
        self.lifecycle_manager = get_lifecycle_manager()
        self.event_bus = get_event_bus()

        # Threadpool for asynchronous decoupled event processing
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="nexus-anomaly-worker")
        self._subscribe_to_ingestion_events()

    def _subscribe_to_ingestion_events(self) -> None:
        """Attaches non-blocking asynchronous listener to Telemetry Ingestion events."""
        def on_telemetry_ingested(evt: IngestionEvent):
            data = evt.data
            m_id = data.get("machine_id")
            if not m_id:
                return

            def run_async_analysis():
                session = SessionLocal()
                try:
                    # In normal operation, recent telemetry is retrieved and evaluated
                    history = self.feature_extractor.get_history(m_id)
                    if history:
                        latest_tel = history[-1]
                        self.analyze(latest_tel, session, persist_if_detected=True)
                except Exception as exc:
                    logger.error(f"Async anomaly analysis error for machine {m_id}: {exc}")
                finally:
                    session.close()

            self._executor.submit(run_async_analysis)

        self.event_bus.subscribe(IngestionEventType.TELEMETRY_INGESTED, on_telemetry_ingested)
        logger.info("AnomalyEngine successfully subscribed to TELEMETRY_INGESTED events.")

    def analyze(
        self,
        telemetry: TelemetryCreate,
        db: Session,
        persist_if_detected: bool = True
    ) -> AnomalyAnalysisResponse:
        """
        Executes end-to-end anomaly analysis pipeline on a single telemetry frame:
        1. Cold-start check
        2. Feature extraction (rolling stats, slopes, load-normalized values)
        3. Detector execution (Statistical Z-Score, Rolling Trend, Isolation Forest)
        4. Cross-signal physical classification (Sensor Anomaly vs Machine Behavior)
        5. Fusion & explainability generation
        6. Lifecycle state tracking (Temporal Persistence)
        7. Database persistence (if anomalous)
        """
        t_start = time.perf_counter()
        m_id = telemetry.machine_id

        # 1. Baseline & Cold-Start Check
        baseline = self.baseline_manager.get_baseline(m_id)
        is_established = baseline.is_established(min_samples=self.config.min_baseline_samples_required)

        # 2. Feature Extraction
        t_feat = time.perf_counter()
        features = self.feature_extractor.extract_features(telemetry, baseline)
        self.feature_extractor.push_telemetry(telemetry)
        feat_time_ms = (time.perf_counter() - t_feat) * 1000.0

        if not is_established:
            # Accumulate normal baseline profile during cold-start period
            baseline.update(telemetry)
            total_ms = (time.perf_counter() - t_start) * 1000.0
            return AnomalyAnalysisResponse(
                machine_id=m_id,
                timestamp=telemetry.timestamp,
                anomaly_detected=False,
                anomaly_score=0.0,
                severity=SeverityLevel.NORMAL,
                anomaly_type=None,
                status=AnomalyLifecycleStatus.INSUFFICIENT_BASELINE,
                primary_metric="none",
                observed_value=0.0,
                expected_value=0.0,
                threshold=0.0,
                triggered_signals=[],
                detector_evidence={
                    "status": "INSUFFICIENT_BASELINE",
                    "samples_collected": baseline.sample_count,
                    "required_samples": self.config.min_baseline_samples_required,
                    "latencies_ms": {"total": round(total_ms, 3), "feature_extraction": round(feat_time_ms, 3)}
                },
                explanation=f"Insufficient baseline history ({baseline.sample_count}/{self.config.min_baseline_samples_required} samples). Collecting baseline profile.",
                persisted_anomaly_id=None
            )

        # 3. Detectors Execution
        t_stat = time.perf_counter()
        stat_evidence = self.statistical_detector.detect(telemetry, features, baseline)
        stat_time_ms = (time.perf_counter() - t_stat) * 1000.0

        t_trend = time.perf_counter()
        trend_evidence = self.trend_detector.detect(telemetry, features)
        trend_time_ms = (time.perf_counter() - t_trend) * 1000.0

        t_iforest = time.perf_counter()
        iforest_evidence = self.isolation_forest_detector.detect(features)
        iforest_time_ms = (time.perf_counter() - t_iforest) * 1000.0

        # 4. Anomaly Classification
        classification = self.classifier.classify(
            statistical_evidence=stat_evidence,
            trend_evidence=trend_evidence,
            isolation_evidence=iforest_evidence,
            pct_deviations=features["pct_deviations"]
        )

        # 5. Fusion & Severity Assignment
        t_fuse = time.perf_counter()
        fusion_result = self.fusion_engine.fuse(
            statistical_evidence=stat_evidence,
            trend_evidence=trend_evidence,
            isolation_evidence=iforest_evidence,
            classification=classification,
            pct_deviations=features["pct_deviations"]
        )
        fuse_time_ms = (time.perf_counter() - t_fuse) * 1000.0

        is_anomalous = fusion_result["is_anomaly"]
        severity: SeverityLevel = fusion_result["severity"]
        anomaly_type: AnomalyType = fusion_result["anomaly_type"]

        # Only update running baseline if current frame is not anomalous
        if not is_anomalous:
            baseline.update(telemetry)

        # 6. Temporal Persistence & Lifecycle Transition
        lifecycle_status, active_anomaly_id = self.lifecycle_manager.update_lifecycle(
            machine_id=m_id,
            is_anomalous=is_anomalous,
            severity=severity,
            db=db
        )

        # 7. Persistence
        persisted_id = None
        primary_metric = stat_evidence.get("primary_metric", "overall")
        observed_val = float(features["raw"].get(primary_metric, 0.0))
        expected_val = float(baseline.get_mean(primary_metric))
        threshold_val = float(expected_val + self.config.z_score_warning_threshold * baseline.get_std(primary_metric))

        # Persist when anomaly is confirmed or active (or detected with High/Critical severity)
        should_persist = (
            persist_if_detected and
            is_anomalous and
            lifecycle_status in [AnomalyLifecycleStatus.CONFIRMED, AnomalyLifecycleStatus.ACTIVE, AnomalyLifecycleStatus.DETECTED]
        )

        if should_persist:
            try:
                record = AnomalyModel(
                    machine_id=m_id,
                    timestamp=telemetry.timestamp,
                    anomaly_detected=True,
                    anomaly_type=anomaly_type.value,
                    anomaly_score=fusion_result["unified_score"],
                    severity=severity.value,
                    status=lifecycle_status.value,
                    primary_metric=primary_metric,
                    observed_value=round(observed_val, 2),
                    expected_value=round(expected_val, 2),
                    threshold=round(threshold_val, 2),
                    triggered_signals=fusion_result["all_triggered_signals"],
                    detector_evidence=fusion_result["evidence"],
                    explanation=fusion_result["explanation"],
                    provenance=telemetry.provenance.value if hasattr(telemetry.provenance, "value") else str(telemetry.provenance),
                    resolved=False
                )
                db.add(record)
                db.commit()
                db.refresh(record)
                persisted_id = record.id
                self.lifecycle_manager.set_active_anomaly_id(m_id, record.id)
                logger.info(f"Anomaly persisted: #{record.id} machine={m_id} severity={severity.value} score={record.anomaly_score}")
            except Exception as exc:
                db.rollback()
                logger.error(f"Failed to persist anomaly record for {m_id}: {exc}")

        total_ms = (time.perf_counter() - t_start) * 1000.0

        # Inject timing metadata into evidence
        fusion_result["evidence"]["latencies_ms"] = {
            "feature_extraction": round(feat_time_ms, 3),
            "statistical": round(stat_time_ms, 3),
            "rolling_trend": round(trend_time_ms, 3),
            "isolation_forest": round(iforest_time_ms, 3),
            "fusion": round(fuse_time_ms, 3),
            "total_inference": round(total_ms, 3),
        }

        return AnomalyAnalysisResponse(
            machine_id=m_id,
            timestamp=telemetry.timestamp,
            anomaly_detected=is_anomalous,
            anomaly_score=fusion_result["unified_score"],
            severity=severity,
            anomaly_type=anomaly_type if is_anomalous else None,
            status=lifecycle_status,
            primary_metric=primary_metric,
            observed_value=round(observed_val, 2),
            expected_value=round(expected_val, 2),
            threshold=round(threshold_val, 2),
            triggered_signals=fusion_result["all_triggered_signals"],
            detector_evidence=fusion_result["evidence"],
            explanation=fusion_result["explanation"],
            persisted_anomaly_id=persisted_id
        )

    def get_machine_anomaly_status(self, machine_id: str, db: Session) -> MachineAnomalyStatus:
        """Retrieves active anomaly status and recent anomaly record for a machine."""
        tracker = self.lifecycle_manager.get_tracker(machine_id)
        baseline = self.baseline_manager.get_baseline(machine_id)
        baseline_status = "ESTABLISHED" if baseline.is_established(self.config.min_baseline_samples_required) else "INSUFFICIENT_BASELINE"

        # Check latest anomaly record
        latest_record = (
            db.query(AnomalyModel)
            .filter_by(machine_id=machine_id)
            .order_by(AnomalyModel.timestamp.desc())
            .first()
        )

        has_active = tracker.current_status in [AnomalyLifecycleStatus.ACTIVE, AnomalyLifecycleStatus.CONFIRMED, AnomalyLifecycleStatus.DETECTED]
        latest_sev = SeverityLevel(latest_record.severity) if latest_record and not latest_record.resolved else SeverityLevel.NORMAL

        active_count = db.query(AnomalyModel).filter_by(machine_id=machine_id, resolved=False).count()

        return MachineAnomalyStatus(
            machine_id=machine_id,
            has_active_anomaly=has_active,
            active_anomaly_count=active_count,
            latest_severity=latest_sev,
            baseline_status=baseline_status,
            latest_anomaly=Anomaly.model_validate(latest_record) if latest_record else None
        )


_engine_instance: Optional[AnomalyEngine] = None


def get_anomaly_engine() -> AnomalyEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = AnomalyEngine()
    return _engine_instance
