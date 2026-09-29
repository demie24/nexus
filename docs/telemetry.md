# NEXUS Telemetry Ingestion Architecture

## 1. Overview
The **NEXUS Telemetry Ingestion Pipeline** acts as the high-throughput, fault-tolerant gateway that consumes continuous operational telemetry frames across industrial assets. It bridges physical/simulated industrial transports into validated persistence and feeds real-time state estimations to the NEXUS Digital Twin.

```text
[Simulator / Hardware]
          │
    (MQTT / REST)
          ▼
┌────────────────────────────────────────────────────────┐
│             NEXUS Ingestion Service                    │
│                                                        │
│  1. Receipt Metrics & Timing                           │
│  2. Physical Plausibility Validation                   │
│  3. Timestamp Window & Machine Registry Check          │
│  4. SHA-256 Cryptographic Deduplication (Idempotency)  │
│  5. PostgreSQL Persistence (with retry & rollback)    │
│  6. Digital Twin State Estimation Trigger              │
│  7. Event Bus Notification (Decoupled Subscribers)     │
└────────────────────────────────────────────────────────┘
          │
          ├──► PostgreSQL `telemetries` (Timeseries Partition-Ready)
          └──► Digital Twin Engine (`machine_states` & In-Memory Cache)
```

---

## 2. Ingestion Transports

### A. MQTT Broker (Eclipse Mosquitto)
Industrial machines publish packets to an enterprise-grade hierarchical topic structure:
```text
nexus/factory/{factory_id}/line/{line_id}/machine/{machine_id}/telemetry
```
* **Broker Port**: Host `1884` (mapped to container `1883`).
* **Quality of Service (QoS)**: QoS 1 (at-least-once delivery).
* **Consumer Worker**: [`apps.worker.mqtt_consumer.MQTTConsumerWorker`](file:///home/demie/nexus/apps/worker/mqtt_consumer.py) runs asynchronously, subscribing to `nexus/factory/+/line/+/machine/+/telemetry`.
* **Resilience**: Malformed JSON or non-UTF-8 payloads are rejected gracefully with metric counters incremented; the worker never crashes.

### B. REST API Ingestion
* **Single Frame**: `POST /api/v1/telemetry`
  * Status `201 Created` on valid ingestion.
  * Status `422 Unprocessable Content` on physical implausibility.
  * Status `404 Not Found` for unregistered machines.
* **Batch Ingestion (Partial Acceptance)**: `POST /api/v1/telemetry/batch`
  * Ingests lists of frames concurrently.
  * Valid items are persisted and committed.
  * Invalid items or duplicates return itemized statuses without failing valid items.

---

## 3. Validation & Physical Plausibility Engine

NEXUS makes a strict architectural distinction between **physically impossible readings** (which indicate sensor malfunction or corrupt payloads and are rejected) and **operational anomalies** (which are physically valid but indicative of asset degradation, and are accepted):

| Parameter | Valid Physical Range | Rejection Criterion | Operational Anomaly Example |
| :--- | :--- | :--- | :--- |
| **Temperature** | -50.0°C to 400.0°C | `< -50°C` or `> 400°C` | `115.0°C` (Accepted: Thermal runaway) |
| **Vibration** | 0.0 to 150.0 mm/s | `< 0.0` or `> 150.0 mm/s` | `12.5 mm/s` (Accepted: Bearing fault) |
| **Pressure** | 0.0 to 1000.0 bar | `< 0.0` bar | `450.0 bar` (Accepted: Pressure surge) |
| **Current** | 0.0 to 500.0 A | `< 0.0` A | `85.0 A` (Accepted: Motor overload) |
| **Voltage** | 0.0 to 1000.0 V | `< 0.0` V | `320.0 V` (Accepted: Voltage sag) |
| **RPM** | 0.0 to 25000.0 | `< 0.0` RPM | `0.0 RPM` under load (Stall) |
| **Active Power** | 0.0 to 1000.0 kW | `< 0.0` kW | Overload spikes |
| **Load Factor** | 0.0 to 5.0 | `< 0.0` or `> 5.0` | `1.4` (40% overload) |
| **Efficiency** | 0.0% to 100.0% | `< 0.0%` or `> 100.0%` | `45.0%` (Severe mechanical friction) |
| **Timestamp** | Now ± 1 hour to 30 days past | Future `> 1h` or Old `> 30d` | Stale or clock drift |

---

## 4. Cryptographic Idempotency & Deduplication

In distributed telemetry pipelines, network retries and multi-transport delivery frequently cause duplicate packet arrival. NEXUS guarantees idempotency via deterministic cryptographic hashing:

```python
raw_key = f"{machine_id}|{timestamp_iso}|{temp:.2f}|{vib:.3f}|{curr:.2f}|{volt:.1f}|{rpm:.1f}|{power:.2f}|{load:.2f}"
idempotency_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
```

1. **Two-Tier Lookups**:
   - **Tier 1 (Zero Latency)**: In-memory LRU cache (`OrderedDict`) checking recent 10,000 hashes in `~0.01 ms`.
   - **Tier 2 (Durable Check)**: Indexed database column `telemetry.idempotency_hash`.
2. **Behavior on Duplicate**:
   - Skips persistence without throwing an exception.
   - Increments duplicate metrics.
   - Returns status `DUPLICATE` with `is_duplicate=True`.

---

## 5. Timeseries Queries

Historical telemetry is queried through composite-indexed queries on `(machine_id, timestamp)`:
```http
GET /api/v1/machines/{machine_id}/telemetry?start_time=2026-09-29T00:00:00Z&end_time=2026-09-29T23:59:59Z&limit=100&order=desc
```
Supporting pagination, range filtering, and sub-millisecond retrieval.
