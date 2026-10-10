"""Bozuk/uç girdilerle de motor çökmemeli ve çıktılar sınırlı kalmalıdır (Health Score 0-100, geçerli sınıf, sonlu sayılar)."""
import math
import random

import pytest

from edifice.models import UtilityType
from edifice.quality import assess
from edifice.service import Project


def _mutate(rng: random.Random) -> Project:
    p = Project.mock()
    b = p.building
    for r in p.readings:
        roll = rng.random()
        if roll < 0.04:
            r.consumption = 0.0
        elif roll < 0.07:
            r.consumption *= rng.choice([1000, 0.001, 50])
        elif roll < 0.09:
            r.cost = 0.0
    if rng.random() < 0.3:
        keep_year = max(r.year for r in p.readings)          # son yıl tam kalır (doğrulama zaten 12 ay ister)
        p.readings = [r for r in p.readings if r.year == keep_year or rng.random() > 0.3]
    b.floor_area_m2 = rng.choice([b.floor_area_m2, 1.0, 50.0, 5_000_000.0])
    b.floors = rng.choice([1, 8, 200])
    b.occupants = rng.choice([0, 320, 100000])
    b.year_built = rng.choice([1850, 1998, 2024])
    for e in p.equipment:
        e.year_installed = rng.choice([e.year_installed, 1900, 2026, 2999, 1000])
        e.condition = rng.choice([1, 3, 5, 0, 9])
    if rng.random() < 0.2:
        p.equipment = []
    return p


@pytest.mark.parametrize("seed", range(60))
def test_engine_survives_bad_inputs_and_stays_bounded(seed):
    p = _mutate(random.Random(seed))
    try:
        h = p.health()
        k = p.kpis()
        r = p.rating()
        codes = p.applicable_codes()
        f = p.finance(codes) if codes else None
        s = p.scenario(codes)
        q = assess(p)
        p.yoy()
        p.health_range()
        p.best_package(1e6)
    except ZeroDivisionError as e:          # sıfır bölme bir hata olarak kabul edilmez
        pytest.fail(f"sıfıra bölme: {e}")
    assert 0 <= h.total <= 100 and all(0 <= v[0] <= 100 for v in h.components.values())
    assert r["class"] in "ABCDEFG" and 0 <= r["percentile"] <= 100
    for v in (k.total_energy_kwh, k.eui_kwh_m2, k.carbon_kg, k.total_cost, s.capex, s.annual_saving):
        assert math.isfinite(v) and v >= 0
    if f:
        assert math.isfinite(f.npv)
    assert 0 <= q.score <= 100
