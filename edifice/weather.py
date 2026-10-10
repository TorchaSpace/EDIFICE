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
