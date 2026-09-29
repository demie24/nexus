# NEXUS Multi-Criteria Decision Engine & Action Ranking (Phase 8)

## 1. Overview & System Mission

The **NEXUS Multi-Criteria Decision Engine** is an advanced operational decision-support system designed to convert predictive insights, diagnostic findings, and counterfactual simulation trajectories into objective, auditable engineering action rankings.

Rather than relying on uninterpretable "black-box" models or speculative generative AI, the NEXUS Decision Engine operates on **100% deterministic, mathematically sound Multi-Criteria Decision Analysis (MCDA)**. It bridges the gap between raw physical evidence and executive maintenance operations without executing unapproved autonomous actions.

```
+-----------------------------------------------------------------------------------+
|                           DIGITAL TWIN SNAPSHOT                                   |
|                Point-in-time immutable factory physical state                     |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                    PHASE 7 COUNTERFACTUAL SIMULATION SUITE                        |
|       DO_NOTHING | LOAD_MODULATION (-20%, -40%) | COOLING_BOOST                   |
|       SCHEDULED_SHUTDOWN | IMMEDIATE_EMERGENCY_STOP                               |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|               EVIDENCE AGGREGATION & CONTEXT CORRELATION                          |
|       - Physical Simulation Outcomes (T_peak, Vib_peak, Output Loss %, RUL)       |
|       - Phase 4 Anomaly Signals & Phase 5 Predictive Hazard Horizons              |
|       - Phase 6 Root Cause Hypotheses & Evidence Strengths                        |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                    PHYSICAL & POLICY HARD CONSTRAINTS                             |
|       - Critical Hazard Limit (P_fail <= 0.70)                                    |
|       - Thermal Runaway Limit (T_peak <= 90.0°C)                                  |
|       - Max Downtime Window   (Downtime <= 8.0h)                                  |
|       - Minimum Acceptable RUL (RUL >= 1.0h)                                      |
|       => Status: FEASIBLE | INFEASIBLE | UNKNOWN                                  |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|             DIMENSIONLESS UTILITY MAPPING & WEIGHTED MCDA SCORING                 |
|       u_i in [0.0, 1.0] (Dimensionless Higher-is-Better Utilities)                |
|       Score = sum(w_i * u_i), where sum(w_i) = 1.0                               |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                 CANDIDATE RANKING & NEAR-TIE DETECTION                            |
|       1. Prioritize FEASIBLE candidates above INFEASIBLE                          |
|       2. Sort descending by Multi-Criteria Utility Score                          |
|       3. Detect near-ties when |Score_i - Score_{i+1}| <= 0.015                   |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                POLICY SENSITIVITY & RANK STABILITY ANALYSIS                       |
|       Evaluate rankings across: BALANCED, SAFETY_FIRST, PRODUCTION_FIRST          |
|       => Stability: HIGH_STABILITY | MODERATE_STABILITY | LOW_STABILITY           |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|            EXPLAINABLE DECISION NARRATIVE & AUDIT PERSISTENCE                     |
|       - Deterministic rule-based trade-off summary against baseline               |
|       - Evidence tracking to DecisionModel database record                        |
|       - Recommended Action pending Human Supervisor Authorization                 |
+-----------------------------------------------------------------------------------+
```

---

## 2. Decision Criteria & Dimensionless Utilities

To compare dissimilar physical, economic, and operational metrics objectively, the engine projects all metrics onto standardized dimensionless utilities $u_i \in [0.0, 1.0]$, where **$1.0$ represents optimal performance** and **$0.0$ represents worst-case acceptability**.

### 2.1 The Six Core Criteria

| Criterion | Metric | Directionality | Scale / Bounds | Utility Formula |
|---|---|---|---|---|
| **Risk** | Projected Failure Probability ($P_{\text{fail}}$) | Lower is better | $[0.0, 1.0]$ | $u_{\text{risk}} = 1.0 - \text{clamp}(P_{\text{fail}}, 0, 1)$ |
| **Cost** | Operational / Intervention Cost | Lower is better | RM $0$ to RM $2,000$ | $u_{\text{cost}} = 1.0 - \text{clamp}\left(\frac{\text{Cost}}{2000}, 0, 1\right)$ |
| **Production Impact** | Throughput Loss Percentage | Lower is better | $0\%$ to $100\%$ | $u_{\text{prod}} = 1.0 - \text{clamp}\left(\frac{\text{Loss}\%}{100}, 0, 1\right)$ |
| **Downtime** | Operational Downtime Duration | Lower is better | $0\text{h}$ to $12\text{h}$ | $u_{\text{downtime}} = 1.0 - \text{clamp}\left(\frac{\text{Downtime}}{12}, 0, 1\right)$ |
| **Recovery Time** | Maintenance Recovery Duration | Lower is better | $0\text{h}$ to $6\text{h}$ | $u_{\text{recovery}} = 1.0 - \text{clamp}\left(\frac{\text{Recovery}}{6}, 0, 1\right)$ |
| **Health Preservation** | Residual RUL & Health Score | Higher is better | RUL $\le 48\text{h}$, Health $\le 100$ | $u_{\text{health}} = 0.5 \cdot \text{clamp}\left(\frac{\text{RUL}}{48}, 0, 1\right) + 0.5 \cdot \text{clamp}\left(\frac{\text{Health}}{100}, 0, 1\right)$ |

### 2.2 Standardized Intervention Cost Mapping (in Malaysian Ringgit - RM)

