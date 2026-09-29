"""
NEXUS Digital Twin Immutable Snapshot Manager
Captures point-in-time states of the factory digital twin, guarantees immutability,
computes cryptographic state hashes, and provides isolated forks for counterfactual simulations.
"""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import Dict, List, Optional, Any
import uuid

from sqlalchemy.orm import Session

from database.models.models import SimulationSnapshotModel, MachineModel, MachineStateModel, TelemetryModel
from services.schemas import DigitalTwinSnapshot, DigitalTwinState, FreshnessStatus, OperatingStatus, DataProvenance
from services.simulation.config import get_default_factory_spec

logger = logging.getLogger("nexus.simulation.snapshot")


class DigitalTwinSnapshotManager:
    """
    Manages creation, immutability, and retrieval of point-in-time Digital Twin snapshots.
    """

    def __init__(self):
        self._cache: Dict[str, DigitalTwinSnapshot] = {}

    def _compute_state_hash(self, machine_states: Dict[str, Any], factory_id: str) -> str:
        """Computes deterministic SHA-256 hash of machine states."""
        serialized = json.dumps(
            {"factory_id": factory_id, "machines": machine_states},
            sort_keys=True,
            default=str
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def create_snapshot(
        self,
        db: Optional[Session] = None,
        dt_engine: Optional[Any] = None,
        factory_id: str = "NEXUS-FACTORY-01",
        custom_machine_states: Optional[Dict[str, Any]] = None,
        telemetry_context: Optional[Dict[str, Any]] = None,
        prediction_context: Optional[Dict[str, Any]] = None,
    ) -> DigitalTwinSnapshot:
        """
        Creates an immutable snapshot of current Digital Twin states.
        Guarantees that simulation executions cannot mutate live production states.
        """
        now = datetime.now(timezone.utc)
        machine_states: Dict[str, Any] = {}
        machines_list: List[str] = []

        if custom_machine_states:
            machine_states = deepcopy(custom_machine_states)
            machines_list = list(machine_states.keys())
        elif db is not None:
            # Query machine states from database
            db_machines = db.query(MachineModel).all()
            for m in db_machines:
                machines_list.append(m.id)
                state_record = db.query(MachineStateModel).filter_by(machine_id=m.id).first()
                if state_record:
                    machine_states[m.id] = {
                        "machine_id": m.id,
                        "machine_name": m.name,
                        "line_id": m.line_id,
                        "machine_type": m.machine_type,
                        "status": state_record.status,
                        "freshness": state_record.freshness,
                        "health_score": float(state_record.health_score),
                        "failure_probability": float(state_record.failure_probability),
                        "load_factor": float(state_record.load_factor),
                        "maintenance_status": state_record.maintenance_status,
                        "temperature": float(state_record.temperature),
                        "vibration": float(state_record.vibration),
                        "pressure": float(state_record.pressure),
                        "current": float(state_record.current),
                        "voltage": float(state_record.voltage),
                        "rpm": float(state_record.rpm),
                        "power_kw": float(state_record.power_kw),
                        "efficiency": float(state_record.efficiency),
                        "output_rate": float(state_record.output_rate),
                        "last_telemetry_timestamp": state_record.last_telemetry_timestamp.isoformat() if state_record.last_telemetry_timestamp else None,
                        "provenance": state_record.provenance,
                    }
                else:
                    # Nominal default
                    machine_states[m.id] = {
                        "machine_id": m.id,
                        "machine_name": m.name,
                        "line_id": m.line_id,
                        "machine_type": m.machine_type,
                        "status": "OPERATING",
                        "freshness": "FRESH",
                        "health_score": 100.0,
                        "failure_probability": 0.01,
                        "load_factor": 1.0,
                        "maintenance_status": "OK",
                        "temperature": m.nominal_temp_c,
                        "vibration": m.nominal_vib_mms,
                        "pressure": 2.5,
                        "current": 20.0,
                        "voltage": 400.0,
                        "rpm": m.nominal_rpm,
                        "power_kw": m.nominal_power_kw,
                        "efficiency": 100.0,
                        "output_rate": 60.0,
                        "last_telemetry_timestamp": now.isoformat(),
                        "provenance": "OBSERVED",
                    }
        else:
            # Fallback to nominal factory spec
            spec = get_default_factory_spec()
            for m in spec.all_machines():
                machines_list.append(m.machine_id)
                machine_states[m.machine_id] = {
                    "machine_id": m.machine_id,
                    "machine_name": m.name,
                    "line_id": m.line_id,
                    "machine_type": m.machine_type,
                    "status": "OPERATING",
                    "freshness": "FRESH",
                    "health_score": 100.0,
                    "failure_probability": 0.01,
                    "load_factor": 1.0,
                    "maintenance_status": "OK",
                    "temperature": m.nominal_temp_c,
                    "vibration": m.nominal_vib_mms,
                    "pressure": m.nominal_pressure_bar,
                    "current": m.nominal_current_a,
                    "voltage": m.nominal_voltage_v,
                    "rpm": m.nominal_rpm,
                    "power_kw": m.nominal_power_kw,
                    "efficiency": 100.0,
                    "output_rate": m.nominal_output_rate,
                    "last_telemetry_timestamp": now.isoformat(),
                    "provenance": "OBSERVED",
                }

        state_hash = self._compute_state_hash(machine_states, factory_id)
        snapshot_id = f"SNAP-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

        snapshot = DigitalTwinSnapshot(
            snapshot_id=snapshot_id,
            factory_id=factory_id,
            created_at=now,
            machines=machines_list,
            machine_states=machine_states,
            telemetry_context=deepcopy(telemetry_context or {}),
            prediction_context=deepcopy(prediction_context or {}),
            state_hash=state_hash,
        )

        # Cache in memory
        self._cache[snapshot_id] = deepcopy(snapshot)

        # Persist to database if session provided
        if db is not None:
            try:
                db_record = SimulationSnapshotModel(
                    snapshot_id=snapshot.snapshot_id,
                    factory_id=snapshot.factory_id,
                    created_at=snapshot.created_at,
                    machines=snapshot.machines,
                    machine_states=snapshot.machine_states,
                    telemetry_context=snapshot.telemetry_context,
                    prediction_context=snapshot.prediction_context,
                    state_hash=snapshot.state_hash,
                )
                db.add(db_record)
                db.commit()
            except Exception as err:
                db.rollback()
                logger.warning(f"Could not persist simulation snapshot to DB: {err}")

        return deepcopy(snapshot)

    def get_snapshot(self, snapshot_id: str, db: Optional[Session] = None) -> Optional[DigitalTwinSnapshot]:
        """
        Retrieves an immutable copy of the snapshot by ID.
        Returns a deep copy to ensure complete immutability.
        """
        if snapshot_id in self._cache:
            return deepcopy(self._cache[snapshot_id])

        if db is not None:
            record = db.query(SimulationSnapshotModel).filter_by(snapshot_id=snapshot_id).first()
            if record:
                snapshot = DigitalTwinSnapshot(
                    snapshot_id=record.snapshot_id,
                    factory_id=record.factory_id,
                    created_at=record.created_at,
                    machines=record.machines,
                    machine_states=record.machine_states,
                    telemetry_context=record.telemetry_context,
                    prediction_context=record.prediction_context,
                    state_hash=record.state_hash,
                )
                self._cache[snapshot_id] = deepcopy(snapshot)
                return deepcopy(snapshot)

        return None

    def fork_machine_state(self, snapshot: DigitalTwinSnapshot, machine_id: str) -> Optional[Dict[str, Any]]:
        """
        Extracts an isolated, deep-copied state for a single machine from the snapshot.
        """
        state = snapshot.machine_states.get(machine_id)
        if not state:
            return None
        return deepcopy(state)


_global_snapshot_manager: Optional[DigitalTwinSnapshotManager] = None


def get_snapshot_manager() -> DigitalTwinSnapshotManager:
    global _global_snapshot_manager
    if _global_snapshot_manager is None:
        _global_snapshot_manager = DigitalTwinSnapshotManager()
    return _global_snapshot_manager
