"""Birim fiyat analizi: faturadaki etkin birim fiyat (₺/kWh) aylık izlenir; medyandan belirgin sapan aylar "olası fazla ödeme" adayıdır.

Neden: elektrik faturasında reaktif enerji bedeli, güç (demand) aşımı, yanlış tarife grubu gibi kalemler tüketimden bağımsız olarak
etkin fiyatı yükseltir. Bu analiz NEDENİ söylemez (faturada kalem yok); yalnızca incelenmesi gereken ayları ve üst sınır tutarı verir."""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

from ..models import UtilityType

SPIKE = 0.15          # medyanın bu kadar üstü = şüpheli (varsayım)
MIN_MONTHS = 6


@dataclass
class MonthPrice:
    month: int
    consumption: float
    price: float
    deviation: float          # (fiyat / medyan) − 1
    flagged: bool
    excess_cost: float        # (fiyat − medyan) × tüketim, yalnız flagged için > 0


@dataclass
class PriceReport:
    utility: str
    year: int
    ok: bool
    median_price: float = 0.0
    months: list[MonthPrice] = field(default_factory=list)
    excess_total: float = 0.0
    tariff_derived: bool = False       # fiyat varsayılan tarifeyle birebir aynı -> gerçek fatura tutarı girilmemiş
    note: str = ""


def analyze(project, utility: UtilityType, year: int | None = None) -> PriceReport:
    year = year or project.year
    rows = sorted((r for r in project.readings if r.utility == utility and r.year == year and r.consumption > 0 and r.cost > 0), key=lambda r: r.month)
    rep = PriceReport(utility.value, year, False)
    if len(rows) < MIN_MONTHS:
        rep.note = f"Yetersiz veri ({len(rows)} ay < {MIN_MONTHS}): tutarlı fatura tutarı olan ay sayısı az."
        return rep
    prices = [r.cost / r.consumption for r in rows]
    med = median(prices)
    tariff = project.assumptions.default_tariffs.get(utility)
    rep.tariff_derived = bool(tariff) and all(abs(p / tariff - 1) <= 0.005 for p in prices)
    rep.median_price, rep.ok = med, True
    for r, p in zip(rows, prices):
        dev = p / med - 1
        flagged = dev > SPIKE and not rep.tariff_derived
        excess = (p - med) * r.consumption if flagged else 0.0
        rep.months.append(MonthPrice(r.month, r.consumption, p, dev, flagged, excess))
    rep.excess_total = sum(m.excess_cost for m in rep.months)
    if rep.tariff_derived:
        rep.note = "Fiyatlar varsayılan tarifeyle birebir aynı: gerçek fatura tutarları girilmemiş görünüyor, analiz yapılamaz."
    return rep
