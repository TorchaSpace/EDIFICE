import random

import pytest

from edifice import weather
from edifice.engine.mv import measure
from edifice.models import UtilityReading, UtilityType
from edifice.service import Project
from test_weather_norm import synth_daily


def make(dd, completed=(2025, 1), cut=0.15, noise=300.0, years=(2023, 2024, 2025, 2026), cut_all_post=True):
    rng = random.Random(7)
    p = Project.mock()
    p.readings = [r for r in p.readings if r.utility != UtilityType.GAS]
    for y in years:
        for m in range(1, 13):
            base = 20000 + 900 * dd[(y, m)][0] + rng.gauss(0, noise)
            if (y, m) >= completed:
                base *= (1 - cut)
            p.readings.append(UtilityReading(UtilityType.GAS, y, m, base, base))
    return p


@pytest.fixture
def dd():
    return weather.monthly_degree_days(synth_daily(2012, 2026, lambda y: {2025: 1.5, 2026: -1.0}.get(y, 0.0)))


def test_measures_known_saving_despite_weather_swings(dd):
    p = make(dd, completed=(2025, 1), cut=0.15)
    r = measure(p, dd, {"BOILER": (2025, 1)})[0]            # BOILER gazı etkiler
    assert r.ok and r.model_ok and r.n_pre == 24 and r.n_post == 24
    assert r.saved_pct == pytest.approx(0.15, abs=0.02)      # hava dalgalansa da %15 yakalanır
    assert r.significant and r.saved_kwh > 0
    assert r.realization_pct == pytest.approx(100 * 0.15 / 0.12, rel=0.2)    # katalog %12 bekliyordu


def test_no_real_saving_is_not_significant(dd):
    p = make(dd, completed=(2025, 1), cut=0.0)
    r = measure(p, dd, {"BOILER": (2025, 1)})[0]
    assert r.ok and abs(r.saved_pct) < 0.02 and not r.significant


def test_insufficient_pre_or_post_or_weather_is_explained(dd):
    p = make(dd, completed=(2024, 1), years=(2024, 2025))
    r = measure(p, dd, {"BOILER": (2024, 1)})[0]
    assert not r.ok and "öncesi veri yetersiz" in r.note
    p2 = make(dd, completed=(2026, 11), years=(2024, 2025, 2026))
    p2.readings = [x for x in p2.readings if not (x.year == 2026 and x.month > 11)]
    assert "sonrası veri yetersiz" in measure(p2, dd, {"BOILER": (2026, 11)})[0].note
    assert "Hava verisi yok" in measure(p, {}, {"BOILER": (2024, 1)})[0].note


def test_short_post_period_is_flagged(dd):
    p = make(dd, completed=(2026, 1), years=(2023, 2024, 2025, 2026))
    p.readings = [x for x in p.readings if not (x.year == 2026 and x.month > 6)]
    r = measure(p, dd, {"BOILER": (2026, 1)})[0]
    assert r.ok and r.n_post == 6 and "12 aydan kısa" in r.note


def test_assistant_and_ui_report_measured_saving(dd):
    from edifice.ai.local import LocalAssistant, Memory
    from edifice.ai.tools import Toolbox
    p = make(dd, completed=(2025, 1), cut=0.15)
    tb = Toolbox({1: p}, 1, {1: dd})
    tb.completed[1] = {"BOILER": (2025, 1)}
    ans = LocalAssistant().answer("biten projeler ne kadar kazandırdı", tb, Memory())
    assert "Yoğuşmalı kazan" in ans and "%15" in ans or "%14" in ans or "%16" in ans
    none = LocalAssistant().answer("gerçekleşen tasarruf", Toolbox({1: p}, 1, {1: dd}), Memory())
    assert "tamamlandı olarak işaretlenmiş proje yok" in none
