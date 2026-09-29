"""
Predictive Dataset & Ground Truth Generation
Generates synthetic run-to-failure and degradation trajectories across multiple failure modes
with time-aware trajectory splitting (Train / Val / Test) and exact mathematical ground truth.
"""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Any
import numpy as np

from services.schemas import TelemetryCreate, OperatingStatus
from services.simulation.config import get_default_factory_spec, MachineSpec
from services.simulation.machine import SimulatedMachine
from services.prediction.config import (
    DEFAULT_HORIZONS_MINUTES,
    CRITICAL_HEALTH_THRESHOLD,
    MAX_RUL_HOURS,
    COLD_START_MIN_SAMPLES,
)
from services.prediction.features import PredictiveFeatureExtractor


# 1 simulation step = 6 operating minutes = 0.10 hours
STEP_MINUTES = 6.0
STEP_HOURS = STEP_MINUTES / 60.0


@dataclass
class DatasetSplit:
    X: np.ndarray
    y_rul: np.ndarray
    y_failure: Dict[int, np.ndarray]  # horizon_minutes -> binary failure label (0 or 1)
    y_health: Dict[int, np.ndarray]   # horizon_minutes -> future health score (0-100)
    trajectories_count: int
    samples_count: int


def generate_single_trajectory(
    spec: MachineSpec,
    scenario_type: str,
    total_steps: int = 100,
    seed: int = 42
) -> Tuple[List[TelemetryCreate], List[float], int]:
    """
    Simulates a full machine trajectory under a specific scenario.
    Returns:
        (telemetries, health_scores, failure_step) where failure_step is -1 if no failure occurred.
    """
    rng = np.random.default_rng(seed)
    machine = SimulatedMachine(spec=spec, rng=rng)
    telemetries: List[TelemetryCreate] = []
    health_scores: List[float] = []
    failure_step: int = -1

    base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    dt_seconds = STEP_MINUTES * 60.0

    for step in range(total_steps):
        current_time = base_time + timedelta(minutes=step * STEP_MINUTES)

        # Apply scenario dynamics
        if scenario_type == "normal":
            # Mild load variation, healthy machine
            load_variation = 0.95 + 0.10 * np.sin(step * 0.15) + rng.uniform(-0.02, 0.02)
            machine.set_load(float(load_variation))

        elif scenario_type == "bearing_degradation":
            # Normal for first 15 steps, then progressive bearing wear cascading to thermal/electrical stress
            if step > 15:
                progress = (step - 15) / max(1, total_steps - 15)
                machine.bearing_degradation = min(1.0, float(progress * 1.1))
                if progress > 0.4:
                    machine.cooling_degradation = min(0.85, float((progress - 0.4) * 1.5))
                    machine.electrical_degradation = min(0.70, float((progress - 0.4) * 1.2))

        elif scenario_type == "cooling_degradation":
            # Normal for first 15 steps, then coolant clogging leading to thermal and lubrication breakdown
            if step > 15:
                progress = (step - 15) / max(1, total_steps - 15)
                machine.cooling_degradation = min(1.0, float(progress * 1.1))
                if progress > 0.4:
                    machine.bearing_degradation = min(0.85, float((progress - 0.4) * 1.4))
                    machine.electrical_degradation = min(0.60, float((progress - 0.4) * 1.0))

        elif scenario_type == "overload":
            # Severe load causing accelerated wear and overheating
            if step > 10:
                if step <= 65:
                    machine.set_load(1.25)
                    progress = (step - 10) / 55.0
                    machine.bearing_degradation = min(0.95, float(progress * 1.0))
                    machine.cooling_degradation = min(0.85, float(progress * 0.9))
                    machine.electrical_degradation = min(0.75, float(progress * 0.8))

        elif scenario_type == "recovery":
            # Degrades until step 40, then maintenance reset back to pristine
            if 15 < step <= 40:
                progress = (step - 15) / 25.0
                machine.bearing_degradation = min(0.55, float(progress * 0.55))
            elif step > 40:
                machine.apply_maintenance()

        # Step physics
        machine.step_physics(dt_seconds=dt_seconds)

        # Automatic electrical/thermal trip protection if critical failure occurred
        if machine.health_score <= CRITICAL_HEALTH_THRESHOLD:
            machine.operating_status = OperatingStatus.FAILED
            machine.set_load(0.0)

        t_frame = machine.generate_telemetry(timestamp=current_time)
        h = machine.health_score

        telemetries.append(t_frame)
        health_scores.append(h)

        # Track first failure point
        if failure_step == -1 and (h <= CRITICAL_HEALTH_THRESHOLD or machine.operating_status == OperatingStatus.FAILED):
            failure_step = step

    return telemetries, health_scores, failure_step


