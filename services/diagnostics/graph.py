"""
NEXUS Diagnostics Dependency Graph
Constructs and traverses a directed acyclic graph (DAG) representing causal mechanisms,
intermediate physical phenomena, and observable sensor telemetry signals.
"""

from typing import Dict, List, Optional, Tuple, Any
import networkx as nx

from services.schemas import RootCauseType, SignalDirection


class DiagnosticDependencyGraph:
    """
    Dependency graph mapping root causes through physical mechanisms to observable signals.
    """

    def __init__(self):
        self.graph = nx.DiGraph()
        self._build_graph()

    def _build_graph(self) -> None:
        """Constructs nodes and directed causal edges."""
        # 1. Root Cause Nodes
        self.graph.add_node(RootCauseType.BEARING_DEGRADATION.value, type="cause", label="Bearing Degradation")
        self.graph.add_node(RootCauseType.COOLING_DEGRADATION.value, type="cause", label="Cooling Degradation")
        self.graph.add_node(RootCauseType.OVERLOAD.value, type="cause", label="Operational Overload")
        self.graph.add_node(RootCauseType.MOTOR_INEFFICIENCY.value, type="cause", label="Motor Inefficiency")
        self.graph.add_node(RootCauseType.SENSOR_ANOMALY.value, type="cause", label="Sensor Anomaly")

        # 2. Intermediate Physical Phenomenon Nodes
        self.graph.add_node("MechanicalFriction", type="mechanism", label="Elevated Mechanical Friction")
        self.graph.add_node("ThermalImpairment", type="mechanism", label="Impaired Thermal Dissipation")
        self.graph.add_node("ExcessDemand", type="mechanism", label="Excessive Load & Rotor Demand")
        self.graph.add_node("ElectromechanicalLoss", type="mechanism", label="Electromechanical Loss")
        self.graph.add_node("SensorTransducerFault", type="mechanism", label="Isolated Transducer Glitch")

        # 3. Observable Signal Nodes
        observables = [
            "vibration",
            "temperature",
            "current",
            "power_kw",
            "load",
            "efficiency",
            "health_score",
            "rul_hours"
        ]
        for obs in observables:
            self.graph.add_node(obs, type="observable", label=obs)

        # 4. Edges: Causes -> Intermediate Mechanisms
        self.graph.add_edge(
            RootCauseType.BEARING_DEGRADATION.value,
            "MechanicalFriction",
            weight=0.95,
            description="Bearing raceway damage and roller micro-welding generate severe mechanical friction"
        )
        self.graph.add_edge(
            RootCauseType.COOLING_DEGRADATION.value,
            "ThermalImpairment",
            weight=0.90,
            description="Restricted coolant flow or fouled heat sinks inhibit normal convective cooling"
        )
        self.graph.add_edge(
            RootCauseType.OVERLOAD.value,
            "ExcessDemand",
            weight=0.95,
            description="Machine duty cycle or workpiece feed exceeds rated mechanical envelope"
        )
        self.graph.add_edge(
            RootCauseType.MOTOR_INEFFICIENCY.value,
            "ElectromechanicalLoss",
            weight=0.85,
            description="Stator winding deterioration and harmonic losses reduce conversion efficiency"
        )
        self.graph.add_edge(
            RootCauseType.SENSOR_ANOMALY.value,
            "SensorTransducerFault",
            weight=0.90,
            description="Transducer circuit artifact, EMI noise, or loose connection creates artificial reading"
        )

        # 5. Edges: Intermediate Mechanisms -> Observable Signals
        # MechanicalFriction -> Signals
        self.graph.add_edge(
            "MechanicalFriction", "vibration",
            weight=0.95, direction=SignalDirection.INCREASING,
            description="Bearing surface defect impacts excite resonant structural vibration"
        )
        self.graph.add_edge(
            "MechanicalFriction", "efficiency",
            weight=0.80, direction=SignalDirection.DECREASING,
            description="Frictional drag dissipates mechanical energy, decreasing overall machine efficiency"
        )
        self.graph.add_edge(
            "MechanicalFriction", "temperature",
            weight=0.65, direction=SignalDirection.INCREASING,
            description="Frictional work converts to localized heat, gradually raising bearing temperature"
        )
        self.graph.add_edge(
            "MechanicalFriction", "current",
            weight=0.50, direction=SignalDirection.INCREASING,
            description="Rotor drag forces motor drive to supply additional torque current"
        )
        self.graph.add_edge(
            "MechanicalFriction", "health_score",
            weight=0.90, direction=SignalDirection.DECREASING,
            description="Progressive mechanical damage reduces digital twin health index"
        )

        # ThermalImpairment -> Signals
        self.graph.add_edge(
            "ThermalImpairment", "temperature",
            weight=0.95, direction=SignalDirection.INCREASING,
            description="Heat accumulation causes continuous exponential rise in core machine temperature"
        )
        self.graph.add_edge(
            "ThermalImpairment", "efficiency",
            weight=0.75, direction=SignalDirection.DECREASING,
            description="Higher temperatures increase stator resistance and viscous losses, degrading efficiency"
        )
        self.graph.add_edge(
            "ThermalImpairment", "health_score",
            weight=0.80, direction=SignalDirection.DECREASING,
            description="Thermal stress accelerates insulation degradation, reducing asset health"
        )

        # ExcessDemand -> Signals
        self.graph.add_edge(
            "ExcessDemand", "load",
            weight=0.98, direction=SignalDirection.INCREASING,
            description="Operational command or mechanical resistance drives measured load above nominal"
        )
        self.graph.add_edge(
            "ExcessDemand", "current",
            weight=0.95, direction=SignalDirection.INCREASING,
            description="Direct proportional increase in armature current to meet high load torque"
        )
        self.graph.add_edge(
            "ExcessDemand", "power_kw",
            weight=0.95, direction=SignalDirection.INCREASING,
            description="Total electrical real power drawn increases proportionally with current"
        )
        self.graph.add_edge(
            "ExcessDemand", "temperature",
            weight=0.70, direction=SignalDirection.INCREASING,
            description="I^2 * R ohmic losses and core heating escalate internal machine temperature"
        )
        self.graph.add_edge(
            "ExcessDemand", "efficiency",
            weight=0.60, direction=SignalDirection.DECREASING,
            description="Operating above rated optimal point increases non-linear losses, lowering efficiency"
        )

        # ElectromechanicalLoss -> Signals
        self.graph.add_edge(
            "ElectromechanicalLoss", "efficiency",
            weight=0.95, direction=SignalDirection.DECREASING,
            description="Severe drop in power conversion efficiency without proportional load increase"
        )
        self.graph.add_edge(
            "ElectromechanicalLoss", "power_kw",
            weight=0.80, direction=SignalDirection.INCREASING,
            description="Excessive power consumption required per unit of productive output"
        )
        self.graph.add_edge(
            "ElectromechanicalLoss", "current",
            weight=0.75, direction=SignalDirection.INCREASING,
            description="Higher reactive or loss current drawn by degraded motor windings"
        )
        self.graph.add_edge(
            "ElectromechanicalLoss", "temperature",
            weight=0.60, direction=SignalDirection.INCREASING,
            description="Stator and rotor resistive dissipation causes gradual thermal buildup"
        )

        # SensorTransducerFault -> Signals
        self.graph.add_edge(
            "SensorTransducerFault", "vibration",
            weight=0.85, direction=SignalDirection.SPIKE,
            description="Transducer artifact presents as isolated spike or baseline jump on vibration"
        )
        self.graph.add_edge(
            "SensorTransducerFault", "temperature",
            weight=0.85, direction=SignalDirection.SPIKE,
            description="Thermocouple disconnect or ADC glitch produces isolated temperature spike"
        )

    def get_reachable_observables(self, cause: RootCauseType) -> Dict[str, Dict[str, Any]]:
        """
        Traverses downstream paths from a cause node to find all observable signals,
        their expected directions, and coupling weights.
        """
        cause_val = cause.value if isinstance(cause, RootCauseType) else cause
        if cause_val not in self.graph:
            return {}

        results = {}
        # Find paths of length 2 (cause -> mechanism -> observable)
        for succ in self.graph.successors(cause_val):
            edge_to_mech = self.graph.get_edge_data(cause_val, succ)
            w1 = edge_to_mech.get("weight", 1.0)
            for obs in self.graph.successors(succ):
                node_data = self.graph.nodes[obs]
                if node_data.get("type") == "observable":
                    edge_to_obs = self.graph.get_edge_data(succ, obs)
                    direction = edge_to_obs.get("direction", SignalDirection.INCREASING)
                    w2 = edge_to_obs.get("weight", 1.0)
                    combined_weight = w1 * w2
                    results[obs] = {
                        "direction": direction,
                        "weight": combined_weight,
                        "mechanism": succ,
                        "description": edge_to_obs.get("description", "")
                    }
        return results

    def explain_path(self, cause: RootCauseType, signal: str) -> List[str]:
        """
        Returns human-readable causal pathway explanations from a cause to an observed signal.
        """
        cause_val = cause.value if isinstance(cause, RootCauseType) else cause
        if cause_val not in self.graph or signal not in self.graph:
            return []

        explanations = []
        try:
            paths = list(nx.all_simple_paths(self.graph, source=cause_val, target=signal))
            for path in paths:
                steps = []
                for i in range(len(path) - 1):
                    src, dst = path[i], path[i + 1]
                    edge = self.graph.get_edge_data(src, dst)
                    desc = edge.get("description", f"{src} affects {dst}")
                    steps.append(desc)
                explanations.append(" -> ".join(steps))
        except nx.NetworkXNoPath:
            pass
        return explanations

    def evaluate_graph_alignment(
        self,
        cause: RootCauseType,
        observed_deviations: Dict[str, Tuple[SignalDirection, float]]
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Evaluates how well observed signal deviations align with the dependency graph topology.
        Returns:
            alignment_score: float in [0.0, 1.0]
            matched_edges: list of matched observable explanations
        """
        expected = self.get_reachable_observables(cause)
        if not expected:
            return 0.0, []

        total_weight = sum(info["weight"] for info in expected.values())
        matched_weight = 0.0
        matches = []

        for sig, info in expected.items():
            if sig in observed_deviations:
                obs_dir, obs_strength = observed_deviations[sig]
                expected_dir = info["direction"]

                # Direction compatibility check
                if obs_dir == expected_dir or (expected_dir == SignalDirection.SPIKE and obs_dir in [SignalDirection.INCREASING, SignalDirection.SPIKE]):
                    # Match bonus scaled by deviation strength and graph path weight
                    weight = info["weight"]
                    matched_weight += weight * min(1.0, obs_strength)
                    matches.append({
                        "signal": sig,
                        "expected_direction": expected_dir.value,
                        "observed_direction": obs_dir.value,
                        "mechanism": info["mechanism"],
                        "description": info["description"],
                        "weight": weight
                    })

        alignment_score = float(matched_weight / total_weight) if total_weight > 0 else 0.0
        return min(1.0, max(0.0, alignment_score)), matches


# Singleton instance
_graph_instance: Optional[DiagnosticDependencyGraph] = None


def get_dependency_graph() -> DiagnosticDependencyGraph:
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = DiagnosticDependencyGraph()
    return _graph_instance
