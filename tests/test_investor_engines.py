import math

from edifice.db import Store
from edifice.engine.finance import analyze
from edifice.engine.rating import energy_class, percentile_worse_than
from edifice.models import Assumptions


def test_energy_class_boundaries():
    assert energy_class(60, 150) == "A" and energy_class(150, 150) == "C" and energy_class(400, 150) == "G"


def test_percentile_monotonic_and_median():
    assert abs(percentile_worse_than(150, 150) - 50) < 1e-6
    assert percentile_worse_than(250, 150) > percentile_worse_than(150, 150) > percentile_worse_than(90, 150)


def test_finance_known_values():
    a = Assumptions()
    a.discount_rate, a.energy_escalation, a.savings_degradation, a.horizon_years = 0.10, 0.0, 0.0, 10
    f = analyze(1000, 250, a)
    expected_npv = -1000 + sum(250 / 1.1 ** t for t in range(1, 11))
    assert math.isclose(f.npv, expected_npv, rel_tol=1e-9)
    assert math.isclose(f.simple_payback, 4.0, rel_tol=1e-6)
    assert f.irr is not None and math.isclose(sum(c / (1 + f.irr) ** t for t, c in enumerate(f.cash_flows)), 0, abs_tol=1e-6)
    assert len(f.cumulative) == 11 and f.cumulative[-1] == f.total_net == 1500


def test_finance_unprofitable_has_no_irr():
    a = Assumptions()
    f = analyze(1000, 10, a)
    assert f.irr is None and f.npv < 0 and f.simple_payback == float("inf")


def test_best_package_respects_budget_and_beats_single():
    store = Store(":memory:")
    p = store.load_project(store.seed_demo())
    area = p.building.floor_area_m2
    codes, fin = p.best_package(1_200_000)
    assert fin is not None and fin.capex <= 1_200_000 + 1e-6
    big, fin2 = p.best_package(10_000_000)
    assert fin2.npv >= fin.npv and set(codes) <= set(big) or fin2.npv >= fin.npv
    none_codes, none_fin = p.best_package(10_000)
    assert none_codes == [] and none_fin is None


def test_settings_roundtrip_includes_finance():
    store = Store(":memory:")
    a = store.load_assumptions()
    a.discount_rate, a.horizon_years = 0.12, 20
    store.save_assumptions(a)
    b = store.load_assumptions()
    assert b.discount_rate == 0.12 and b.horizon_years == 20
