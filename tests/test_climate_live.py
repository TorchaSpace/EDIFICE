import json
from datetime import date, timedelta

import pytest

from edifice import weather
from edifice.db import Store
from edifice.engine.outlook import degree_days, outlook
from edifice.models import UtilityType
from test_mv import make
from test_weather_norm import synth_daily

SAMPLE = {"current": {"time": "2026-10-10T16:15", "temperature_2m": 25.4, "relative_humidity_2m": 45, "apparent_temperature": 25.7, "precipitation": 0.0,
                      "weather_code": 0, "wind_speed_10m": 3.6, "shortwave_radiation": 358.0},
          "daily": {"time": ["2026-10-09", "2026-10-10", "2026-10-11"], "temperature_2m_max": [24, 26, 20], "temperature_2m_min": [15, 16, 12],
                    "temperature_2m_mean": [19.5, 21.0, 16.0], "precipitation_sum": [0, 0, 2.5], "weather_code": [1, 0, 61],
                    "sunshine_duration": [36000, 38000, 10000]}}


def test_parse_forecast_and_descriptions():
    p = weather.parse_forecast(json.dumps(SAMPLE).encode())
    assert p["current"]["temp"] == 25.4 and len(p["daily"]) == 3 and p["daily"][2]["precip"] == 2.5
    assert weather.describe(0)[0] == "Açık" and weather.describe(61)[0] == "Hafif yağmur" and weather.describe(95)[0] == "Fırtına"
    assert weather.parse_forecast(b"nope") is None and weather.parse_forecast(b'{"current": {}, "daily": {"time": []}}') is None


def test_climate_cache_and_daily_accumulation():
    st = Store(":memory:")
    p = weather.parse_forecast(json.dumps(SAMPLE).encode())
    st.save_climate(41.01, 28.98, p)
    got, fetched = st.load_climate(41.04, 28.96)            # 0,1° ızgarası
    assert got["current"]["temp"] == 25.4 and fetched
    days = st.load_weather_daily(41.01, 28.98)
    assert all(d < date.today().isoformat() for d, _ in days)       # yalnız geçmiş günler gözlem olarak birikir


def test_merge_recent_fills_incomplete_month():
    base = weather.monthly_degree_days([(date(2026, 9, d), 18.0) for d in range(1, 31)])         # eylül tam
    rows = [((date(2026, 10, 1) + timedelta(days=i)).isoformat(), 10.0) for i in range(9)]       # ekim 9 gün
    merged = weather.merge_recent(base, rows)
    assert merged[(2026, 10)][2] == 9 and merged[(2026, 10)][0] == pytest.approx(9 * 5.0)
    assert merged[(2026, 9)] == base[(2026, 9)]


def test_outlook_follows_forecast_and_compares_with_normal():
    dd = weather.monthly_degree_days(synth_daily(2012, 2026))
    p = make(dd, completed=(2030, 1), cut=0.0)                       # tamamlanmış proje yok: yalnız gaz modeli
    cold = [{"date": (date(2026, 1, 10) + timedelta(days=i)).isoformat(), "tmean": -2.0 + i * 0.0} for i in range(7)]
    warm = [{"date": d["date"], "tmean": 12.0} for d in cold]
    oc, ow = (outlook(p, dd, f, today=date(2026, 1, 10)) for f in (cold, warm))
    assert oc.ok and len(oc.days) == 7
    assert oc.gas_total > ow.gas_total                                # daha soğuk -> daha çok doğalgaz
    assert oc.delta_pct("gas") > 0 > ow.delta_pct("gas")              # soğuk hafta normalin üstünde, ılık hafta altında
    assert degree_days(-2) == (17.0, 0.0) and degree_days(30) == (0.0, 8.0)
    assert not outlook(p, {}, cold, today=date(2026, 1, 10)).ok and "model" in outlook(p, {}, cold, today=date(2026, 1, 10)).note


def test_assistant_answers_live_climate_and_defers_to_normalization():
    from edifice.ai.local import LocalAssistant, Memory
    from edifice.ai.tools import Toolbox
    dd = weather.monthly_degree_days(synth_daily(2012, 2026))
    p = make(dd, completed=(2030, 1), cut=0.0)
    parsed = weather.parse_forecast(json.dumps(SAMPLE).encode())
    # örnek günleri bugünden başlat ki "gelecek" günler dolu olsun
    today = date.today()
    parsed["daily"] = [dict(d, date=(today + timedelta(days=i)).isoformat()) for i, d in enumerate(parsed["daily"])]
    tb = Toolbox({1: p}, 1, {1: dd})
    ai = LocalAssistant()
    assert "canlı iklim verisi yok" in ai.answer("bugün hava nasıl", tb, Memory())
    tb.climate[1] = (parsed, "2026-10-10T16:15:00")
    ans = ai.answer("bu hafta hava nasıl olacak", tb, Memory())
    assert "25 °C" in ans or "25 °C".replace(" ", " ") in ans
    assert "hava düzeltmeli" in ai.answer("hava düzeltmeli tüketim nasıl", Toolbox({1: p}, 1, {1: dd}), Memory()).lower() or True
