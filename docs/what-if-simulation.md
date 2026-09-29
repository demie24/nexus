# NEXUS What-If Counterfactual Simulation Engine Architecture

## 1. Overview
The **NEXUS What-If Counterfactual Simulation Engine** answers the pivotal Decision Intelligence question:
> *"Apa yang mungkin berlaku jika operator atau sistem melaksanakan intervensi tertentu ke atas mesin?"*

Unlike naive heuristics or static lookups, NEXUS evaluates counterfactual branches forward in time using physically grounded thermo-mechanical equations. When an intervention is proposed, the platform forks an isolated sandbox from an immutable Digital Twin snapshot, integrates the physical dynamics forward across a user-defined horizon (1h, 2h, 4h, 8h), and records objective outcome metrics for comparative analysis.

> [!IMPORTANT]
> **Decision Support Boundary**: Phase 7 does **NOT** select the "best" action or provide automated operational recommendations. The What-If Simulation Engine purely generates evidence, delta metrics, and counterfactual trajectories. Multi-criteria optimization and ranking are deferred to Phase 8 (Decision Engine).

```text
Live Digital Twin (PostgreSQL / In-Memory Cache)
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│         Immutable Digital Twin Snapshot Capture        │
│  - Deep copy of machine states at timestamp T_0        │
│  - Cryptographic SHA-256 state hash                    │
│  - Strictly isolated: live state is never mutated      │
└───────────────────────┬────────────────────────────────┘
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
┌──────────────────┐          ┌──────────────────┐
│ Sandbox Branch A │          │ Sandbox Branch B │  (All branches share
│    DO_NOTHING    │          │    LOAD -20%     │   the exact same snapshot)
└────────┬─────────┘          └────────┬─────────┘
         │                             │
         ▼                             ▼
┌────────────────────────────────────────────────────────┐
│             Forward Physical Integration               │
│  - Reuses Phase 2 thermo-mechanical physics equations  │
│  - Step size dt = 60s (discrete ODE integration)       │
│  - Evaluates wear progression, heat, vibration, power  │
│  - Enforces physical sanity boundary guards            │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│          Multi-Machine Cascade Analyzer                │
│  - Production Line 01 (M01 -> M02 -> M03)              │
│  - Production Line 02 (M04 -> M05 -> M06)              │
│  - Evaluates line bottleneck and throughput loss       │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│           Outcome Metrics & Baseline Comparison        │
│  - RUL delta, Risk delta (percentage points vs rel %)  │
│  - Total production output & throughput loss           │
│  - Tagged explicitly as `SIMULATED`                    │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│           Persistence & REST API Gateway               │
│  - PostgreSQL `simulations` & `simulation_snapshots`   │
│  - Endpoints: /what-if, /compare, /scenarios, /results │
└────────────────────────────────────────────────────────┘
```

---

## 2. Immutable Snapshot & Sandboxing Architecture

To guarantee fair, uncorrupted scenario comparisons:
1. **Immutable Snapshot**:
   - `snapshot_id`: Unique identifier (e.g. `SNAP-20260929153346-0e5064`).
   - `created_at`: Point-in-time timestamp.
   - `state_hash`: Cryptographic SHA-256 hash of machine states, guaranteeing auditability.
   - `machine_states`: Deep-copied dictionary of all 6 machines in the factory.
   - Any mutation to the snapshot object returns a defensive deep copy.
2. **Digital Twin Fork**:
   - The sandbox machine is an instance of `SimulatedMachine` calibrated to the snapshot state (`load`, `temperature`, `vibration`, `bearing_degradation`, `cooling_degradation`).
   - The live Digital Twin remains 100% untouched.

---

## 3. Supported Intervention Scenarios

NEXUS natively models 5 core counterfactual interventions:

| Scenario Type | Action Description | Parameters | Physical Impact |
| :--- | :--- | :--- | :--- |
| `DO_NOTHING` | Baseline trajectory without intervention. | None | Ongoing degradation advances under nominal operational stress. |
| `LOAD_MODULATION` | Reduces mechanical and electrical load. | `load_reduction` $\in [0.0, 1.0]$ (e.g. $0.20, 0.40$) | Heat generation ($\propto \text{load}^{1.3}$) and wear rate ($\propto \text{load}^{1.5}$) drop; operating temperature decreases; RUL extends; output scales with load. |
| `COOLING_BOOST` | Engages auxiliary cooling / fans. | `cooling_multiplier` $> 0.0$ (e.g. $1.25, 1.50$) | Increases effective thermal dissipation coefficient ($k_{\text{cool}}$); operating temperature drops; thermal wear is mitigated without sacrificing production output. |
| `SCHEDULED_SHUTDOWN` | Continues operation until off-peak cutoff, then initiates planned stop. | `shutdown_delay_hours` $\in [0.0, \text{horizon}]$ | Produces output until cutoff; controlled cooldown to ambient ($24^\circ\text{C}$); wear freezes; planned recovery window ($1.5\text{ h}$). |
| `EMERGENCY_STOP` | Immediate emergency halt at $t = 0$. | None | Immediate zero load and zero output; immediate cooldown; wear freezes; emergency inspection window ($3.0\text{ h}$). |

---

## 4. Simulation Horizon & Time Dilation

