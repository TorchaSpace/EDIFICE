import math

from edifice.models import UtilityType
from edifice.service import Project


def test_kpis_consistent():
    p = Project.mock()
    k = p.kpis()
    assert math.isclose(k.total_energy_kwh, k.electricity_kwh + k.gas_kwh)
    assert math.isclose(k.eui_kwh_m2, k.total_energy_kwh / p.building.floor_area_m2)
    assert k.carbon_kg > 0 and k.total_cost > 0


def test_health_in_range():
    h = Project.mock().health()
    assert 0 <= h.total <= 100
    assert h.grade in "ABCDE"
    assert math.isclose(sum(w for _, w in h.components.values()), 1.0)


def test_empty_scenario_changes_nothing():
    s = Project.mock().scenario([])
    assert s.capex == 0 and s.annual_saving == 0
    assert math.isclose(s.target.carbon_kg, s.current.carbon_kg)


def test_scenario_combines_multiplicatively():
    p = Project.mock()
    s = p.scenario(["LED", "CHILLER"])
    by = {o.code: o for o in p.opportunities}
    expected = p.kpis().electricity_kwh * (1 - by['LED'].saving_pct) * (1 - by['CHILLER'].saving_pct)
    assert math.isclose(s.target.electricity_kwh, expected)
    assert s.annual_saving > 0 and s.payback_years > 0


def test_all_opportunities_have_positive_payback():
    for r in Project.mock().opportunity_results():
        assert r.payback_years > 0 and r.capex > 0
