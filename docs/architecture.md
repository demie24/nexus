# NEXUS Platform Architecture

## 1. High-Level System Architecture

NEXUS is designed as an industrial-grade **Decision Intelligence & Digital Twin Platform** using a modular, service-oriented architecture.

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   VIRTUAL INDUSTRIAL ENVIRONMENT                       │
│  - 6 Multi-Disciplinary Machines (M01-M06 across 2 Production Lines)   │
│  - Physics Coupled Thermodynamic & Mechanical Equations                │
│  - 5 Operational & Degradation Scenarios                               │
│  - Transports: In-Memory Ring Buffer, PostgreSQL, Mosquitto MQTT       │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ Telemetry Stream (QoS 1, REST, MQTT)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                 TELEMETRY INGESTION PIPELINE (Phase 3)                 │
│  - Physical Plausibility Validation (bounds & thermodynamic limits)    │
│  - SHA-256 Cryptographic Fingerprint Deduplication (Idempotency)       │
│  - Partial Batch Acceptance Engine                                     │
│  - Asynchronous MQTT Consumer Worker                                   │
│  - PostgreSQL Timeseries Persistence (`telemetries` table)             │
│  - Decoupled Ingestion Event Bus (`TELEMETRY_INGESTED`)                │
└──────────────────┬───────────────────────────────┬─────────────────────┘
                   │ Synchronous State Update      │ Asynchronous Event
                   ▼                               ▼
┌─────────────────────────────────────┐ ┌────────────────────────────────┐ ┌────────────────────────────────┐ ┌────────────────────────────────┐
│      DIGITAL TWIN ENGINE            │ │   ANOMALY DETECTION ENGINE     │ │ PREDICTIVE INTELLIGENCE ENGINE │ │ ROOT CAUSE ANALYSIS & DIAGS    │
│  - Deterministic State Transitions  │ │  - Feature Extraction (Rolling)│ │  - Multi-Horizon Risk Forecast │ │  - Causal Dependency Graph     │
│  - Dynamic Freshness Tracking       │ │  - Detector A: Statistical Z   │ │    (60m, 120m, 240m, 360m)     │ │  - Physical Consistency Engine │
│    (FRESH <= 60s, STALE, UNKNOWN)   │ │  - Detector B: Rolling Trend   │ │  - Calibrated Probabilities    │ │  - Lead-Lag Cross-Correlation  │
│  - Health Score Calculation         │ │  - Detector C: Isolation Forest│ │  - Quantile RUL Bounds [lo, hi]│ │  - Multi-Source Evidence Fuse  │
│  - Enterprise Factory Snapshot      │ │  - Sensor vs Machine Classifier│ │  - Health Trajectory Forecast  │ │  - Top-K Ranked Explanations   │
│  - Fast In-Memory Cache             │ │  - Multi-Detector Evidence Fuse│ │  - Factor Attribution Explains │ │  - Engineering Text Reports    │
│                                     │ │  - Temporal Persistence State  │ │  - Cold Start Guard (< 15 smp) │ │  - Cold Start / Fallback Guard │
└──────────────────┬──────────────────┘ └────────────────┬───────────────┘ └────────────────┬───────────────┘ └────────────────┬───────────────┘
                   │                                     │                                  │                                  │
                   └──────────────────┬──────────────────┴──────────────────────────────────┴──────────────────────────────────┘
                                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    NEXUS API GATEWAY (FastAPI)                         │
│  - `/health`, `/ready`, `/metrics`                                     │
│  - `/api/v1/machines` (Registry, States, Time-Series Telemetry)        │
│  - `/api/v1/telemetry` (Single & Batch Ingestion)                      │
│  - `/api/v1/factory/state` (Factory Digital Twin Snapshot)             │
│  - `/api/v1/anomalies` (List, Detail, On-Demand Analysis, Status)      │
│  - `/api/v1/predictions` (List, Detail, On-Demand Analysis, Horizons)  │
│  - `/api/v1/diagnostics` (List, Detail, On-Demand RCA Analysis)        │
│  - `/api/v1/simulation` (What-If Scenarios, Compare, Forked Sandboxes) │
│  - `/api/v1/simulator` (Control, Scenario Injection, Ticks)            │
│  - `/api/v1/audit` (Governance & Immutable Audit Logs)                 │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Layered Responsibilities

| Layer | Responsibility | SLA / Latency |
| :--- | :--- | :--- |
| **Simulation Layer** | Generates physically realistic synthetic telemetry with configurable sensor noise and failure scenario modifiers. | Configurable ($1\text{ Hz}$ to $1000\text{ Hz}$) |
| **Ingestion Layer** | Validates physical bounds, eliminates network duplicates, writes to database, updates Digital Twin. | P95 $< 15\text{ ms}$ |
| **Digital Twin Layer** | Evaluates deterministic machine health, failure probability, and data freshness. | P95 $< 25\text{ ms}$ |
| **Anomaly Intelligence** | Unsupervised multi-layer anomaly detection (Statistical, Trend, Isolation Forest) and physical classification. | P95 $< 30\text{ ms}$ (Target: $< 200\text{ ms}$) |
| **Predictive Intelligence** | Multi-horizon risk forecasting (1h, 2h, 4h, 6h), quantile RUL uncertainty interval, degradation trajectory. | P95 $= 26.2\text{ ms}$ (Target: $< 200\text{ ms}$) |
| **Root Cause Analysis (RCA)** | Causal graph traversal, physical consistency validation, lead-lag cross-correlation, and evidence fusion ranking. | P95 $= 5.59\text{ ms}$ (Target: $< 300\text{ ms}$) |
| **What-If Simulation Engine** | Forks sandboxed machine states from immutable snapshots, integrates forward physics, evaluates multi-machine cascade. | P95 $= 8.25\text{ ms}$ (Target: $< 500\text{ ms}$) |
| **API Gateway Layer** | Exposes versioned REST endpoints with CORS, structured validation, and security headers. | Sub-millisecond routing overhead |

---

## 3. Data Flow & Provenance

Every record in the NEXUS system carries an immutable `DataProvenance` tag:
* `OBSERVED`: Verified real or primary operational telemetry stream.
* `PREDICTED`: Statistical or machine learning model forecast (Phase 5).

* `DIAGNOSED`: Root cause analysis and fault attribution record (Phase 6).
* `SIMULATED`: Counterfactual simulation or What-If scenario (Phase 7).
* `RECOMMENDED`: Prescriptive action derived from the Decision Engine (Phase 8).

