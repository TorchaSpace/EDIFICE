import math
import random
from datetime import date, timedelta

import pytest

from edifice import weather
from edifice.engine.weather_norm import normalize
from edifice.models import UtilityReading, UtilityType
from edifice.service import Project


def synth_daily(first_year, last_year, shift=lambda y: 0.0):
    """Sinüs tabanlı yapay sıcaklık (ortalama 14°C, genlik 10°C) + yıla özgü sapma."""
    out, d = [], date(first_year, 1, 1)
    while d <= date(last_year, 12, 31):
        doy = d.timetuple().tm_yday
        t = 14 - 10 * math.cos(2 * math.pi * (doy - 15) / 365) + shift(d.year)
        out.append((d, t))
        d += timedelta(days=1)
    return out


def build_project(dd, gas_base=20000.0, gas_slope=900.0, noise=0.0, years=(2024, 2025)):
    rng = random.Random(1)
    p = Project.mock()
    p.readings = [r for r in p.readings if r.utility != UtilityType.GAS]
    for y in years:
        for m in range(1, 13):
            hdd = dd[(y, m)][0]
            p.readings.append(UtilityReading(UtilityType.GAS, y, m, gas_base + gas_slope * hdd + rng.gauss(0, noise), 1.0))
    return p


def test_degree_days_from_daily():
    dd = weather.monthly_degree_days([(date(2025, 1, d), 5.0) for d in range(1, 32)])
    h, c, n = dd[(2025, 1)]
    assert n == 31 and h == pytest.approx(31 * (weather.HDD_BASE_C - 5)) and c == 0


def test_recovers_weather_effect_and_normalizes_warm_winter():
    # 2025 kışı 2°C sıcak: ham tüketim düşer; düzeltilince normal yıla yaklaşmalı
    dd = weather.monthly_degree_days(synth_daily(2012, 2025, lambda y: 2.0 if y == 2025 else 0.0))
    p = build_project(dd)
    wn = normalize(p, dd)
    g = wn.by_utility["Doğalgaz"]
    assert g.ok and g.r2 > 0.99 and g.heat_slope == pytest.approx(900, rel=0.02)
    raw_ch = (g.raw[2025] / g.raw[2024] - 1) * 100
    norm_ch = (g.normalized[2025] / g.normalized[2024] - 1) * 100
    assert raw_ch < -8                                   # ham: belirgin düşüş (sıcak kış)
    assert abs(norm_ch) < 0.5                            # düzeltilmiş: gerçekte değişim yok (yalnız hava farkı)
    assert wn.confidence == "Yüksek"


def test_real_efficiency_gain_survives_normalization():
    dd = weather.monthly_degree_days(synth_daily(2012, 2025))
    p = build_project(dd, gas_base=20000.0)
    for r in p.readings:                                  # 2025'te sabit tüketim %10 azaldı (gerçek verimlilik)
        if r.utility == UtilityType.GAS and r.year == 2025:
            r.consumption -= 0.10 * 20000.0
    g = normalize(p, dd).by_utility["Doğalgaz"]
    assert (g.normalized[2025] / g.normalized[2024] - 1) * 100 < -1.0     # iyileşme düzeltmede kaybolmaz


def test_weak_relationship_is_not_normalized():
    dd = weather.monthly_degree_days(synth_daily(2012, 2025))
    rng = random.Random(3)
    p = build_project(dd)
    for r in p.readings:
        if r.utility == UtilityType.GAS:
            r.consumption = rng.uniform(50000, 60000)     # iklimle ilgisiz
    gas = normalize(p, dd).by_utility["Doğalgaz"]
    assert not gas.ok and "zayıf" in gas.note and gas.normalized == gas.raw


def test_missing_weather_returns_none_and_cache_check():
    p = Project.mock()
    assert normalize(p, {}) is None
    assert weather.missing_for({}, [2024, 2025], today=date(2026, 1, 20))
    dd = weather.monthly_degree_days(synth_daily(2014, 2025))
    assert not weather.missing_for(dd, [2024, 2025], today=date(2026, 1, 20))


def test_never_negative_and_finite_under_noise():
    dd = weather.monthly_degree_days(synth_daily(2012, 2025))
    p = build_project(dd, noise=8000)
    wn = normalize(p, dd)
    assert all(math.isfinite(v) and v >= 0 for u in wn.by_utility.values() for v in u.normalized.values())


def test_weather_cache_roundtrip_and_chat_answer():
    from edifice.ai.local import LocalAssistant, Memory
    from edifice.ai.tools import Toolbox
    from edifice.db import Store
    dd = weather.monthly_degree_days(synth_daily(2012, 2025, lambda y: 2.0 if y == 2025 else 0.0))
    st = Store(":memory:")
    st.save_weather(41.01, 28.98, dd)
    assert st.load_weather(41.04, 28.96) == {k: pytest.approx(v) for k, v in dd.items()}     # 0,1° ızgarası
    assert st.load_weather(10, 10) == {}
    p = build_project(dd)
    ai = LocalAssistant()
    ans = ai.answer("hava düzeltmeli tüketim nasıl", Toolbox({1: p}, 1, {1: dd}), Memory())
    assert "hava düzeltmesi güveni" in ans.lower() and "%" in ans
    none = ai.answer("iklim etkisi ne kadar", Toolbox({1: p}, 1), Memory())
    assert "hava verisi yok" in none
