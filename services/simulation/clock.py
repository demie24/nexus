"""
Simulation Clock & Virtual Time Acceleration Module
Enables time dilation (e.g. 1 real second = 10 simulated seconds) and manual stepped ticks.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional


class SimulationClock:
    def __init__(
        self,
        start_time: Optional[datetime] = None,
        time_scale: float = 1.0
    ):
        """
        :param start_time: Starting virtual datetime (defaults to current UTC).
        :param time_scale: Ratio of simulated seconds to real wall-clock seconds.
        """
        self.start_time = start_time or datetime.now(timezone.utc)
        self.time_scale = max(0.01, float(time_scale))
        self.elapsed_sim_seconds: float = 0.0

    @property
    def current_time(self) -> datetime:
        """Returns the current simulated datetime."""
        return self.start_time + timedelta(seconds=self.elapsed_sim_seconds)

    def tick_wall_clock(self, wall_dt_seconds: float) -> float:
        """
        Advances the virtual clock based on elapsed wall-clock time and time_scale.
        Returns simulated seconds advanced.
        """
        sim_dt = wall_dt_seconds * self.time_scale
        self.elapsed_sim_seconds += sim_dt
        return sim_dt

    def step(self, sim_dt_seconds: float) -> datetime:
        """
        Directly advances the virtual clock by a specific number of simulated seconds.
        Useful for deterministic testing and rapid batch simulations.
        """
        self.elapsed_sim_seconds += max(0.0, sim_dt_seconds)
        return self.current_time

    def set_time_scale(self, time_scale: float) -> None:
        """Dynamically adjusts the virtual time acceleration multiplier."""
        self.time_scale = max(0.01, float(time_scale))

    def reset(self, start_time: Optional[datetime] = None) -> None:
        """Resets the simulation clock back to origin."""
        if start_time:
            self.start_time = start_time
        self.elapsed_sim_seconds = 0.0
