import pytest

from edifice.engine.pricing import analyze
from edifice.models import UtilityType
from edifice.service import Project


def test_tariff_derived_prices_are_not_analyzed():
    r = analyze(Project.mock(), UtilityType.ELECTRICITY)
    assert r.ok and r.tariff_derived and r.excess_total == 0


def test_spike_months_are_flagged_with_excess_cost():
    p = Project.mock()
    for r in p.readings:
        if r.utility == UtilityType.ELECTRICITY and r.year == p.year:
            r.cost *= 1.0 + 0.0 * r.month            # tarifeden türetilmiş zinciri kır
            r.cost += r.consumption * 0.01 * (r.month % 3)
    spike = next(r for r in p.readings if r.utility == UtilityType.ELECTRICITY and r.year == p.year and r.month == 7)
    base_price = spike.cost / spike.consumption
    spike.cost += spike.consumption * base_price * 0.40          # reaktif ceza gibi %40 fazla
    rep = analyze(p, UtilityType.ELECTRICITY)
    assert rep.ok and not rep.tariff_derived
    flagged = [m for m in rep.months if m.flagged]
    assert [m.month for m in flagged] == [7]
    assert flagged[0].excess_cost == pytest.approx((flagged[0].price - rep.median_price) * flagged[0].consumption)
    assert rep.excess_total == pytest.approx(flagged[0].excess_cost) and rep.excess_total > 0


def test_insufficient_months_explained():
    p = Project.mock()
    p.readings = [r for r in p.readings if not (r.utility == UtilityType.GAS and r.year == p.year and r.month > 3)]
    rep = analyze(p, UtilityType.GAS)
    assert not rep.ok and "Yetersiz veri" in rep.note
