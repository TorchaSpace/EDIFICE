"""Hesap motorunun iç tutarlılığı: bağımsız yoldan yeniden hesaplanabilen değerler ve fiziksel/mantıksal değişmezler."""
import itertools

import pytest

from edifice.models import UtilityType
from edifice.service import Project


@pytest.fixture
def p():
    return Project.mock()


def test_kpis_match_raw_readings(p):
    k = p.kpis()
    elec = sum(r.consumption for r in p.readings if r.year == p.year and r.utility == UtilityType.ELECTRICITY)
    gas = sum(r.consumption for r in p.readings if r.year == p.year and r.utility == UtilityType.GAS)
    assert k.electricity_kwh == pytest.approx(elec) and k.gas_kwh == pytest.approx(gas)
    assert k.total_energy_kwh == pytest.approx(elec + gas)
    assert k.eui_kwh_m2 == pytest.approx((elec + gas) / p.building.floor_area_m2)
    ef = p.assumptions.emission_factor_kg_per_kwh
    assert k.carbon_kg == pytest.approx(elec * ef[UtilityType.ELECTRICITY] + gas * ef[UtilityType.GAS])
    assert sum(p.monthly(p.year, UtilityType.ELECTRICITY)) == pytest.approx(elec)


def test_scenario_is_monotonic_and_consistent(p):
    codes = [o.code for o in p.opportunities]
    base = p.scenario([])
    assert base.annual_saving == 0 and base.target.total_energy_kwh == pytest.approx(base.current.total_energy_kwh)
    prev = 0.0
    for n in range(1, len(codes) + 1):
        s = p.scenario(codes[:n])
        assert s.capex >= 0 and s.annual_saving >= prev          # öneri eklemek tasarrufu azaltmaz
        assert s.target.total_energy_kwh <= s.current.total_energy_kwh
        assert s.target.carbon_kg <= s.current.carbon_kg
        prev = s.annual_saving
    lo, typ, hi = (p.scenario(codes, m).annual_saving for m in ("low", "typ", "high"))
    assert lo <= typ <= hi


def test_finance_identities(p):
    codes = p.applicable_codes()
    f = p.finance(codes)
    assert f.cash_flows[0] == pytest.approx(-f.capex)
    assert f.cumulative[-1] == pytest.approx(sum(f.cash_flows)) and f.total_net == pytest.approx(f.cumulative[-1])
    r = p.assumptions.discount_rate
    npv = sum(cf / (1 + r) ** t for t, cf in enumerate(f.cash_flows))
    assert f.npv == pytest.approx(npv)
    if f.irr is not None:                                          # IRR'de NPV sıfır olmalı
        assert sum(cf / (1 + f.irr) ** t for t, cf in enumerate(f.cash_flows)) == pytest.approx(0, abs=1.0)
    lo, hi = p.finance(codes, "low"), p.finance(codes, "high")
    assert lo.npv <= f.npv <= hi.npv


def test_optimizer_matches_brute_force(p):
    codes = [o.code for o in p.opportunities if p.scenario([o.code]).capex > 0]
    for budget in (0, 3e5, 1e6, 2e6, 6e6, 1e8):
        best_codes, best_fin = p.best_package(budget)
        brute = max((p.finance(list(c)).npv for n in range(0, len(codes) + 1) for c in itertools.combinations(codes, n)
                     if p.scenario(list(c)).capex <= budget and c), default=None)
        spent = p.scenario(best_codes).capex if best_codes else 0
        assert spent <= budget + 1e-6
        if brute is not None and brute > 0:
            assert best_fin.npv == pytest.approx(brute, rel=1e-9)
        else:
            assert not best_codes                                  # NPV'si pozitif paket yoksa boş döner


def test_rating_is_monotonic_in_eui(p):
    from edifice.engine.rating import energy_class
    order = "ABCDEFG"
    last = -1
    for eui in range(10, 600, 10):
        cls = energy_class(eui, p.assumptions.benchmark_for(p.building.use_type))
        assert order.index(cls) >= last
        last = order.index(cls)


def test_health_score_bounds_and_weights(p):
    h = p.health()
    assert 0 <= h.total <= 100
    assert all(0 <= v[0] <= 100 for v in h.components.values())
    assert sum(v[1] for v in h.components.values()) == pytest.approx(1.0)
    assert h.total == pytest.approx(sum(v[0] * v[1] for v in h.components.values()), abs=0.1)
    lo, hi, eq = p.health_range()
    assert lo <= h.total <= hi or lo - 1 <= h.total <= hi + 1
