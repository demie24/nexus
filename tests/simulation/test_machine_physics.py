"""
Unit Tests for Machine Physics & Coupled Dynamics
Verifies thermodynamic equilibrium, bearing degradation, overload, and physical boundaries.
"""

from datetime import datetime, timezone
import numpy as np
import pytest

from services.schemas import OperatingStatus
from services.simulation.config import get_default_factory_spec
from services.simulation.machine import SimulatedMachine


@pytest.fixture
def rng():
    return np.random.default_rng(42)


@pytest.fixture
def sample_machine(rng):
    spec = get_default_factory_spec().get_machine("M03")
    return SimulatedMachine(spec, rng)


def test_nominal_telemetry_generation(sample_machine):
    now = datetime.now(timezone.utc)
    tel = sample_machine.generate_telemetry(now)

    assert tel.machine_id == "M03"
    assert 65.0 < tel.temperature < 85.0
    assert 2.0 < tel.vibration < 4.5
    assert 15.0 < tel.power_kw < 25.0
    assert tel.efficiency > 90.0
    assert tel.quality_indicator == 1.0


def test_load_increase_increases_current_and_power(sample_machine):
    now = datetime.now(timezone.utc)
    sample_machine.sensor_noise_enabled = False

    # Low load
    sample_machine.set_load(0.5)
    sample_machine.step_physics(1.0)
    t_low = sample_machine.generate_telemetry(now)

    # High load
    sample_machine.set_load(1.2)
    sample_machine.step_physics(1.0)
    t_high = sample_machine.generate_telemetry(now)

    assert t_high.current > t_low.current
    assert t_high.power_kw > t_low.power_kw


def test_bearing_degradation_impact(sample_machine):
    now = datetime.now(timezone.utc)
    sample_machine.sensor_noise_enabled = False

    # Baseline
    t_base = sample_machine.generate_telemetry(now)
    h_base = sample_machine.health_score

    # Wear bearing to 80%
    sample_machine.bearing_degradation = 0.8
    sample_machine.step_physics(10.0)
    t_degraded = sample_machine.generate_telemetry(now)

    # Vibration must jump significantly
    assert t_degraded.vibration > t_base.vibration + 4.0
    # Health score must drop
    assert sample_machine.health_score < h_base - 40.0
    # Failure probability must rise
    assert sample_machine.failure_probability > 0.40
    # Efficiency must drop
    assert t_degraded.efficiency < t_base.efficiency


def test_cooling_degradation_causes_thermal_rise(sample_machine):
    sample_machine.sensor_noise_enabled = False
    sample_machine.cooling_degradation = 0.9

    # Advance thermal physics
    for _ in range(30):
        sample_machine.step_physics(10.0)

    assert sample_machine.internal_temperature > sample_machine.spec.nominal_temp_c + 10.0


def test_idle_and_maintenance_state(sample_machine):
    # Set to zero load
    sample_machine.set_load(0.0)
    assert sample_machine.operating_status == OperatingStatus.IDLE

    # Restore via maintenance
    sample_machine.apply_maintenance()
    assert sample_machine.health_score == 100.0
    assert sample_machine.bearing_degradation == 0.0
    assert sample_machine.cooling_degradation == 0.0
    assert sample_machine.operating_status == OperatingStatus.OPERATING
