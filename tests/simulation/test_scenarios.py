"""
Unit Tests for Simulation Scenarios & Failure Progression
Tests scenario activation, escalation, recovery, and false-positive sensor anomalies.
"""

from services.simulation.engine import VirtualFactorySimulator
from services.simulation.scenarios import ScenarioType, ScenarioStatus


def test_scenario_bearing_degradation_progression():
    sim = VirtualFactorySimulator(seed=42)
    scen = sim.trigger_scenario(
        scenario_type=ScenarioType.BEARING_DEGRADATION,
        machine_id="M03",
        severity=0.85,
        duration_sim_seconds=100.0
    )
    assert scen.status == ScenarioStatus.ACTIVE

    # Advance 80 seconds
    for _ in range(8):
        sim.step(10.0)

    m = sim.machines["M03"]
    assert m.bearing_degradation > 0.4
    assert m.health_score < 80.0
    assert m.failure_probability > 0.15

    # Recover scenario
    success = sim.recover_scenario(scen.scenario_id)
    assert success is True
    assert m.health_score == 100.0
    assert m.bearing_degradation == 0.0


def test_scenario_cooling_degradation():
    sim = VirtualFactorySimulator(seed=42)
    scen = sim.trigger_scenario(
        scenario_type=ScenarioType.COOLING_DEGRADATION,
        machine_id="M01",
        severity=0.90,
        duration_sim_seconds=100.0
    )
    for _ in range(10):
        sim.step(10.0)

    m = sim.machines["M01"]
    assert m.cooling_degradation > 0.5
    assert m.internal_temperature > m.spec.nominal_temp_c


def test_scenario_overload():
    sim = VirtualFactorySimulator(seed=42)
    scen = sim.trigger_scenario(
        scenario_type=ScenarioType.OVERLOAD,
        machine_id="M05",
        severity=0.80,
        duration_sim_seconds=50.0
    )
    m = sim.machines["M05"]
    assert m.current_load > 1.25

    # Run beyond duration to auto-complete
    for _ in range(6):
        sim.step(10.0)

    # After duration, load returns to rated
    assert m.current_load == m.spec.rated_load


def test_scenario_sensor_anomaly():
    sim = VirtualFactorySimulator(seed=42)
    scen = sim.trigger_scenario(
        scenario_type=ScenarioType.SENSOR_ANOMALY,
        machine_id="M02",
        severity=0.90,
        parameters={"sensor": "vibration", "bias": 7.5}
    )
    tel = sim.step(1.0)[1]  # M02 is index 1

    # Telemetry should report spiked vibration, but machine physical health remains 100%
    assert tel.vibration > 8.0
    assert sim.machines["M02"].bearing_degradation == 0.0
    assert sim.machines["M02"].health_score == 100.0
    # Data quality score should reflect anomaly
    assert tel.quality_indicator < 1.0


def test_scenario_stop():
    sim = VirtualFactorySimulator(seed=42)
    scen = sim.trigger_scenario(
        scenario_type=ScenarioType.BEARING_DEGRADATION,
        machine_id="M04",
        severity=0.7
    )
    assert scen.scenario_id in sim.active_scenarios

    sim.stop_scenario(scen.scenario_id)
    assert scen.scenario_id not in sim.active_scenarios
