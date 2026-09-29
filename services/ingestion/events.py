"""
Event Bus & Ingestion Pipeline Events
Provides decoupled event dispatching for downstream intelligence engines (Anomaly, Prediction, RCA).
"""

from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Callable, Dict, List, Any

logger = logging.getLogger("nexus.ingestion.events")


class IngestionEventType(str, Enum):
    TELEMETRY_INGESTED = "TELEMETRY_INGESTED"
    DIGITAL_TWIN_UPDATED = "DIGITAL_TWIN_UPDATED"
    INGESTION_REJECTED = "INGESTION_REJECTED"
    STALE_DETECTED = "STALE_DETECTED"


class IngestionEvent:
    def __init__(self, event_type: IngestionEventType, data: Dict[str, Any]):
        self.event_type = event_type
        self.data = data
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        }


class EventBus:
    def __init__(self):
        self._subscribers: Dict[IngestionEventType, List[Callable[[IngestionEvent], None]]] = {
            t: [] for t in IngestionEventType
        }

    def subscribe(self, event_type: IngestionEventType, handler: Callable[[IngestionEvent], None]) -> None:
        self._subscribers[event_type].append(handler)

    def publish(self, event: IngestionEvent) -> None:
        handlers = self._subscribers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                logger.error(f"Error executing event handler for {event.event_type}: {exc}")


_default_event_bus = EventBus()


def get_event_bus() -> EventBus:
    return _default_event_bus