* `DO_NOTHING`: RM 0.00
* `LOAD_MODULATION (-20%)`: RM 80.00 (Inverter torque/speed tuning & recalibration)
* `LOAD_MODULATION (-40%)`: RM 100.00 (Heavy derating & tooling speed adjustment)
* `COOLING_BOOST (+25%)`: RM 120.00 (Auxiliary chiller activation & coolant fluid cycle)
* `SCHEDULED_SHUTDOWN`: RM 450.00 (Off-peak planned technician deployment & turnaround)
* `EMERGENCY_STOP`: RM 1,200.00 (Immediate triage, lockout-tagout reset, scrap clearance)

---

## 3. Operational Policy Profiles & Weighting

Weights represent operational policy preferences and corporate risk appetite. All weights are configuration-driven and automatically normalized such that $\sum w_i = 1.0$:

$$w_i^{\text{norm}} = \frac{w_i}{\sum_{j=1}^6 w_j}$$

### Default Policy Profiles

```json
{
  "BALANCED": {
    "risk_weight": 0.25,
    "cost_weight": 0.15,
    "production_weight": 0.20,
    "downtime_weight": 0.15,
    "recovery_weight": 0.10,
    "health_weight": 0.15
  },
  "SAFETY_FIRST": {
    "risk_weight": 0.40,
    "cost_weight": 0.05,
    "production_weight": 0.10,
    "downtime_weight": 0.10,
    "recovery_weight": 0.10,
    "health_weight": 0.25
  },
  "PRODUCTION_FIRST": {
    "risk_weight": 0.15,
    "cost_weight": 0.15,
    "production_weight": 0.40,
    "downtime_weight": 0.15,
    "recovery_weight": 0.05,
    "health_weight": 0.10
  }
}
```

---

## 4. Hard Constraints vs Preferences

A central design tenet of NEXUS is that **hard physical and safety boundaries must never be compensated by high utility scores elsewhere**.

If an action violates an operational constraint, it is classified as `INFEASIBLE` with the exact violation recorded, rather than receiving an arbitrary low score:

1. **Critical Failure Probability Limit**: Continuing operating when $P_{\text{fail}} > 0.70$ is strictly prohibited.
2. **Thermal Runaway Limit**: Operating with peak core temperature $T_{\text{peak}} > 90.0^\circ\text{C}$ is strictly prohibited.
3. **Maximum Allowed Downtime**: Any scheduled or emergency intervention resulting in downtime $> 8.0\text{h}$ is deemed unviable for the current production shift.
4. **Minimum Acceptable RUL Margin**: Operating when projected RUL $< 1.0\text{h}$ without immediate scheduled maintenance is prohibited.

> **Exemption Rule for Halt Actions**: Actions designed specifically to halt equipment degradation (`EMERGENCY_STOP`, `SCHEDULED_SHUTDOWN`) are exempted from the operating hazard and temperature continuation checks, as their explicit engineering purpose is to terminate equipment operation.

---

## 5. Candidate Ranking & Near-Tie Detection

The Decision Engine sorts candidate actions using a two-tier hierarchy:
1. **Feasibility Partitioning**: All `FEASIBLE` candidates are ranked above `UNKNOWN` and `INFEASIBLE` candidates.
2. **Score Maximization**: Candidates within each partition are sorted descending by multi-criteria decision score:
   $$\text{Decision Score} = \sum_{i=1}^6 w_i^{\text{norm}} \cdot u_i$$

### Near-Tie Detection ($\Delta \le 0.015$)
When the utility scores of two adjacent feasible candidates differ by $\le 0.015$, the engine flags a **near-tie** (`near_tie: true`, `near_tie_with: "<Other Action>"`). This signals to human plant supervisors that both options offer mathematically equivalent value, and shift context (such as urgent dispatch orders or technician availability) should guide final approval.

---

## 6. Sensitivity Analysis & Rank Stability

The engine evaluates candidate rankings across all three foundational policy profiles (`BALANCED`, `SAFETY_FIRST`, `PRODUCTION_FIRST`) to assess recommendation fragility:

* **HIGH_STABILITY**: The top recommended action is identical across all three policies. The action is structurally dominant.
* **MODERATE_STABILITY**: The top recommended action is preferred under 2 of 3 policies. Stakeholders are advised of the divergent policy condition.
* **LOW_STABILITY**: The top recommendation shifts across every profile. Explicit management alignment on operational priorities is recommended before proceeding.

---

## 7. REST API Endpoints

### 7.1 Catalog & Policies
`GET /api/v1/decision-policies` (or `/api/v1/decisions/policies`)
* Returns available operational policies, default weights, and domain constraints.

### 7.2 On-Demand Decision Analysis
`POST /api/v1/decisions/analyze`
* **Request**:
```json
{
  "machine_id": "M01",
  "policy_profile": "BALANCED",
  "horizon_hours": 4.0,
  "persist": true
}
```
* **Response**: Returns `DecisionAnalysisResponse` with ranked candidates, utility scores, near-tie indicators, stability rating, evidence references, and executive explanation.

### 7.3 Historical Decision Queries
* `GET /api/v1/decisions`: List historical decision records with filtering by `machine_id` and `policy_profile`.
* `GET /api/v1/decisions/{decision_id}`: Retrieve full decision evaluation by ID.
* `GET /api/v1/machines/{machine_id}/decisions`: Retrieve historical decision evaluations for a specific machine.

---

## 8. Performance SLA Benchmark

* **SLA Requirement**: P95 latency $< 200\text{ ms}$.
* **Empirical Benchmark Results** (15 iterations across multiple machines):
  * **P50 Latency**: `19.83 ms`
  * **P95 Latency**: `22.78 ms`
  * **Maximum Latency**: `25.68 ms`
  * **Headroom**: ~8.7x faster than the maximum allowed SLA limit.
