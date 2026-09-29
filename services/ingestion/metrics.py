"""
Ingestion & Digital Twin Observability Metrics
Collects runtime metrics for throughput, latency, rejections, duplicate rates, and subsystem health.
"""

from collections import deque
import threading
import time
from typing import Dict, Any, List


class IngestionMetrics:
    def __init__(self, latency_window_size: int = 1000):
        self._lock = threading.Lock()
        self.telemetry_received_total: int = 0
        self.telemetry_accepted_total: int = 0
        self.telemetry_rejected_total: int = 0
        self.telemetry_duplicate_total: int = 0
        self.database_write_errors_total: int = 0
        self.mqtt_connection_status: bool = False
        self.stale_machine_count: int = 0

        # Latency samples in milliseconds
        self._ingestion_latencies: deque = deque(maxlen=latency_window_size)
        self._digital_twin_latencies: deque = deque(maxlen=latency_window_size)

    def record_received(self, count: int = 1) -> None:
        with self._lock:
            self.telemetry_received_total += count

    def record_accepted(self, count: int = 1) -> None:
        with self._lock:
            self.telemetry_accepted_total += count

    def record_rejected(self, count: int = 1) -> None:
        with self._lock:
            self.telemetry_rejected_total += count

    def record_duplicate(self, count: int = 1) -> None:
        with self._lock:
            self.telemetry_duplicate_total += count

    def record_database_error(self) -> None:
        with self._lock:
            self.database_write_errors_total += 1

    def set_mqtt_status(self, connected: bool) -> None:
        with self._lock:
            self.mqtt_connection_status = connected

    def set_stale_count(self, count: int) -> None:
        with self._lock:
            self.stale_machine_count = count

    def record_latencies(self, ingestion_ms: float, digital_twin_ms: float) -> None:
        with self._lock:
            self._ingestion_latencies.append(ingestion_ms)
            self._digital_twin_latencies.append(digital_twin_ms)

    def _calc_stats(self, samples: deque) -> Dict[str, float]:
        if not samples:
            return {"avg_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0}
        arr = sorted(list(samples))
        n = len(arr)
        p95_idx = min(int(n * 0.95), n - 1)
        return {
            "avg_ms": round(sum(arr) / n, 3),
            "p95_ms": round(arr[p95_idx], 3),
            "max_ms": round(arr[-1], 3)
        }

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "telemetry_received_total": self.telemetry_received_total,
                "telemetry_accepted_total": self.telemetry_accepted_total,
                "telemetry_rejected_total": self.telemetry_rejected_total,
                "telemetry_duplicate_total": self.telemetry_duplicate_total,
                "database_write_errors": self.database_write_errors_total,
                "mqtt_connected": self.mqtt_connection_status,
                "stale_machine_count": self.stale_machine_count,
                "ingestion_latency": self._calc_stats(self._ingestion_latencies),
                "digital_twin_latency": self._calc_stats(self._digital_twin_latencies)
            }


_metrics_instance = IngestionMetrics()


def get_metrics_collector() -> IngestionMetrics:
    return _metrics_instance
