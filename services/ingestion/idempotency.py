"""
Telemetry Idempotency & Deduplication Engine
Calculates deterministic cryptographic SHA-256 fingerprints across machine ID, timestamp,
and core operational metrics to prevent duplicate telemetry records.
"""

from collections import OrderedDict
import hashlib
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from database.models.models import TelemetryModel
from services.schemas import TelemetryCreate


def generate_telemetry_idempotency_hash(payload: TelemetryCreate) -> str:
    """
    Computes a deterministic SHA-256 cryptographic fingerprint from payload metrics.
    Ensures identical telemetry packets received via multiple transports yield the same hash.
    """
    ts_str = payload.timestamp.isoformat()
    raw_key = (
        f"{payload.machine_id}|{ts_str}|"
        f"{payload.temperature:.2f}|{payload.vibration:.3f}|{payload.current:.2f}|"
        f"{payload.voltage:.1f}|{payload.rpm:.1f}|{payload.power_kw:.2f}|{payload.load:.2f}"
    )
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class IdempotencyManager:
    def __init__(self, max_cache_size: int = 10000):
        # In-memory LRU cache for high-throughput zero-latency duplicate checks
        self.cache: OrderedDict[str, bool] = OrderedDict()
        self.max_cache_size = max_cache_size

    def is_duplicate(self, hash_str: str, db: Optional[Session] = None) -> bool:
        """
        Determines whether the given idempotency hash has already been processed.
        Checks in-memory LRU cache first, falling back to database query if db session is provided.
        """
        # 1. Fast in-memory cache check
        if hash_str in self.cache:
            self.cache.move_to_end(hash_str)
            return True

        # 2. Database existence check
        if db is not None:
            existing = (
                db.query(TelemetryModel.id)
                .filter(TelemetryModel.idempotency_hash == hash_str)
                .first()
            )
            if existing is not None:
                self.record(hash_str)
                return True

        return False

    def record(self, hash_str: str) -> None:
        """Records the hash in the in-memory deduplication cache."""
        self.cache[hash_str] = True
        if len(self.cache) > self.max_cache_size:
            self.cache.popitem(last=False)

    def clear(self) -> None:
        """Clears the in-memory cache."""
        self.cache.clear()


# Default singleton instance
_idempotency_manager: Optional[IdempotencyManager] = None


def get_idempotency_manager() -> IdempotencyManager:
    global _idempotency_manager
    if _idempotency_manager is None:
        _idempotency_manager = IdempotencyManager()
    return _idempotency_manager
