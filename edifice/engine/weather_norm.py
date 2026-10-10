"""Hava normalizasyonu: tüketimi derece-güne regresyonla bağlayıp "normal yıl" iklimine çevirir.

Model (aylık, her enerji türü için): tüketim = a + b·HDD + c·CDD, b,c ≥ 0 (en küçük kareler).
Düzeltilmiş ay = gerçek + b·(HDD_normal − HDD_gerçek) + c·(CDD_normal − CDD_gerçek)  (artık hata korunur).
Güven: R² ve gözlem sayısı; zayıf modelde düzeltme yapılmaz ve nedeni söylenir."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..models import UtilityType
from ..weather import NORMAL_YEARS

MIN_POINTS = 12
R2_OK, R2_WEAK = 0.6, 0.3


@dataclass
class UtilityNorm:
    utility: str
    ok: bool
    r2: float = 0.0
    n: int = 0
    base_kwh: float = 0.0               # a (hava duyarsız taban, aylık)
    heat_slope: float = 0.0             # kWh / HDD
    cool_slope: float = 0.0             # kWh / CDD
    raw: dict[int, float] = field(default_factory=dict)       # yıl -> ham yıllık kWh
    normalized: dict[int, float] = field(default_factory=dict)
    note: str = ""


@dataclass
class WeatherNorm:
    year: int
    prev: int | None
    by_utility: dict[str, UtilityNorm]
    raw_total: float
    norm_total: float
    raw_prev_total: float | None
    norm_prev_total: float | None
    raw_change_pct: float | None
    norm_change_pct: float | None
    normal_years: int
    confidence: str                      # Yüksek | Orta | Düşük | Yok
    note: str = ""


def _fit(y: np.ndarray, hdd: np.ndarray, cdd: np.ndarray):
    cols = [np.ones_like(y), hdd, cdd]
    active = [0, 1, 2]
    for _ in range(3):
        X = np.column_stack([cols[i] for i in active])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        neg = [i for i, b in zip(active, beta) if i > 0 and b < 0]
        if not neg:
            break
        active = [i for i in active if i not in neg]
    full = [0.0, 0.0, 0.0]
    for i, b in zip(active, beta):
        full[i] = float(b)
    pred = full[0] + full[1] * hdd + full[2] * cdd
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return full, r2


def normal_year(dd: dict, until_year: int) -> dict[int, tuple[float, float]]:
    """Ay -> (HDD, CDD) son NORMAL_YEARS tam yılın ortalaması."""
    out = {}
    for m in range(1, 13):
        vals = [dd[(y, m)] for y in range(until_year - NORMAL_YEARS, until_year + 1) if (y, m) in dd and dd[(y, m)][2] >= 27]
        if vals:
            out[m] = (sum(v[0] for v in vals) / len(vals), sum(v[1] for v in vals) / len(vals))
    return out


def normalize(project, dd: dict) -> WeatherNorm | None:
    """Hava verisi yoksa None. dd: weather.monthly_degree_days çıktısı."""
    year, prev = project.year, project.previous_year()
    years = [y for y in (year, prev) if y is not None]
    normal = normal_year(dd, year)
    if len(normal) < 12:
        return None
    result: dict[str, UtilityNorm] = {}
    for u, label in ((UtilityType.GAS, "Doğalgaz"), (UtilityType.ELECTRICITY, "Elektrik")):
        series = {y: project.monthly(y, u) for y in years}
        pts = [(y, m + 1, v) for y, vals in series.items() for m, v in enumerate(vals) if v > 0 and (y, m + 1) in dd and dd[(y, m + 1)][2] >= 27]
        raw = {y: sum(series[y]) for y in years}
        un = UtilityNorm(u.value, False, raw=raw, normalized=dict(raw))
        if sum(raw.values()) <= 0:
            un.note = "Tüketim yok."
        elif len(pts) < MIN_POINTS:
            un.note = f"Yetersiz gözlem ({len(pts)} ay < {MIN_POINTS})."
        else:
            y_ = np.array([p[2] for p in pts])
            hdd = np.array([dd[(p[0], p[1])][0] for p in pts])
            cdd = np.array([dd[(p[0], p[1])][1] for p in pts])
            (a, b, c), r2 = _fit(y_, hdd, cdd)
            un.r2, un.n, un.base_kwh, un.heat_slope, un.cool_slope = r2, len(pts), a, b, c
            if r2 < R2_WEAK:
                un.note = f"İklimle ilişki zayıf (R²={r2:.2f}); düzeltme yapılmadı."
            else:
                un.ok = True
                for y in years:
                    adj = 0.0
                    for m, v in enumerate(series[y]):
                        if v <= 0 or (y, m + 1) not in dd:
                            adj += v
                            continue
                        h_a, c_a, _d = dd[(y, m + 1)]
                        h_n, c_n = normal[m + 1]
                        adj += v + b * (h_n - h_a) + c * (c_n - c_a)
                    un.normalized[y] = max(adj, 0.0)
                un.note = "Güvenilir" if r2 >= R2_OK else f"Orta güven (R²={r2:.2f})"
        result[label] = un
    raw_t = sum(u.raw.get(year, 0) for u in result.values())
    norm_t = sum(u.normalized.get(year, 0) for u in result.values())
    raw_p = sum(u.raw.get(prev, 0) for u in result.values()) if prev else None
    norm_p = sum(u.normalized.get(prev, 0) for u in result.values()) if prev else None
    ch = lambda a, b: (a / b - 1) * 100 if b else None
    used = [u for u in result.values() if u.ok]
    heavy = max(result.values(), key=lambda u: u.raw.get(year, 0))
    conf = "Yok" if not used else ("Yüksek" if heavy.ok and heavy.r2 >= R2_OK else "Orta" if heavy.ok else "Düşük")
    return WeatherNorm(year, prev, result, raw_t, norm_t, raw_p, norm_p, ch(raw_t, raw_p) if raw_p else None,
                       ch(norm_t, norm_p) if norm_p else None, NORMAL_YEARS, conf)


def fit_models(project, dd: dict) -> dict[UtilityType, tuple[float, float, float, float, int]]:
    """Enerji türü -> (a, b, c, R², n). Yeterli gözlem ve R² ≥ 0,3 yoksa o tür yer almaz."""
    years = [y for y in (project.year, project.previous_year()) if y is not None]
    out = {}
    for u in (UtilityType.GAS, UtilityType.ELECTRICITY):
        pts = []
        for y in years:
            for m, v in enumerate(project.monthly(y, u), start=1):
                if v > 0 and (y, m) in dd and dd[(y, m)][2] >= 27:
                    pts.append((v, dd[(y, m)][0], dd[(y, m)][1]))
        if len(pts) < MIN_POINTS:
            continue
        arr = np.array(pts)
        (a, b, c), r2 = _fit(arr[:, 0], arr[:, 1], arr[:, 2])
        if r2 >= R2_WEAK:
            out[u] = (a, b, c, r2, len(pts))
    return out
