"""
NEXUS Multi-Machine Cascade & Production Line Impact Analyzer
Evaluates downstream and upstream propagation of machine interventions across factory lines.
"""

from typing import Dict, List, Any, Optional
from services.simulation.config import get_default_factory_spec, FactorySpec


class MultiMachineCascadeAnalyzer:
    """
    Analyzes inter-machine dependencies and sequential production line cascades.
    Factory Topology:
      Line 01 (Sequential Subtractive Machining):
        M01 (CNC Milling) -> M02 (Industrial Lathe) -> M03 (Precision Grinder)
      Line 02 (Sequential Fabrication & Assembly):
        M04 (Robotic Welder) -> M05 (Hydraulic Press) -> M06 (Automated Packaging)
    """

    def __init__(self, factory_spec: Optional[FactorySpec] = None):
        self.spec = factory_spec or get_default_factory_spec()

    def get_line_for_machine(self, machine_id: str) -> Optional[str]:
        m = self.spec.get_machine(machine_id)
        return m.line_id if m else None

    def get_line_machines(self, line_id: str) -> List[str]:
        line = self.spec.lines.get(line_id)
        if not line:
            return []
        return [m.machine_id for m in line.machines]

    def evaluate_cascade(
        self,
        target_machine_id: str,
        simulated_output_rate: float,
        nominal_output_rate: float,
        is_shutdown: bool,
        all_machine_states: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Computes line-level and factory-level cascade effects resulting from target machine intervention.
        """
        line_id = self.get_line_for_machine(target_machine_id)
        if not line_id:
            return {
                "affected_cascade_machines": [],
                "line_id": "UNKNOWN",
                "cascade_summary": "Machine does not belong to a recognized line."
            }

        line_machines = self.get_line_machines(line_id)
        other_line_machines = [mid for mid in line_machines if mid != target_machine_id]

        # Calculate nominal and simulated throughput for all lines
        all_specs = {m.machine_id: m for m in self.spec.all_machines()}

        # Nominal factory output rate per hour (sum of finished line bottlenecks)
        # Line 1 finished rate is governed by M03; Line 2 by M06
        line1_nom = all_specs["M03"].nominal_output_rate if "M03" in all_specs else 65.0
        line2_nom = all_specs["M06"].nominal_output_rate if "M06" in all_specs else 70.0
        total_nominal_factory_rate = line1_nom + line2_nom

        affected_machines = []
        machine_cascade_details = {}

        if is_shutdown or simulated_output_rate <= 0.001:
            # Sequential line stoppage: When a line machine stops, the line cannot produce finished goods
            affected_machines = other_line_machines
            for mid in other_line_machines:
                machine_cascade_details[mid] = {
                    "status_override": "LINE_HALTED_BUFFER_HOLD",
                    "effective_output_rate": 0.0,
                    "utilization_pct": 0.0,
                    "reason": f"Bottleneck machine {target_machine_id} is halted."
                }
            line_simulated_rate = 0.0
            line_loss_pct = 100.0
        else:
            # Throttle or modulation: Bottleneck throughput is constrained by min rate
            fractional_capacity = max(0.0, min(1.5, simulated_output_rate / max(1.0, nominal_output_rate)))
            if fractional_capacity < 0.99:
                affected_machines = other_line_machines
                for mid in other_line_machines:
                    cur_nom = all_specs[mid].nominal_output_rate if mid in all_specs else 80.0
                    throttled_rate = cur_nom * fractional_capacity
                    machine_cascade_details[mid] = {
                        "status_override": "SYNCHRONIZED_THROTTLED",
                        "effective_output_rate": round(throttled_rate, 2),
                        "utilization_pct": round(fractional_capacity * 100.0, 1),
                        "reason": f"Line throughput paced by {target_machine_id} ({fractional_capacity*100:.0f}% load)."
                    }
                line_nom = all_specs[line_machines[-1]].nominal_output_rate
                line_simulated_rate = line_nom * fractional_capacity
                line_loss_pct = round((1.0 - fractional_capacity) * 100.0, 2)
            else:
                line_nom = all_specs[line_machines[-1]].nominal_output_rate
                line_simulated_rate = line_nom
                line_loss_pct = 0.0

        # Compute whole factory impact
        if line_id == "LINE_01":
            factory_sim_rate = line_simulated_rate + line2_nom
        else:
            factory_sim_rate = line1_nom + line_simulated_rate

        factory_loss_pct = round(
            max(0.0, (total_nominal_factory_rate - factory_sim_rate) / total_nominal_factory_rate * 100.0),
            2
        )

        return {
            "target_machine_id": target_machine_id,
            "line_id": line_id,
            "affected_cascade_machines": affected_machines,
            "line_nominal_rate": line1_nom if line_id == "LINE_01" else line2_nom,
            "line_simulated_rate": round(line_simulated_rate, 2),
            "line_throughput_loss_pct": line_loss_pct,
            "total_factory_nominal_rate": total_nominal_factory_rate,
            "total_factory_simulated_rate": round(factory_sim_rate, 2),
            "factory_throughput_loss_pct": factory_loss_pct,
            "cascade_details": machine_cascade_details
        }
