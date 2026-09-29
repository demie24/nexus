"""
NEXUS Digital Twin Engine
Maintains current state representations, evaluates deterministic state transitions,
tracks data freshness/staleness, and generates factory snapshots.
"""

from datetime import datetime, timezone, timedelta
import logging
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

from database.models.models import MachineModel, MachineStateModel, TelemetryModel
from services.schemas import (
    OperatingStatus,
    FreshnessStatus,
    DigitalTwinState,
    FactorySnapshot,
    DataProvenance,
)

logger = logging.getLogger("nexus.digital_twin")


class DigitalTwinEngine:
    def __init__(self, stale_threshold_seconds: float = 60.0):
        self.stale_threshold_seconds = stale_threshold_seconds
        # In-memory fast cache of Digital Twin states keyed by machine_id
        self._states_cache: Dict[str, DigitalTwinState] = {}

    def determine_state_transition(
        self,
        health_score: float,
        failure_prob: float,
        load_factor: float,
        maintenance_status: str,
        current_status: OperatingStatus
    ) -> OperatingStatus:
        """
        Determines machine operational state transition based on deterministic rules.
        """
        if current_status == OperatingStatus.FAILED or health_score <= 0.0:
            return OperatingStatus.FAILED
        if maintenance_status in ["IN_PROGRESS", "MAINTENANCE"]:
            return OperatingStatus.MAINTENANCE
        if health_score < 25.0:
            return OperatingStatus.CRITICAL
        if health_score < 45.0 or failure_prob >= 0.65:
            return OperatingStatus.HIGH_RISK
        if health_score < 75.0 or failure_prob >= 0.30:
            return OperatingStatus.DEGRADED
        if load_factor <= 0.05:
            return OperatingStatus.IDLE

        return OperatingStatus.OPERATING

    def evaluate_freshness(self, last_telemetry_time: Optional[datetime]) -> FreshnessStatus:
        """
        Evaluates whether machine state is FRESH, STALE, or UNKNOWN based on elapsed time.
        """
        if last_telemetry_time is None:
            return FreshnessStatus.UNKNOWN

        now = datetime.now(timezone.utc)
        if last_telemetry_time.tzinfo is None:
            last_telemetry_time = last_telemetry_time.replace(tzinfo=timezone.utc)

        elapsed = (now - last_telemetry_time).total_seconds()
        if elapsed > self.stale_threshold_seconds:
            return FreshnessStatus.STALE
        return FreshnessStatus.FRESH

    def update_from_telemetry(
        self,
        telemetry: TelemetryModel,
        machine: MachineModel,
        db: Session
    ) -> DigitalTwinState:
        """
        Updates the Digital Twin state for a machine upon receiving a valid telemetry frame.
        Persists update to PostgreSQL machine_states table and refreshes in-memory cache.
        """
        state_record = db.query(MachineStateModel).filter_by(machine_id=machine.id).first()

        # Compute dynamic health and failure probability if not already populated
        # Base health derived from vibration and temperature deviation
        temp_delta = max(0.0, telemetry.temperature - machine.nominal_power_kw * 3.5)
        vib_delta = max(0.0, telemetry.vibration - 3.0)
        calc_health = max(0.0, min(100.0, 100.0 - 15.0 * vib_delta - 0.8 * temp_delta))
        calc_fail_prob = min(1.0, max(0.0, (100.0 - calc_health) / 100.0 * 0.95))

        new_status = self.determine_state_transition(
            health_score=calc_health,
            failure_prob=calc_fail_prob,
            load_factor=telemetry.load,
            maintenance_status=machine.maintenance_status,
            current_status=OperatingStatus(state_record.status) if state_record else OperatingStatus.OPERATING
        )

        now = datetime.now(timezone.utc)

        if not state_record:
            state_record = MachineStateModel(
                machine_id=machine.id,
                status=new_status.value,
                freshness=FreshnessStatus.FRESH.value,
                health_score=round(calc_health, 1),
                failure_probability=round(calc_fail_prob, 3),
                load_factor=round(telemetry.load, 2),
                maintenance_status=machine.maintenance_status,
                temperature=telemetry.temperature,
                vibration=telemetry.vibration,
                pressure=telemetry.pressure,
                current=telemetry.current,
                voltage=telemetry.voltage,
                rpm=telemetry.rpm,
                power_kw=telemetry.power_kw,
                efficiency=telemetry.efficiency,
                output_rate=telemetry.output_rate,
                last_telemetry_id=telemetry.id,
                last_telemetry_timestamp=telemetry.timestamp,
                provenance=telemetry.provenance,
                updated_at=now
            )
            db.add(state_record)
        else:
            state_record.status = new_status.value
            state_record.freshness = FreshnessStatus.FRESH.value
            state_record.health_score = round(calc_health, 1)
            state_record.failure_probability = round(calc_fail_prob, 3)
            state_record.load_factor = round(telemetry.load, 2)
            state_record.maintenance_status = machine.maintenance_status
            state_record.temperature = telemetry.temperature
            state_record.vibration = telemetry.vibration
            state_record.pressure = telemetry.pressure
            state_record.current = telemetry.current
            state_record.voltage = telemetry.voltage
            state_record.rpm = telemetry.rpm
            state_record.power_kw = telemetry.power_kw
            state_record.efficiency = telemetry.efficiency
            state_record.output_rate = telemetry.output_rate
            state_record.last_telemetry_id = telemetry.id
            state_record.last_telemetry_timestamp = telemetry.timestamp
            state_record.provenance = telemetry.provenance
            state_record.updated_at = now

        db.commit()
        db.refresh(state_record)

        # Build schema object
        dt_state = DigitalTwinState(
            machine_id=machine.id,
            machine_name=machine.name,
            line_id=machine.line_id,
            machine_type=machine.machine_type,
            status=new_status,
            freshness=FreshnessStatus.FRESH,
            health_score=state_record.health_score,
            failure_probability=state_record.failure_probability,
            load_factor=state_record.load_factor,
            maintenance_status=state_record.maintenance_status,
            temperature=state_record.temperature,
            vibration=state_record.vibration,
            pressure=state_record.pressure,
            current=state_record.current,
            voltage=state_record.voltage,
            rpm=state_record.rpm,
            power_kw=state_record.power_kw,
            efficiency=state_record.efficiency,
            output_rate=state_record.output_rate,
            last_telemetry_timestamp=state_record.last_telemetry_timestamp,
            last_telemetry_id=state_record.last_telemetry_id,
            provenance=DataProvenance(state_record.provenance),
            updated_at=state_record.updated_at
        )

        self._states_cache[machine.id] = dt_state
        return dt_state

    def get_machine_state(self, machine_id: str, db: Session) -> Optional[DigitalTwinState]:
        """
        Retrieves current Digital Twin state for a machine, evaluating freshness dynamically.
        """
        machine = db.query(MachineModel).filter_by(id=machine_id).first()
        if not machine:
            return None

        state_record = db.query(MachineStateModel).filter_by(machine_id=machine_id).first()
        if not state_record:
            # Construct default UNKNOWN state
            return DigitalTwinState(
                machine_id=machine.id,
                machine_name=machine.name,
                line_id=machine.line_id,
                machine_type=machine.machine_type,
                status=OperatingStatus.IDLE,
                freshness=FreshnessStatus.UNKNOWN,
                health_score=100.0,
                failure_probability=0.0,
                load_factor=0.0,
                temperature=0.0,
                vibration=0.0,
                pressure=0.0,
                current=0.0,
                voltage=400.0,
                rpm=0.0,
                power_kw=0.0,
                efficiency=100.0,
                output_rate=0.0
            )

        freshness = self.evaluate_freshness(state_record.last_telemetry_timestamp)

        return DigitalTwinState(
            machine_id=machine.id,
            machine_name=machine.name,
            line_id=machine.line_id,
            machine_type=machine.machine_type,
            status=OperatingStatus(state_record.status),
            freshness=freshness,
            health_score=state_record.health_score,
            failure_probability=state_record.failure_probability,
            load_factor=state_record.load_factor,
            maintenance_status=state_record.maintenance_status,
            temperature=state_record.temperature,
            vibration=state_record.vibration,
            pressure=state_record.pressure,
            current=state_record.current,
            voltage=state_record.voltage,
            rpm=state_record.rpm,
            power_kw=state_record.power_kw,
            efficiency=state_record.efficiency,
            output_rate=state_record.output_rate,
            last_telemetry_timestamp=state_record.last_telemetry_timestamp,
            last_telemetry_id=state_record.last_telemetry_id,
            provenance=DataProvenance(state_record.provenance),
            updated_at=state_record.updated_at
        )

    def get_all_machine_states(self, db: Session) -> List[DigitalTwinState]:
        machines = db.query(MachineModel).all()
        return [self.get_machine_state(m.id, db) for m in machines]

    def get_factory_snapshot(self, db: Session, active_scenarios_count: int = 0) -> FactorySnapshot:
        """
        Aggregates health, counts, and states across all machines in the factory.
        """
        states = self.get_all_machine_states(db)
        total = len(states)
        if total == 0:
            return FactorySnapshot(
                total_machines=0,
                operating_machines=0,
                degraded_machines=0,
                high_risk_machines=0,
                failed_machines=0,
                stale_machines=0,
                overall_health=100.0,
                machines=[]
            )

        operating = sum(1 for s in states if s.status in [OperatingStatus.OPERATING, OperatingStatus.NORMAL])
        degraded = sum(1 for s in states if s.status == OperatingStatus.DEGRADED)
        high_risk = sum(1 for s in states if s.status in [OperatingStatus.HIGH_RISK, OperatingStatus.CRITICAL])
        failed = sum(1 for s in states if s.status == OperatingStatus.FAILED)
        stale = sum(1 for s in states if s.freshness == FreshnessStatus.STALE)

        overall_health = round(sum(s.health_score for s in states) / total, 1)

        # Latest telemetry timestamp across all machines
        valid_timestamps = [s.last_telemetry_timestamp for s in states if s.last_telemetry_timestamp]
        latest_ts = max(valid_timestamps) if valid_timestamps else None

        return FactorySnapshot(
            total_machines=total,
            operating_machines=operating,
            degraded_machines=degraded,
            high_risk_machines=high_risk,
            failed_machines=failed,
            stale_machines=stale,
            overall_health=overall_health,
            active_scenarios=active_scenarios_count,
            latest_telemetry_timestamp=latest_ts,
            machines=states
        )


_digital_twin_engine: Optional[DigitalTwinEngine] = None


def get_digital_twin_engine() -> DigitalTwinEngine:
    global _digital_twin_engine
    if _digital_twin_engine is None:
        _digital_twin_engine = DigitalTwinEngine()
    return _digital_twin_engine
