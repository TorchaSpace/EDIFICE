"""Önümüzdeki günlerin enerji öngörüsü: aylık hava-tüketim modelini günlüğe indirip tahmin sıcaklıklarına uygular.

Günlük model: tüketim_gün = a/30,4 + b·HDD_gün + c·CDD_gün (a,b,c aylık regresyondan). Bu bir YAKLAŞIMDIR: model aylık verilerle kuruldu,
günlük dalgalanmayı (hafta sonu, tatil) bilmez. Normal haftayla kıyas, aynı takvim ayının son 10 yıllık ortalama günlük derece-günüyle yapılır."""
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date

from ..models import UtilityType
from ..weather import CDD_BASE_C, HDD_BASE_C
from .weather_norm import fit_models, normal_year


@dataclass
class OutlookDay:
    day: str
    tmean: float
    hdd: float
    cdd: float
    gas_kwh: float
    elec_kwh: float


@dataclass
class Outlook:
    days: list[OutlookDay] = field(default_factory=list)
    gas_total: float = 0.0
    elec_total: float = 0.0
    gas_normal: float = 0.0
    elec_normal: float = 0.0
    r2: dict[str, float] = field(default_factory=dict)
    note: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.days)

    def delta_pct(self, key: str) -> float | None:
        a, b = (self.gas_total, self.gas_normal) if key == "gas" else (self.elec_total, self.elec_normal)
        return (a / b - 1) * 100 if b else None


def degree_days(t: float) -> tuple[float, float]:
    return max(0.0, HDD_BASE_C - t), max(0.0, t - CDD_BASE_C)


def outlook(project, dd: dict, forecast_days: list[dict], today: date | None = None, horizon: int = 7) -> Outlook:
    today = today or date.today()
    future = [d for d in forecast_days if d["date"] >= today.isoformat()][:horizon]
    out = Outlook()
    if not future:
        out.note = "Tahmin verisi yok."
        return out
    models = fit_models(project, dd)
    if not models:
        out.note = "İklim–tüketim modeli kurulamadı (en az 12 ay veri ve iklimle ilişki gerekir); önce geçmiş faturaları yükleyin."
        return out
    normal = normal_year(dd, project.year)
    for d in future:
        dt = date.fromisoformat(d["date"])
        hdd, cdd = degree_days(d["tmean"])
        dim = monthrange(dt.year, dt.month)[1]
        per_day = {}
        per_day_norm = {}
        for u, (a, b, c, r2, n) in models.items():
            base = a / 30.4
            per_day[u] = max(0.0, base + b * hdd + c * cdd)
            nh, nc = normal.get(dt.month, (None, None))
            per_day_norm[u] = max(0.0, base + b * (nh / dim) + c * (nc / dim)) if nh is not None else per_day[u]
        gas, elec = per_day.get(UtilityType.GAS, 0.0), per_day.get(UtilityType.ELECTRICITY, 0.0)
        out.days.append(OutlookDay(d["date"], d["tmean"], hdd, cdd, gas, elec))
        out.gas_total += gas
        out.elec_total += elec
        out.gas_normal += per_day_norm.get(UtilityType.GAS, 0.0)
        out.elec_normal += per_day_norm.get(UtilityType.ELECTRICITY, 0.0)
    out.r2 = {u.value: m[3] for u, m in models.items()}
    out.note = "Model aylık verilerle kuruldu; günlük tahmin yaklaşıktır (hafta sonu/tatil etkisi bilinmez)."
    return out
