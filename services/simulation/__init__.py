"""
NEXUS Simulation Package
Provides Virtual Factory Engine, Clock, Machine Physics, Scenarios, and Transports.
"""

from services.simulation.config import (
    MachineSpec,
    ProductionLineSpec,
    FactorySpec,
    get_default_factory_spec,
)
from services.simulation.clock import SimulationClock
from services.simulation.machine import SimulatedMachine
from services.simulation.scenarios import (
    ScenarioType,
    ScenarioStatus,
    SimulationScenarioInstance,
)
from services.simulation.transports import (
    BaseTelemetryTransport,
    InMemoryTransport,
    MQTTTransport,
    DatabaseTransport,
    CompositeTransport,
)
from services.simulation.engine import (
    VirtualFactorySimulator,
    get_simulator,
)

from services.simulation.snapshot import (
    DigitalTwinSnapshotManager,
    get_snapshot_manager,
)
from services.simulation.cascade import MultiMachineCascadeAnalyzer
from services.simulation.metrics import (
    validate_metrics_sanity,
    build_baseline_comparison,
    SimulationSanityError,
)
from services.simulation.counterfactual import (
    WhatIfSimulationEngine,
    get_what_if_engine,
    ENGINE_VERSION,
    PHYSICS_MODEL_VERSION,
    SCENARIO_VERSION,
)
from services.simulation.comparison import (
    ScenarioComparisonEngine,
    get_comparison_engine,
)

__all__ = [
    "MachineSpec",
    "ProductionLineSpec",
    "FactorySpec",
    "get_default_factory_spec",
    "SimulationClock",
    "SimulatedMachine",
    "ScenarioType",
    "ScenarioStatus",
    "SimulationScenarioInstance",
    "BaseTelemetryTransport",
    "InMemoryTransport",
    "MQTTTransport",
    "DatabaseTransport",
    "CompositeTransport",
    "VirtualFactorySimulator",
    "get_simulator",
    "DigitalTwinSnapshotManager",
    "get_snapshot_manager",
    "MultiMachineCascadeAnalyzer",
    "validate_metrics_sanity",
    "build_baseline_comparison",
    "SimulationSanityError",
    "WhatIfSimulationEngine",
    "get_what_if_engine",
    "ENGINE_VERSION",
    "PHYSICS_MODEL_VERSION",
    "SCENARIO_VERSION",
    "ScenarioComparisonEngine",
    "get_comparison_engine",
]

