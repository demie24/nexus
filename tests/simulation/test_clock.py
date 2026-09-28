"""
Unit Tests for Simulation Clock
Tests time acceleration, stepping, and synchronization.
"""

from datetime import datetime, timezone
from services.simulation.clock import SimulationClock


def test_clock_stepping():
    t0 = datetime(2026, 9, 29, 8, 0, 0, tzinfo=timezone.utc)
    clock = SimulationClock(start_time=t0, time_scale=1.0)

    t1 = clock.step(30.0)
    assert clock.elapsed_sim_seconds == 30.0
    assert (t1 - t0).total_seconds() == 30.0


def test_clock_time_dilation():
    clock = SimulationClock(time_scale=10.0)
    sim_dt = clock.tick_wall_clock(0.5)

    # 0.5 wall seconds * 10x scale = 5.0 simulated seconds
    assert sim_dt == 5.0
    assert clock.elapsed_sim_seconds == 5.0


def test_clock_reset():
    clock = SimulationClock()
    clock.step(100.0)
    assert clock.elapsed_sim_seconds == 100.0

    clock.reset()
    assert clock.elapsed_sim_seconds == 0.0
