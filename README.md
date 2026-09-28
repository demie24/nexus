# NEXUS

## AI-Orchestrated Decision Intelligence & Digital Twin Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.13+](https://img.shields.io/badge/Python-3.13+-brightgreen.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React%20%7C%20TypeScript-61DAFB.svg)](https://react.dev/)
[![Docker](https://img.shields.io/badge/Infra-Docker%20Compose-2496ED.svg)](https://www.docker.com/)

---

## 1. Executive Summary

**NEXUS** ialah sebuah platform **Decision Intelligence** dan **Digital Twin** perindustrian end-to-end yang menjembatani jurang antara pemantauan data mentah dengan tindakan operasi berkeputusan tinggi.

NEXUS **bukan sekadar dashboard pemantauan**, **bukan chatbot ringkas**, dan **bukan aplikasi CRUD**. NEXUS ialah sistem sokongan keputusan (*decision-support system*) industri yang memproses telemetri, menganggarkan keadaan semasa, mengesan anomali, meramalkan risiko kegagalan, menyiasat punca masalah (*Root Cause Analysis*), mensimulasikan senario "What-If", menyusun cadangan tindakan optimum, dan meletakkan pengendali manusia dalam kitaran kelulusan (*Human-in-the-Loop*).

```text
DATA
  ↓
DATA VALIDATION
  ↓
STATE ESTIMATION (Digital Twin)
  ↓
ANOMALY DETECTION (Statistical + Isolation Forest)
  ↓
PREDICTION (Failure Probability & RUL)
  ↓
ROOT CAUSE ANALYSIS (Dependency & Causal Correlation Graph)
  ↓
SIMULATION ("What-If" Counterfactual Scenarios)
  ↓
DECISION ENGINE (Multi-Criteria Action Ranking)
  ↓
RECOMMENDATION
  ↓
HUMAN APPROVAL (Immutable Audit Trail)
```

---

## 2. Virtual Industrial Domain

Untuk memastikan sistem boleh diuji secara konsisten tanpa pergantungan kepada perkakasan fizikal, NEXUS mengintegrasikan **Synthetic Industrial Environment**:

```text
Virtual Factory
│
├── Production Line 01
│   ├── Machine M01 (CNC Milling)
│   ├── Machine M02 (Industrial Lathe)
│   └── Machine M03 (Precision Grinder)
│
├── Production Line 02
│   ├── Machine M04 (Robotic Welder)
│   ├── Machine M05 (Hydraulic Press)
│   └── Machine M06 (Automated Packaging)
│
└── Central Energy & Auxiliary System
```

Setiap mesin mensimulasikan parameter fizik dinamik:
* **Suhu Operasi (°C)**
* **Amplitud Getaran (mm/s)**
* **Arus & Voltan Elektrik (A / V)**
* **Kelajuan Putaran (RPM)**
* **Penggunaan Tenaga (kW)**
* **Kadar Output & Kecekapan (%)**
* **Skor Kesihatan & Kebarangkalian Kegagalan (%)**

Simulator menyokong 7 profil operasi:
1. Normal Nominal Operation
2. Progressive Degradation (Bearing / Thermal / Electrical wear)
3. Sudden Sensor Anomaly & Noise
4. Performance & Throughput Drop
5. Impending Critical Failure
6. Operator Interventions & Load Modulation
7. Post-Maintenance Recovery

---

## 3. Prinsip Kejuruteraan & Ketelusan Data

NEXUS mematuhi standard kejuruteraan ketat:
1. **Kebebasan daripada LLM Komersial Wajib**: Teras analitik, ramalan, dan keputusan berfungsi 100% menggunakan statistik, regresi, graf kausal, dan algoritma pengoptimuman tempatan (CPU-friendly). LLM luaran hanyalah lapisan pilihan (*optional adapter*) untuk sintesis bahasa semula jadi.
2. **Pemisahan Kategori Data**:
   * `OBSERVED`: Data telemetri sebenar/sintetik yang disahkan.
   * `PREDICTED`: Unjuran model statistik dan Machine Learning.
   * `SIMULATED`: Hasil percabangan senario hipotetikal "What-If".
   * `RECOMMENDED`: Pilihan tindakan yang dinilai kos, risiko, dan impak operasinya.
3. **Human-in-the-Loop**: Tiada tindakan berisiko tinggi dilaksanakan secara autonomi tanpa kelulusan operator bertauliah. Semua tindakan direkodkan dalam jejak audit kekal (*audit log*).

---

## 4. Seni Bina Sistem (Architecture)

```text
                    ┌───────────────────────────────────┐
                    │    React Command Center (UI)      │
                    │   (Vite + TypeScript + Tailwind)  │
                    └─────────────────┬─────────────────┘
                                      │ REST / WebSocket
                    ┌─────────────────▼─────────────────┐
                    │       FastAPI API Gateway         │
                    │   (Auth, RBAC, Rate Limiting)     │
                    └─────────────────┬─────────────────┘
                                      │
       ┌──────────────────────────────┼──────────────────────────────┐
       │                              │                              │
       ▼                              ▼                              ▼
 Data Ingestion Layer      Intelligence Engine            Simulation Engine
 (Validation & Quality)    - Anomaly Detection (IF/Z)     - Scenario Branching
       │                   - Degradation Forecasting      - Multi-Machine Cascade
       │                   - Root Cause Analysis (RCA)    - Counterfactual Replay
       │                              │                              │
       └──────────────────────────────┼──────────────────────────────┘
                                      │
                                ┌─────▼──────┐
                                │  Decision  │
                                │   Engine   │
                                └─────┬──────┘
                                      │
                               ┌──────▼───────┐
                               │ AI Multi-    │
                               │ Agent Layer  │
                               └──────┬───────┘
                                      │ Structured Recommendation
                               ┌──────▼───────┐
                               │ Human Review │
                               │ & Audit Log  │
                               └──────────────┘
```

---

## 5. Struktur Direktori Repositori

```text
nexus/
├── apps/
│   ├── api/                 # FastAPI core service & API v1 routers
│   ├── worker/              # Background event processors & task queues
│   ├── simulator/           # Virtual Factory synthetic telemetry streamer
│   └── frontend/            # React + TypeScript + Tailwind CSS Command Center
├── services/
│   ├── ingestion/           # Data sanitization, boundary checks, and quality flags
│   ├── digital_twin/        # Machine state machine & health estimation
│   ├── anomaly/             # Statistical z-score & Isolation Forest anomaly engine
│   ├── prediction/          # Failure trajectory & Remaining Useful Life (RUL)
│   ├── diagnostics/         # Causal graph, correlation & Root Cause Analysis
│   ├── simulation/          # What-if scenario evaluator & counterfactuals
│   ├── decision/            # Multi-criteria action ranking & cost-benefit scoring
│   └── orchestration/       # Deterministic Multi-Agent coordinator
├── database/
│   ├── models/              # SQLAlchemy ORM models (Machines, Telemetry, Audits)
│   ├── migrations/          # Alembic database migration scripts
│   └── session.py           # Database connection & session management
├── infrastructure/
│   ├── docker/              # Dockerfiles for each modular service
│   ├── mosquitto/           # MQTT broker configuration
│   └── docker-compose.yml   # Multi-container orchestration
├── tests/
│   ├── unit/                # Unit tests for core services
│   ├── integration/         # Cross-service pipeline tests
│   ├── api/                 # REST API endpoints test suite
│   ├── simulation/          # Scenario determinism & cascade tests
│   ├── ml/                  # ML baseline & evaluation metric tests
│   └── security/            # Auth, RBAC, and input sanitization tests
├── docs/                    # Detailed architectural and engineering specifications
├── scripts/                 # Utility scripts, data seeding, and test runners
├── .env.example             # Environment configuration template
├── README.md                # Project documentation
└── LICENSE                  # MIT License
```

---

## 6. Port Isolation & Perkhidmatan Tempatan

Bagi mengelakkan sebarang konflik dengan perkhidmatan lain yang sedang aktif pada sistem hos, NEXUS memperuntukkan port khusus:

* **NEXUS API Gateway:** `8080`
* **NEXUS Frontend UI:** `5180`
* **NEXUS PostgreSQL:** `5434`
* **NEXUS Redis:** `6379`
* **NEXUS Mosquitto MQTT:** `1884`

---

## 7. Fasa Pembangunan (Roadmap)

- [x] **Discovery & GitHub Setup**: Pemeriksaan persekitaran, seni bina, dan inisialisasi git repository.
- [x] **Fasa 1: Foundation & Core Infrastructure**: Pydantic schemas, SQLAlchemy models, Alembic migrations, security foundation, FastAPI gateway, dan pytest test suites (30 tests, 97% coverage).
- [ ] **Fasa 2: Virtual Factory Simulator**: Penjana telemetri sintetik realistik untuk mesin M01-M06 dengan suntikan kecacatan terkawal.
- [ ] **Fasa 3: Telemetry Ingestion & Digital Twin**: Validasi kualiti data, penjejakan status dinamik, dan pengiraan skor kesihatan (*Health Score*).
- [ ] **Fasa 4: Anomaly Detection Engine**: Model Statistical Z-Score, Rolling Window, dan Isolation Forest.
- [ ] **Fasa 5: Predictive Intelligence**: Ramalan kebarangkalian kegagalan (*Failure Probability*) dan baki jangka hayat mesin (*RUL*).
- [ ] **Fasa 6: Root Cause Analysis (RCA)**: Graf pergantungan (*dependency graph*) dan analisis korelasi kausal bagi menyiasat punca kerosakan.
- [ ] **Fasa 7: What-If Simulation Engine**: Penilaian senario hipotetikal (contoh: pengurangan beban 20% vs penutupan segera).
- [ ] **Fasa 8: Decision Engine**: Pemarkahan pelbagai kriteria (Kos vs Risiko vs Kerugian Pengeluaran) dan cadangan tindakan optimum.
- [ ] **Fasa 9: AI Multi-Agent Orchestration**: Penyelarasan Ejen Analisis, Diagnostik, Simulasi, dan Keputusan dalam format berstruktur.
- [ ] **Fasa 10: Operational Command Center (Frontend)**: Dashboard web moden dengan sokongan visualisasi telemetri, panel simulasi, dan kelulusan tindakan.
- [ ] **Fasa 11: Security & Auditability**: JWT authentication, RBAC, dan rekod jejak audit kekal (*immutable audit log*).
- [ ] **Fasa 12: Testing & CI/CD**: Ujian unit komprehensif, ujian integrasi senario, dan workflow GitHub Actions.
- [ ] **Fasa 13: Observability**: Endpoint kesihatan sistem (`/health`, `/ready`, `/metrics`) dan metrik telemetri.
- [ ] **Fasa 14: Portfolio Polish**: Dokumentasi akhir, rajah seni bina terperinci, dan panduan demonstrasi.

---

## 8. Panduan Pemasangan & Pembangunan Tempatan (Local Setup)

### 8.1 Keperluan Sistem
* Linux / macOS / WSL2 (Windows)
* Python 3.11+ (Disahkan pada Python 3.13)
* Docker & Docker Compose v2+
* Git

### 8.2 Langkah Permulaan

```bash
# 1. Klon repositori
git clone https://github.com/demie24/nexus.git
cd nexus

# 2. Bina dan aktifkan Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Pasang kebergantungan (dependencies)
pip install -r requirements.txt

# 4. Sediakan konfigurasi environment
cp .env.example .env

# 5. Mulakan perkhidmatan infrastruktur (PostgreSQL, Redis, Mosquitto MQTT)
docker compose up -d

# 6. Jalankan migrasi pangkalan data melalui Alembic
alembic upgrade head

# 7. Jalankan ujian automatik & liputan kod
pytest -v --cov=apps --cov=services --cov=database tests/

# 8. Mulakan pelayan API FastAPI secara tempatan
uvicorn apps.api.main:app --host 0.0.0.0 --port 8080 --reload
```

### 8.3 Endpoint Pantas
* **Dokumentasi Interaktif (Swagger UI):** `http://localhost:8080/docs`
* **Dokumentasi ReDoc:** `http://localhost:8080/redoc`
* **Pemeriksaan Kesihatan (Liveness):** `http://localhost:8080/health`
* **Pemeriksaan Ketersediaan (Readiness):** `http://localhost:8080/ready`
* **Metrik Operasi:** `http://localhost:8080/metrics`

---

## 9. Lesen

Dilesenkan di bawah [MIT License](LICENSE).