def process_trajectory_samples(
    telemetries: List[TelemetryCreate],
    health_scores: List[float],
    failure_step: int,
    horizons_minutes: List[int] = DEFAULT_HORIZONS_MINUTES
) -> Tuple[np.ndarray, np.ndarray, Dict[int, np.ndarray], Dict[int, np.ndarray]]:
    """
    Extracts strictly historical feature vectors and ground truth labels for a trajectory.
    """
    extractor = PredictiveFeatureExtractor(window_size=20)
    X_list: List[np.ndarray] = []
    y_rul_list: List[float] = []
    y_failure_map: Dict[int, List[float]] = {h: [] for h in horizons_minutes}
    y_health_map: Dict[int, List[float]] = {h: [] for h in horizons_minutes}

    total_steps = len(telemetries)

    for step in range(total_steps):
        t_frame = telemetries[step]
        h = health_scores[step]

        # Extract features (internally pushes to window)
        _, vector = extractor.extract_features(
            machine_id=t_frame.machine_id,
            current_telemetry=t_frame,
            current_health=h
        )

        # Wait until sufficient history is available
        if vector is None:
            continue

        # 1. Ground truth RUL point estimate
        if failure_step != -1:
            if step < failure_step:
                rul_val = (failure_step - step) * STEP_HOURS
            else:
                rul_val = 0.0
        else:
            rul_val = MAX_RUL_HOURS

        X_list.append(vector)
        y_rul_list.append(rul_val)

        # 2. Multi-horizon failure binary label & health trajectory
        for h_min in horizons_minutes:
            h_hours = h_min / 60.0
            h_steps = int(round(h_min / STEP_MINUTES))

            # Binary failure label: will machine fail within horizon?
            failed_in_horizon = 1.0 if rul_val <= h_hours else 0.0
            y_failure_map[h_min].append(failed_in_horizon)

            # Future health target
            future_step = min(total_steps - 1, step + h_steps)
            future_health = health_scores[future_step]
            y_health_map[h_min].append(future_health)

    if not X_list:
        empty_x = np.empty((0, len(extractor.calculate_slope([1, 2]))))
        return empty_x, np.array([]), {h: np.array([]) for h in horizons_minutes}, {h: np.array([]) for h in horizons_minutes}

    return (
        np.array(X_list, dtype=float),
        np.array(y_rul_list, dtype=float),
        {h: np.array(vals, dtype=float) for h, vals in y_failure_map.items()},
        {h: np.array(vals, dtype=float) for h, vals in y_health_map.items()},
    )


def generate_predictive_dataset(
    num_trajectories_per_scenario: int = 10,
    steps_per_trajectory: int = 90,
    horizons_minutes: List[int] = DEFAULT_HORIZONS_MINUTES,
    seed: int = 42
) -> Tuple[DatasetSplit, DatasetSplit, DatasetSplit]:
    """
    Generates time-aware / trajectory-level split dataset (Train, Val, Test).
    Guarantees no trajectory cross-contamination.
    """
    factory_spec = get_default_factory_spec()
    machines = factory_spec.all_machines()  # M01 - M06
    scenarios = ["normal", "bearing_degradation", "cooling_degradation", "overload", "recovery"]

    train_trajs = []
    val_trajs = []
    test_trajs = []

    traj_idx = 0
    for scenario in scenarios:
        scenario_trajs = []
        for i in range(num_trajectories_per_scenario):
            m_spec = machines[traj_idx % len(machines)]
            current_seed = seed + traj_idx * 17
            telems, healths, f_step = generate_single_trajectory(
                spec=m_spec,
                scenario_type=scenario,
                total_steps=steps_per_trajectory,
                seed=current_seed
            )
            scenario_trajs.append((telems, healths, f_step))
            traj_idx += 1

        n_scen = len(scenario_trajs)
        n_train = max(1, int(round(n_scen * 0.60)))
        n_val = max(1, int(round(n_scen * 0.20)))
        train_trajs.extend(scenario_trajs[:n_train])
        val_trajs.extend(scenario_trajs[n_train:n_train + n_val])
        test_trajs.extend(scenario_trajs[n_train + n_val:])

    def build_split(trajs: List[Any]) -> DatasetSplit:
        X_all, y_rul_all = [], []
        y_fail_all: Dict[int, List[np.ndarray]] = {h: [] for h in horizons_minutes}
        y_health_all: Dict[int, List[np.ndarray]] = {h: [] for h in horizons_minutes}

        for telems, healths, f_step in trajs:
            X, y_rul, y_fail, y_health = process_trajectory_samples(
                telems, healths, f_step, horizons_minutes=horizons_minutes
            )
            if len(X) > 0:
                X_all.append(X)
                y_rul_all.append(y_rul)
                for h in horizons_minutes:
                    y_fail_all[h].append(y_fail[h])
                    y_health_all[h].append(y_health[h])

        X_cat = np.concatenate(X_all, axis=0) if X_all else np.empty((0, 0))
        y_rul_cat = np.concatenate(y_rul_all, axis=0) if y_rul_all else np.empty((0,))
        y_fail_cat = {h: np.concatenate(y_fail_all[h], axis=0) for h in horizons_minutes}
        y_health_cat = {h: np.concatenate(y_health_all[h], axis=0) for h in horizons_minutes}

        return DatasetSplit(
            X=X_cat,
            y_rul=y_rul_cat,
            y_failure=y_fail_cat,
            y_health=y_health_cat,
            trajectories_count=len(trajs),
            samples_count=len(X_cat)
        )

    train_split = build_split(train_trajs)
    val_split = build_split(val_trajs)
    test_split = build_split(test_trajs)

    return train_split, val_split, test_split