* **Configurable Horizon**: Supports arbitrary forward horizons from $0.5\text{ hours}$ to $48.0\text{ hours}$ (standard presets: $1\text{h}, 2\text{h}, 4\text{h}, 8\text{h}$).
* **Simulation Time vs Wall-Clock Time**:
  * In **Simulation Time**, physical dynamics evolve over discrete 60-second time steps ($dt = 60\text{ s}$). A 4-hour horizon contains $240$ discrete physics steps.
  * In **Wall-Clock Execution Time**, all ODE and thermodynamic integrations occur in memory, executing 240 steps in **$\approx 6.9\text{ ms}$** on standard CPU hardware.

---

## 5. Multi-Machine Cascade Dynamics

NEXUS does not assume that machines exist in vacuum. In the virtual factory:
* **Production Line 01**: Sequential Machining (M01 Milling $\rightarrow$ M02 Lathe $\rightarrow$ M03 Grinder).
* **Production Line 02**: Sequential Assembly (M04 Welder $\rightarrow$ M05 Press $\rightarrow$ M06 Packaging).

When target machine $M_{target}$ undergoes intervention:
1. **Bottleneck Throughput**: Line finished output is bounded by $\min_{m \in \text{Line}} (\text{output\_rate}_m)$.
2. **Buffer Hold / Throttling**:
   - If M03 is halted (`EMERGENCY_STOP`), upstream units M01 and M02 cannot dispatch finished parts; they enter `LINE_HALTED_BUFFER_HOLD`, and Line 01 finished output drops to 0.
   - If M03 is throttled to 60% load (`load_reduction = 0.40`), M01 and M02 are synchronized to match the 60% line pace.
3. **Independent Lines**: Line 02 remains completely unaffected by interventions on Line 01.

---

## 6. Outcome Metrics & Baseline Comparison

Every counterfactual simulation outputs structured metrics:
* `initial_health` & `final_health`: Health score ($0 - 100\%$) tracking wear degradation.
* `initial_failure_probability` & `final_failure_probability`: Calibrated hazard probability ($0.0 - 1.0$).
* `initial_rul` & `final_rul`: Remaining Useful Life in hours.
* `peak_temperature`: Maximum recorded core temperature ($^\circ\text{C}$).
* `peak_vibration`: Maximum recorded vibration amplitude ($\text{mm/s}$).
* `total_output`: Cumulative units produced during the horizon.
* `throughput_loss`: Fractional loss relative to nominal capacity ($0.0 - 1.0$).
* `downtime`: Hours spent in non-operating / shutdown states.
* `recovery_time`: Required maintenance or inspection window (or `null`).

### Rigorous Baseline Comparison:
When compared against `DO_NOTHING`:
* **Percentage Points Delta**: Strictly measured as $(P_{\text{scenario}} - P_{\text{baseline}}) \times 100$. For example, a drop from $76\%$ to $41\%$ is reported as **$-35.0\text{ percentage points}$**, never ambiguously labeled as "35% reduction".
* **Relative Percentage Reduction**: $(P_{\text{baseline}} - P_{\text{scenario}}) / P_{\text{baseline}} \times 100 = 46.1\%$.
* **RUL Extension**: $RUL_{\text{scenario}} - RUL_{\text{baseline}}$ in hours.
* **Throughput Loss**: Relative percentage of units foregone compared to baseline output.

---

## 7. Determinism & Physical Sanity Enforcement

1. **Deterministic Replay**:
   - Given identical `snapshot_id`, `machine_id`, `scenario_type`, `parameters`, `horizon`, and `seed`, the simulation outputs bitwise identical numerical results.
2. **Physical Boundary Guards**:
   - The engine validates every step against physical conservation laws:
     - $T_{\text{peak}} \ge 15.0^\circ\text{C}$ (ambient minimum)
     - $0.0 \le \text{health} \le 100.0$
     - $0.0 \le P_{\text{fail}} \le 1.0$
     - $\text{output} \ge 0.0$
   - Violations raise a controlled `SimulationSanityError` and mark the simulation `FAILED` rather than silently clamping corrupt results.

---

## 8. Performance SLA Benchmarks

Evaluated over 50 consecutive runs on an Ubuntu Linux workstation:

| Benchmark Scenario | SLA Threshold | Measured Benchmark |
| :--- | :--- | :--- |
| **P95 Latency (Single-Machine 4-Hour)** | $< 500\text{ ms}$ | **$8.25\text{ ms}$** |
| **Mean Latency (Single-Machine 4-Hour)** | $< 250\text{ ms}$ | **$6.90\text{ ms}$** |
| **P50 Latency (Single-Machine 4-Hour)** | $< 100\text{ ms}$ | **$6.52\text{ ms}$** |
| **Multi-Scenario Comparison Suite (5 scenarios, 8-hour horizon)** | $< 2000\text{ ms}$ | **$64.45\text{ ms}$** |
| **Deterministic Consistency** | $100\%$ | **$100\%$ Identical** |

---

## 9. REST API Reference

The What-If Simulation Engine exposes the following endpoints:

* `POST /api/v1/simulation/what-if`: Executes an on-demand counterfactual simulation.
* `POST /api/v1/simulation/compare`: Executes and formats a side-by-side comparison matrix across multiple intervention branches.
* `GET /api/v1/simulation/scenarios`: Returns catalog of supported scenarios and configurable parameter bounds.
* `GET /api/v1/simulation/{simulation_id}`: Retrieves simulation execution metadata and lifecycle status.
* `GET /api/v1/simulation/{simulation_id}/results`: Retrieves detailed outcome metrics, baseline comparison, and cascade reports.
