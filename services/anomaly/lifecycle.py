"""
NEXUS Temporal Persistence & Anomaly Lifecycle Engine
Tracks temporal persistence across sequential telemetry ticks to avoid single-spike false alarms.
Manages lifecycle transitions: DETECTED -> CONFIRMED -> ACTIVE -> RECOVERING -> RESOLVED.
"""

from datetime import datetime, timezone
import logging
from typing import Dict, Optional, Tuple
from sqlalchemy.orm import Session

from database.models.models import AnomalyModel
from services.schemas import AnomalyLifecycleStatus, SeverityLevel
from services.anomaly.config import get_anomaly_config

logger = logging.getLogger("nexus.anomaly.lifecycle")


class MachineLifecycleTracker:
    def __init__(self, machine_id: str):
        self.machine_id = machine_id
        self.consecutive_anomalous: int = 0
        self.consecutive_normal: int = 0
        self.current_status: AnomalyLifecycleStatus = AnomalyLifecycleStatus.RESOLVED
        self.active_anomaly_id: Optional[int] = None
        self.last_updated: datetime = datetime.now(timezone.utc)


class AnomalyLifecycleManager:
    def __init__(self):
        self.config = get_anomaly_config()
        self._trackers: Dict[str, MachineLifecycleTracker] = {}

    def get_tracker(self, machine_id: str) -> MachineLifecycleTracker:
        if machine_id not in self._trackers:
            self._trackers[machine_id] = MachineLifecycleTracker(machine_id)
        return self._trackers[machine_id]

    def update_lifecycle(
        self,
        machine_id: str,
        is_anomalous: bool,
        severity: SeverityLevel,
        db: Optional[Session] = None
    ) -> Tuple[AnomalyLifecycleStatus, Optional[int]]:
        """
        Updates machine lifecycle based on current tick anomaly status.
        Returns: (new_status, active_anomaly_id)
        """
        tracker = self.get_tracker(machine_id)
        now = datetime.now(timezone.utc)
        tracker.last_updated = now

        if is_anomalous:
            tracker.consecutive_anomalous += 1
            tracker.consecutive_normal = 0

            # High or Critical severity bypasses streak requirement immediately
            immediate_confirm = severity in [SeverityLevel.HIGH, SeverityLevel.CRITICAL]

            if tracker.current_status in [AnomalyLifecycleStatus.RESOLVED, AnomalyLifecycleStatus.RECOVERING]:
                if immediate_confirm or tracker.consecutive_anomalous >= self.config.min_consecutive_anomalies_to_confirm:
                    tracker.current_status = AnomalyLifecycleStatus.CONFIRMED
                else:
                    tracker.current_status = AnomalyLifecycleStatus.DETECTED

            elif tracker.current_status == AnomalyLifecycleStatus.DETECTED:
                if immediate_confirm or tracker.consecutive_anomalous >= self.config.min_consecutive_anomalies_to_confirm:
                    tracker.current_status = AnomalyLifecycleStatus.CONFIRMED

            elif tracker.current_status == AnomalyLifecycleStatus.CONFIRMED:
                tracker.current_status = AnomalyLifecycleStatus.ACTIVE

        else:
            # Current frame is normal
            tracker.consecutive_normal += 1
            tracker.consecutive_anomalous = 0

            if tracker.current_status in [AnomalyLifecycleStatus.ACTIVE, AnomalyLifecycleStatus.CONFIRMED]:
                tracker.current_status = AnomalyLifecycleStatus.RECOVERING

            elif tracker.current_status == AnomalyLifecycleStatus.RECOVERING:
                if tracker.consecutive_normal >= self.config.recovery_cooldown_ticks:
                    tracker.current_status = AnomalyLifecycleStatus.RESOLVED
                    # Close active anomaly in DB if present
                    if tracker.active_anomaly_id and db:
                        self._resolve_in_db(tracker.active_anomaly_id, now, db)
                    tracker.active_anomaly_id = None

            elif tracker.current_status == AnomalyLifecycleStatus.DETECTED:
                # Single isolated spike resolved immediately
                tracker.current_status = AnomalyLifecycleStatus.RESOLVED
                tracker.active_anomaly_id = None

        return tracker.current_status, tracker.active_anomaly_id

    def set_active_anomaly_id(self, machine_id: str, anomaly_id: int) -> None:
        tracker = self.get_tracker(machine_id)
        tracker.active_anomaly_id = anomaly_id

    def _resolve_in_db(self, anomaly_id: int, resolved_at: datetime, db: Session) -> None:
        try:
            record = db.query(AnomalyModel).filter_by(id=anomaly_id).first()
            if record and not record.resolved:
                record.resolved = True
                record.status = AnomalyLifecycleStatus.RESOLVED.value
                record.resolved_at = resolved_at
                db.commit()
                logger.info(f"Anomaly record #{anomaly_id} successfully marked as RESOLVED.")
        except Exception as exc:
            db.rollback()
            logger.error(f"Error marking anomaly #{anomaly_id} resolved: {exc}")

    def reset(self, machine_id: Optional[str] = None) -> None:
        if machine_id:
            self._trackers.pop(machine_id, None)
        else:
            self._trackers.clear()


_lifecycle_manager = AnomalyLifecycleManager()


def get_lifecycle_manager() -> AnomalyLifecycleManager:
    return _lifecycle_manager
