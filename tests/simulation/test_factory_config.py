"""
Unit Tests for Virtual Factory Configuration
Verifies topology, machine specifications, and nominal parameters.
"""

from services.simulation.config import get_default_factory_spec, FactorySpec


def test_default_factory_topology():
    spec = get_default_factory_spec()
    assert spec.factory_id == "FACTORY_01"
    assert len(spec.lines) == 2
    assert "LINE_01" in spec.lines
    assert "LINE_02" in spec.lines

    # 3 machines on Line 1, 3 machines on Line 2
    assert len(spec.lines["LINE_01"].machines) == 3
    assert len(spec.lines["LINE_02"].machines) == 3

    all_machines = spec.all_machines()
    assert len(all_machines) == 6
    machine_ids = [m.machine_id for m in all_machines]
    assert machine_ids == ["M01", "M02", "M03", "M04", "M05", "M06"]


def test_machine_lookup():
    spec = get_default_factory_spec()
    m03 = spec.get_machine("M03")
    assert m03 is not None
    assert m03.machine_type == "Precision Grinder"
    assert m03.nominal_rpm == 3000.0
    assert m03.nominal_power_kw == 18.5

    # Nonexistent machine
    assert spec.get_machine("M99") is None
