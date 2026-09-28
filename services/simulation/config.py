"""
Virtual Factory Configuration & Machine Specifications
Provides configuration-driven factory topologies, nominal parameters, and sensor noise baselines.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class MachineSpec(BaseModel):
    machine_id: str
    name: str
    machine_type: str
    line_id: str
    rated_load: float = 1.0

    # Nominal operating ratings
    nominal_power_kw: float
    nominal_rpm: float
    nominal_current_a: float
    nominal_voltage_v: float = 400.0
    nominal_temp_c: float
    nominal_vib_mms: float
    nominal_pressure_bar: float
    nominal_output_rate: float  # units per hour

    # Maximum safety thresholds
    max_temp_c: float = 95.0
    max_vib_mms: float = 8.0
    max_current_a: float = 60.0
    max_pressure_bar: float = 200.0

    # Configurable sensor noise standard deviations
    temp_noise_std: float = 0.35
    vib_noise_std: float = 0.06
    current_noise_std: float = 0.25
    voltage_noise_std: float = 1.2
    rpm_noise_std: float = 4.0
    pressure_noise_std: float = 0.08
    power_noise_std: float = 0.20


class ProductionLineSpec(BaseModel):
    line_id: str
    name: str
    machines: List[MachineSpec]


class FactorySpec(BaseModel):
    factory_id: str = "FACTORY_01"
    name: str = "NEXUS Virtual Industrial Plant"
    lines: Dict[str, ProductionLineSpec] = Field(default_factory=dict)

    def get_machine(self, machine_id: str) -> Optional[MachineSpec]:
        for line in self.lines.values():
            for m in line.machines:
                if m.machine_id == machine_id:
                    return m
        return None

    def all_machines(self) -> List[MachineSpec]:
        machines = []
        for line in self.lines.values():
            machines.extend(line.machines)
        return machines


def get_default_factory_spec() -> FactorySpec:
    """
    Constructs the standard Virtual Factory specification containing 2 lines and 6 machines (M01-M06).
    """
    # Production Line 01
    line1_machines = [
        MachineSpec(
            machine_id="M01",
            name="CNC Milling Center 1",
            machine_type="CNC Milling",
            line_id="LINE_01",
            nominal_power_kw=15.0,
            nominal_rpm=1500.0,
            nominal_current_a=21.5,
            nominal_temp_c=68.0,
            nominal_vib_mms=2.4,
            nominal_pressure_bar=3.0,
            nominal_output_rate=80.0,
            max_temp_c=90.0,
            max_vib_mms=7.5
        ),
        MachineSpec(
            machine_id="M02",
            name="Precision Lathe Unit 1",
            machine_type="Industrial Lathe",
            line_id="LINE_01",
            nominal_power_kw=12.0,
            nominal_rpm=1800.0,
            nominal_current_a=17.2,
            nominal_temp_c=62.0,
            nominal_vib_mms=1.9,
            nominal_pressure_bar=2.5,
            nominal_output_rate=95.0,
            max_temp_c=88.0,
            max_vib_mms=7.0
        ),
        MachineSpec(
            machine_id="M03",
            name="Precision Surface Grinder",
            machine_type="Precision Grinder",
            line_id="LINE_01",
            nominal_power_kw=18.5,
            nominal_rpm=3000.0,
            nominal_current_a=26.5,
            nominal_temp_c=74.0,
            nominal_vib_mms=3.1,
            nominal_pressure_bar=3.5,
            nominal_output_rate=65.0,
            max_temp_c=95.0,
            max_vib_mms=8.5
        ),
    ]

    # Production Line 02
    line2_machines = [
        MachineSpec(
            machine_id="M04",
            name="Robotic Arc Welder",
            machine_type="Robotic Welder",
            line_id="LINE_02",
            nominal_power_kw=24.0,
            nominal_rpm=0.0,  # Stationary welding arm
            nominal_current_a=34.5,
            nominal_temp_c=78.0,
            nominal_vib_mms=1.2,
            nominal_pressure_bar=6.0,
            nominal_output_rate=110.0,
            max_temp_c=98.0,
            max_vib_mms=6.0
        ),
        MachineSpec(
            machine_id="M05",
            name="Hydraulic Stamping Press",
            machine_type="Hydraulic Press",
            line_id="LINE_02",
            nominal_power_kw=38.0,
            nominal_rpm=750.0,
            nominal_current_a=52.0,
            nominal_temp_c=71.0,
            nominal_vib_mms=4.2,
            nominal_pressure_bar=150.0,
            nominal_output_rate=50.0,
            max_temp_c=92.0,
            max_vib_mms=9.0
        ),
        MachineSpec(
            machine_id="M06",
            name="High-Speed Packaging Unit",
            machine_type="Automated Packaging",
            line_id="LINE_02",
            nominal_power_kw=8.5,
            nominal_rpm=1200.0,
            nominal_current_a=12.0,
            nominal_temp_c=54.0,
            nominal_vib_mms=1.7,
            nominal_pressure_bar=2.0,
            nominal_output_rate=160.0,
            max_temp_c=85.0,
            max_vib_mms=6.5
        ),
    ]

    factory = FactorySpec(
        factory_id="FACTORY_01",
        name="NEXUS Virtual Industrial Plant",
        lines={
            "LINE_01": ProductionLineSpec(
                line_id="LINE_01",
                name="Primary Machining Line",
                machines=line1_machines
            ),
            "LINE_02": ProductionLineSpec(
                line_id="LINE_02",
                name="Assembly & Packaging Line",
                machines=line2_machines
            ),
        }
    )
    return factory
