"""Hava verisi: günlük ortalama sıcaklıktan aylık derece-gün (HDD/CDD) hesabı ve önbellekli indirme (Open-Meteo arşiv API'si).

Not: Open-Meteo ücretsiz API'si ticari olmayan kullanım içindir; ticari dağıtımda ücretli plana geçmek ya da kendi sunucunda
barındırmak gerekir (BASE_URL değiştirilerek). Derece-gün taban sıcaklıkları varsayımdır (Ayarlar'a taşınabilir)."""
from __future__ import annotations

import json
from calendar import monthrange
from datetime import date, timedelta
from urllib.parse import urlencode

HDD_BASE_C = 15.0     # ısıtma: günlük ortalama bu sıcaklığın altı (varsayım)
CDD_BASE_C = 22.0     # soğutma: günlük ortalama bu sıcaklığın üstü (varsayım)
NORMAL_YEARS = 10     # "normal yıl" = son 10 tam yılın aylık ortalaması
BASE_URL = "https://archive-api.open-meteo.com/v1/archive"
LAG_DAYS = 7          # arşivin son günlere ait verisi gecikmeli gelir


def request_url(lat: float, lon: float, start: date, end: date) -> str:
    q = {"latitude": f"{lat:.3f}", "longitude": f"{lon:.3f}", "start_date": start.isoformat(), "end_date": end.isoformat(),
         "daily": "temperature_2m_mean", "timezone": "auto"}
    return f"{BASE_URL}?{urlencode(q)}"


def parse_daily(data: bytes) -> list[tuple[date, float]]:
    try:
        d = json.loads(data.decode("utf-8"))["daily"]
        return [(date.fromisoformat(t), float(v)) for t, v in zip(d["time"], d["temperature_2m_mean"]) if v is not None]
    except (KeyError, ValueError, TypeError):
        return []


def monthly_degree_days(daily: list[tuple[date, float]]) -> dict[tuple[int, int], tuple[float, float, int]]:
    """{(yıl, ay): (HDD, CDD, gün sayısı)}"""
    out: dict[tuple[int, int], list[float]] = {}
    for d, t in daily:
        acc = out.setdefault((d.year, d.month), [0.0, 0.0, 0])
        acc[0] += max(0.0, HDD_BASE_C - t)
        acc[1] += max(0.0, t - CDD_BASE_C)
        acc[2] += 1
    return {k: (v[0], v[1], int(v[2])) for k, v in out.items()}


def complete(dd: dict, year: int, month: int) -> bool:
    got = dd.get((year, month))
    return bool(got) and got[2] >= monthrange(year, month)[1] - 1


def needed_range(first_year: int, last_year: int, today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    start = date(min(first_year, last_year - NORMAL_YEARS), 1, 1)
    end = min(date(last_year, 12, 31), today - timedelta(days=LAG_DAYS))
    return start, end


def missing_for(dd: dict, years: list[int], today: date | None = None) -> bool:
    """Önbellekte, tüketim yıllarının tam aylarından ve normal-yıl aralığından eksik var mı?"""
    if not years:
        return False
    start, end = needed_range(min(years), max(years), today)
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        last_day = date(y, m, monthrange(y, m)[1])
        if last_day <= end and not complete(dd, y, m):
            return True
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return False


# ---- anlık durum ve tahmin (Open-Meteo forecast API) ------------------------------------------------------
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
WMO = {0: ("Açık", "☀"), 1: ("Çoğunlukla açık", "🌤"), 2: ("Parçalı bulutlu", "⛅"), 3: ("Kapalı", "☁"), 45: ("Sisli", "🌫"), 48: ("Kırağılı sis", "🌫"),
       51: ("Hafif çise", "🌦"), 53: ("Çise", "🌦"), 55: ("Yoğun çise", "🌧"), 61: ("Hafif yağmur", "🌧"), 63: ("Yağmur", "🌧"), 65: ("Şiddetli yağmur", "🌧"),
       71: ("Hafif kar", "🌨"), 73: ("Kar", "🌨"), 75: ("Yoğun kar", "❄"), 80: ("Hafif sağanak", "🌦"), 81: ("Sağanak", "🌧"), 82: ("Şiddetli sağanak", "⛈"),
       95: ("Fırtına", "⛈"), 96: ("Dolulu fırtına", "⛈"), 99: ("Şiddetli dolulu fırtına", "⛈")}


def describe(code) -> tuple[str, str]:
    try:
        c = int(code)
    except (TypeError, ValueError):
        return ("-", "")
    return WMO.get(c) or WMO.get(max((k for k in WMO if k <= c), default=0), ("-", ""))


def forecast_url(lat: float, lon: float, past_days: int = 7, forecast_days: int = 7) -> str:
    q = {"latitude": f"{lat:.3f}", "longitude": f"{lon:.3f}",
         "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,shortwave_radiation",
         "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,weather_code,sunshine_duration",
         "past_days": past_days, "forecast_days": forecast_days, "timezone": "auto"}
    return f"{FORECAST_URL}?{urlencode(q)}"


def parse_forecast(data: bytes) -> dict | None:
    """-> {"current": {...}, "daily": [{"date","tmax","tmin","tmean","precip","code","sun_h"}]} ya da None."""
    try:
        d = json.loads(data.decode("utf-8"))
        cur = d["current"]
        day = d["daily"]
        rows = []
        for i, t in enumerate(day["time"]):
            tm = day["temperature_2m_mean"][i]
            if tm is None:
                continue
            sun = day.get("sunshine_duration", [None] * len(day["time"]))[i]
            rows.append({"date": t, "tmax": day["temperature_2m_max"][i], "tmin": day["temperature_2m_min"][i], "tmean": tm,
                         "precip": day["precipitation_sum"][i] or 0.0, "code": day["weather_code"][i], "sun_h": (sun or 0) / 3600})
        if not rows or cur.get("temperature_2m") is None:
            return None
        return {"current": {"time": cur["time"], "temp": cur["temperature_2m"], "feels": cur.get("apparent_temperature"),
                            "humidity": cur.get("relative_humidity_2m"), "wind": cur.get("wind_speed_10m"), "precip": cur.get("precipitation") or 0.0,
                            "code": cur.get("weather_code"), "radiation": cur.get("shortwave_radiation")}, "daily": rows}
    except (KeyError, ValueError, TypeError, IndexError):
        return None


def merge_recent(dd: dict, daily_rows: list[tuple[str, float]]) -> dict:
    """Arşiv geriden gelir (≈7 gün); son günlerin gözlemleriyle eksik/yarım ayları tamamlar. daily_rows: (YYYY-MM-DD, ortalama °C)."""
    pts = [(date.fromisoformat(d), t) for d, t in daily_rows]
    fresh = monthly_degree_days(pts)
    out = dict(dd)
    for k, v in fresh.items():
        if k not in out or v[2] > out[k][2]:
            out[k] = v
    return out
