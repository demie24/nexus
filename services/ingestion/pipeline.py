"""
NEXUS Telemetry Ingestion Pipeline
Validates, normalizes, deduplicates, persists telemetry data, updates the Digital Twin,
and dispatches structured lifecycle events.
"""

from datetime import datetime, timezone
import logging
import time
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError

from database.models.models import MachineModel, TelemetryModel
from services.schemas import (
    TelemetryCreate,
    IngestionResult,
    BatchIngestionResult,
    IngestionItemStatus,
)
from services.ingestion.validator import (
    validate_telemetry_bounds,
    validate_timestamp,
    validate_machine_exists,
    TelemetryValidationError,
)
from services.ingestion.idempotency import (
    generate_telemetry_idempotency_hash,
    get_idempotency_manager,
)
from services.ingestion.metrics import get_metrics_collector
from services.ingestion.events import (
    get_event_bus,
    IngestionEvent,
    IngestionEventType,
)
from services.digital_twin.engine import get_digital_twin_engine

logger = logging.getLogger("nexus.ingestion.pipeline")


class TelemetryIngestionService:
    def __init__(self):
        self.idempotency_manager = get_idempotency_manager()
        self.metrics_collector = get_metrics_collector()
        self.event_bus = get_event_bus()
        self.digital_twin_engine = get_digital_twin_engine()

    def ingest(
        self,
        payload: TelemetryCreate,
        db: Session,
        client_ip: Optional[str] = None
    ) -> IngestionResult:
        """
        Processes a single telemetry record through the ingestion pipeline.
        1. Records receipt metric
        2. Validates physical bounds, timestamp, and machine registry
        3. Computes cryptographic hash and checks idempotency
        4. Persists telemetry record to PostgreSQL
        5. Updates machine Digital Twin state and in-memory cache
        6. Emits structured ingestion lifecycle events
        """
        self.metrics_collector.record_received(1)
        start_time = time.perf_counter()

        # Step 1: Validation
        try:
            validate_telemetry_bounds(payload)
            validate_timestamp(payload.timestamp)
            machine = validate_machine_exists(payload.machine_id, db)
        except (TelemetryValidationError, ValueError) as val_err:
            logger.warning(f"Telemetry validation rejected: {val_err}")
            self.metrics_collector.record_rejected(1)
            self.event_bus.publish(
                IngestionEvent(
                    IngestionEventType.INGESTION_REJECTED,
                    {"machine_id": payload.machine_id, "reason": str(val_err)}
                )
            )
            return IngestionResult(
                status=IngestionItemStatus.REJECTED,
                message=str(val_err),
                machine_id=payload.machine_id,
                is_duplicate=False,
                digital_twin_updated=False
            )

        # Step 2: Idempotency & Deduplication Check
        hash_str = generate_telemetry_idempotency_hash(payload)
        if self.idempotency_manager.is_duplicate(hash_str, db=db):
            logger.info(f"Duplicate telemetry detected for machine {payload.machine_id} (hash: {hash_str[:12]}...)")
            self.metrics_collector.record_duplicate(1)
            return IngestionResult(
                status=IngestionItemStatus.DUPLICATE,
                message="Duplicate telemetry detected: identical frame already recorded",
                machine_id=payload.machine_id,
                is_duplicate=True,
                idempotency_hash=hash_str,
                digital_twin_updated=False
            )

        # Step 3: Persistence to Database
        db_start = time.perf_counter()
        try:
            telemetry_record = TelemetryModel(
                machine_id=payload.machine_id,
                timestamp=payload.timestamp,
                temperature=payload.temperature,
                vibration=payload.vibration,
                pressure=payload.pressure,
                current=payload.current,
                voltage=payload.voltage,
                rpm=payload.rpm,
                power_kw=payload.power_kw,
                load=payload.load,
                output_rate=payload.output_rate,
                efficiency=payload.efficiency,
                quality_indicator=payload.quality_indicator,
                provenance=payload.provenance.value,
                idempotency_hash=hash_str
            )
            db.add(telemetry_record)
            db.commit()
            db.refresh(telemetry_record)
            self.idempotency_manager.record(hash_str)
        except SQLAlchemyError as db_err:
            db.rollback()
            logger.error(f"Database error writing telemetry for machine {payload.machine_id}: {db_err}")
            self.metrics_collector.record_database_error()
            self.metrics_collector.record_rejected(1)
            return IngestionResult(
                status=IngestionItemStatus.REJECTED,
                message=f"Database write failure: {db_err}",
                machine_id=payload.machine_id,
                is_duplicate=False,
                digital_twin_updated=False
            )
        db_latency_ms = (time.perf_counter() - db_start) * 1000.0

        # Step 4: Digital Twin State Update
        dt_start = time.perf_counter()
        try:
            dt_state = self.digital_twin_engine.update_from_telemetry(
                telemetry=telemetry_record,
                machine=machine,
                db=db
            )
            dt_latency_ms = (time.perf_counter() - dt_start) * 1000.0
            dt_updated = True
        except Exception as dt_err:
            logger.error(f"Error updating digital twin for machine {payload.machine_id}: {dt_err}")
            dt_latency_ms = (time.perf_counter() - dt_start) * 1000.0
            dt_updated = False
            dt_state = None

        # Step 5: Metrics & Structured Events
        self.metrics_collector.record_accepted(1)
        self.metrics_collector.record_latencies(db_latency_ms, dt_latency_ms)

        self.event_bus.publish(
            IngestionEvent(
                IngestionEventType.TELEMETRY_INGESTED,
                {
                    "telemetry_id": telemetry_record.id,
                    "machine_id": payload.machine_id,
                    "timestamp": telemetry_record.timestamp.isoformat(),
                    "provenance": telemetry_record.provenance,
                }
            )
        )

        if dt_updated and dt_state:
            self.event_bus.publish(
                IngestionEvent(
                    IngestionEventType.DIGITAL_TWIN_UPDATED,
                    {
                        "machine_id": payload.machine_id,
                        "status": dt_state.status.value,
                        "health_score": dt_state.health_score,
                        "freshness": dt_state.freshness.value,
                    }
                )
            )

        return IngestionResult(
            status=IngestionItemStatus.ACCEPTED,
            message="Telemetry ingested and digital twin updated successfully",
            telemetry_id=telemetry_record.id,
            machine_id=payload.machine_id,
            is_duplicate=False,
            idempotency_hash=hash_str,
            digital_twin_updated=dt_updated
        )

    def ingest_dict(self, raw_data: Dict[str, Any], db: Session) -> IngestionResult:
        """
        Parses raw dict (e.g. from MQTT JSON or webhook) and runs it through the ingestion pipeline.
        Gracefully handles JSON schema mismatches.
        """
        machine_id = str(raw_data.get("machine_id", "UNKNOWN"))
        try:
            payload = TelemetryCreate(**raw_data)
        except ValidationError as val_err:
            self.metrics_collector.record_received(1)
            self.metrics_collector.record_rejected(1)
            logger.warning(f"Payload validation failed for machine {machine_id}: {val_err}")
            return IngestionResult(
                status=IngestionItemStatus.REJECTED,
                message=f"Schema validation error: {val_err}",
                machine_id=machine_id,
                is_duplicate=False,
                digital_twin_updated=False
            )
        return self.ingest(payload, db)

    def ingest_batch(
        self,
        payloads: List[TelemetryCreate],
        db: Session
    ) -> BatchIngestionResult:
        """
        Processes a batch of telemetry payloads supporting partial acceptance.
        Valid records are ingested and committed, while duplicates and invalid records
        are logged and returned in the batch summary without failing valid records.
        """
        results: List[IngestionResult] = []
        accepted = 0
        duplicate = 0
        rejected = 0

        for payload in payloads:
            res = self.ingest(payload, db)
            results.append(res)
            if res.status == IngestionItemStatus.ACCEPTED:
                accepted += 1
            elif res.status == IngestionItemStatus.DUPLICATE:
                duplicate += 1
            else:
                rejected += 1

        return BatchIngestionResult(
            total_received=len(payloads),
            accepted_count=accepted,
            duplicate_count=duplicate,
            rejected_count=rejected,
            results=results
        )


_service_instance: Optional[TelemetryIngestionService] = None


def get_ingestion_service() -> TelemetryIngestionService:
    global _service_instance
    if _service_instance is None:
        _service_instance = TelemetryIngestionService()
    return _service_instance
