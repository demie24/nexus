"""
Telemetry Validation & Physical Plausibility Engine
Validates machine identity, timestamp boundaries, and physical plausible ranges.
Distinguishes between physically impossible readings (rejected) and genuine operational anomalies (accepted).
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from database.models.models import MachineModel
from services.schemas import TelemetryCreate


class TelemetryValidationError(ValueError):
    def __init__(self, field: str, value: any, reason: str):
        super().__init__(f"Validation failure on '{field}' ({value}): {reason}")
        self.field = field
        self.value = value
        self.reason = reason


def validate_telemetry_bounds(payload: TelemetryCreate) -> None:
    """
    Validates that physical readings conform to physical thermodynamic and mechanical laws.
    High readings (anomalies) are permitted, but impossible values are rejected.
    """
    # 1. Temperature: Absolute lower bound is -50°C; upper safety ceiling is 400°C
    if payload.temperature < -50.0:
        raise TelemetryValidationError("temperature", payload.temperature, "Temperature cannot be below -50°C (physically impossible)")
    if payload.temperature > 400.0:
        raise TelemetryValidationError("temperature", payload.temperature, "Temperature exceeds physical sensor ceiling (400°C)")

    # 2. Vibration: Velocity must be non-negative
    if payload.vibration < 0.0:
        raise TelemetryValidationError("vibration", payload.vibration, "Vibration velocity cannot be negative")
    if payload.vibration > 150.0:
        raise TelemetryValidationError("vibration", payload.vibration, "Vibration exceeds catastrophic physical limits (150 mm/s)")

    # 3. Pressure: Must be non-negative
    if payload.pressure < 0.0:
        raise TelemetryValidationError("pressure", payload.pressure, "Pressure cannot be negative")

    # 4. Current & Voltage: Electrical readings cannot be negative
    if payload.current < 0.0:
        raise TelemetryValidationError("current", payload.current, "Electric current cannot be negative")
    if payload.voltage < 0.0:
        raise TelemetryValidationError("voltage", payload.voltage, "Voltage cannot be negative")

    # 5. RPM: Mechanical rotation speed cannot be negative
    if payload.rpm < 0.0:
        raise TelemetryValidationError("rpm", payload.rpm, "RPM cannot be negative")

    # 6. Active Power: Cannot be negative
    if payload.power_kw < 0.0:
        raise TelemetryValidationError("power_kw", payload.power_kw, "Power consumption cannot be negative")

    # 7. Operating Load: Must be non-negative
    if payload.load < 0.0:
        raise TelemetryValidationError("load", payload.load, "Load factor cannot be negative")
    if payload.load > 5.0:
        raise TelemetryValidationError("load", payload.load, "Load factor exceeds physical overload boundary (5.0)")

    # 8. Efficiency: Physical percentage bounded strictly between 0% and 100%
    if payload.efficiency < 0.0 or payload.efficiency > 100.0:
        raise TelemetryValidationError("efficiency", payload.efficiency, "Efficiency percentage must be strictly within [0.0, 100.0]")

    # 9. Output rate: Production units cannot be negative
    if payload.output_rate < 0.0:
        raise TelemetryValidationError("output_rate", payload.output_rate, "Output rate cannot be negative")

    # 10. Quality indicator: Must be bounded between 0.0 and 1.0
    if payload.quality_indicator < 0.0 or payload.quality_indicator > 1.0:
        raise TelemetryValidationError("quality_indicator", payload.quality_indicator, "Quality indicator must be within [0.0, 1.0]")


def validate_timestamp(timestamp: datetime, max_future_seconds: float = 3600.0, max_past_days: float = 30.0) -> None:
    """
    Validates that telemetry timestamp is neither absurdly in the future nor expired beyond retention.
    """
    now = datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    if timestamp > now + timedelta(seconds=max_future_seconds):
        raise TelemetryValidationError("timestamp", timestamp.isoformat(), "Timestamp is too far in the future (> 1 hour ahead)")

    if timestamp < now - timedelta(days=max_past_days):
        raise TelemetryValidationError("timestamp", timestamp.isoformat(), f"Timestamp is older than allowed retention window ({max_past_days} days)")


def validate_machine_exists(machine_id: str, db: Session) -> MachineModel:
    """
    Validates that target machine is registered in the industrial registry.
    """
    machine = db.query(MachineModel).filter_by(id=machine_id).first()
    if not machine:
        raise TelemetryValidationError("machine_id", machine_id, f"Machine '{machine_id}' is not registered in registry")
    return machine
