"""
NEXUS Virtual Factory Simulation Engine
Orchestrates simulated machines, scenarios, simulation clock, and telemetry transports.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional, Any
import numpy as np

from services.schemas import TelemetryCreate
from services.simulation.config import FactorySpec, get_default_factory_spec
from services.simulation.clock import SimulationClock
from services.simulation.machine import SimulatedMachine
from services.simulation.scenarios import (
    SimulationScenarioInstance,
    ScenarioType,
    ScenarioStatus,
)
from services.simulation.transports import (
    CompositeTransport,
    InMemoryTransport,
    BaseTelemetryTransport,
)

logger = logging.getLogger("nexus.simulation.engine")


class VirtualFactorySimulator:
    def __init__(
        self,
        factory_spec: Optional[FactorySpec] = None,
        seed: Optional[int] = 42,
        time_scale: float = 1.0,
        transports: Optional[List[BaseTelemetryTransport]] = None
    ):
        self.spec = factory_spec or get_default_factory_spec()
        self.seed = seed
        self.rng = np.random.default_rng(seed)

        self.clock = SimulationClock(
            start_time=datetime.now(timezone.utc),
            time_scale=time_scale
        )

        # Initialize simulated machines
        self.machines: Dict[str, SimulatedMachine] = {}
        for m_spec in self.spec.all_machines():
            self.machines[m_spec.machine_id] = SimulatedMachine(m_spec, self.rng)

        # Scenarios tracking
        self.active_scenarios: Dict[str, SimulationScenarioInstance] = {}

        # Transports
        self.in_memory_transport = InMemoryTransport()
        all_transports = [self.in_memory_transport]
        if transports:
            all_transports.extend(transports)
        self.transport = CompositeTransport(all_transports)

        # Background runner task
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.total_ticks: int = 0
        self.total_telemetries_generated: int = 0

    def add_transport(self, transport: BaseTelemetryTransport) -> None:
        """Dynamically attach an additional transport (e.g. Database or MQTT)."""
        self.transport.add(transport)

    def set_seed(self, seed: int) -> None:
        """Resets the random number generator with a deterministic seed."""
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        for machine in self.machines.values():
            machine.rng = self.rng

    def trigger_scenario(
        self,
        scenario_type: ScenarioType,
        machine_id: str,
        severity: float = 0.75,
        duration_sim_seconds: float = 300.0,
        parameters: Optional[Dict[str, Any]] = None,
        scenario_id: Optional[str] = None
    ) -> SimulationScenarioInstance:
        """
        Launches an abnormal scenario or fault injection against a target machine.
        """
        machine = self.machines.get(machine_id)
        if not machine:
            raise ValueError(f"Machine '{machine_id}' does not exist in Virtual Factory.")

        instance = SimulationScenarioInstance(
            scenario_type=scenario_type,
            machine_id=machine_id,
            severity=severity,
            duration_sim_seconds=duration_sim_seconds,
            parameters=parameters,
            scenario_id=scenario_id
        )
        instance.start(machine, self.clock.elapsed_sim_seconds)
        self.active_scenarios[instance.scenario_id] = instance
        logger.info(f"Triggered scenario: {instance.scenario_id} ({scenario_type.value}) on {machine_id}")
        return instance

    def recover_scenario(self, scenario_id: str) -> bool:
        """Initiates recovery or maintenance for an active scenario."""
        instance = self.active_scenarios.get(scenario_id)
        if not instance:
            return False
        machine = self.machines.get(instance.machine_id)
        if machine:
            instance.recover(machine)
        return True

    def stop_scenario(self, scenario_id: str) -> bool:
        """Forces immediate cessation of a scenario."""
        instance = self.active_scenarios.get(scenario_id)
        if not instance:
            return False
        machine = self.machines.get(instance.machine_id)
        if machine:
            instance.stop(machine)
        if instance.status == ScenarioStatus.COMPLETED:
            self.active_scenarios.pop(scenario_id, None)
        return True

    def step(self, dt_sim_seconds: float = 1.0) -> List[TelemetryCreate]:
        """
        Advances the virtual factory by dt_sim_seconds and generates a telemetry batch.
        """
        current_time = self.clock.step(dt_sim_seconds)
        self.total_ticks += 1

        # 1. Update active scenarios
        completed_ids = []
        for s_id, scen in self.active_scenarios.items():
            mach = self.machines.get(scen.machine_id)
            if mach:
                scen.update(mach, dt_sim_seconds)
            if scen.status == ScenarioStatus.COMPLETED:
                completed_ids.append(s_id)
        for s_id in completed_ids:
            self.active_scenarios.pop(s_id, None)

        # 2. Step physics and generate telemetry for each machine
        telemetries: List[TelemetryCreate] = []
        for machine in self.machines.values():
            machine.step_physics(dt_sim_seconds)
            tel = machine.generate_telemetry(current_time)
            summary = machine.get_state_summary()

            # Dispatch to transports
            self.transport.send(tel, summary)

            telemetries.append(tel)
            self.total_telemetries_generated += 1

        return telemetries

    async def run_loop(self, tick_interval_seconds: float = 1.0) -> None:
        """
        Asynchronous runner loop for continuous streaming simulation.
        """
        self._running = True
        logger.info(
            f"Simulator loop started: {len(self.machines)} machines, "
            f"tick_interval={tick_interval_seconds}s, time_scale={self.clock.time_scale}x"
        )
        try:
            while self._running:
                # Calculate sim seconds per tick based on clock time_scale
                sim_dt = tick_interval_seconds * self.clock.time_scale
                self.step(sim_dt)
                await asyncio.sleep(tick_interval_seconds)
        except asyncio.CancelledError:
            logger.info("Simulator loop cancelled.")
        finally:
            self._running = False

    def stop_loop(self) -> None:
        """Stops the continuous simulation loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("Simulator loop stopped.")

    def get_status(self) -> Dict[str, Any]:
        """Returns overall simulator health, clock, and metrics."""
        return {
            "factory_id": self.spec.factory_id,
            "factory_name": self.spec.name,
            "is_running": self._running,
            "simulated_time": self.clock.current_time.isoformat(),
            "time_scale": self.clock.time_scale,
            "total_ticks": self.total_ticks,
            "total_telemetries_generated": self.total_telemetries_generated,
            "active_scenarios_count": len(self.active_scenarios),
            "machine_count": len(self.machines),
            "seed": self.seed
        }

    def get_machines_summary(self) -> List[Dict[str, Any]]:
        """Returns internal state snapshot for all machines."""
        return [m.get_state_summary() for m in self.machines.values()]

    def get_latest_telemetry(self, machine_id: str) -> Optional[TelemetryCreate]:
        return self.in_memory_transport.get_latest(machine_id)

    def close(self) -> None:
        self.stop_loop()
        self.transport.close()


# Singleton shared simulator instance for application usage
_default_simulator: Optional[VirtualFactorySimulator] = None


def get_simulator() -> VirtualFactorySimulator:
    global _default_simulator
    if _default_simulator is None:
        _default_simulator = VirtualFactorySimulator()
    return _default_simulator
