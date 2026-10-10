"""Çatı GES boyutlandırma ve finansal analiz (aylık dengeli model).

Model: aylık üretim = kWp × (PVGIS kWh/kWp). Aylık elektrik tüketiminin üretimle örtüşen kısmının yalnız `SELF_MATCH` oranı eşzamanlı
tüketilir (saatlik veri yok; depolama yok); fazlası `EXPORT_FACTOR` × tarife ile değerlenir. Bu ikisi ve birim maliyet VARSAYIMDIR.
Çatı sınırı: kat başına alanın `ROOF_SHARE` kadarı, kWp başına `M2_PER_KWP` m²."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..models import Assumptions, UtilityType
from .finance import FinanceResult, analyze

SELF_MATCH = 0.85           # aylık örtüşmenin eşzamanlı tüketilen oranı (varsayım; gündüz ağırlıklı ofis için)
EXPORT_FACTOR = 0.0         # şebekeye verilen fazlanın tarifeye oranı (varsayım; mevzuat/uygulama doğrulanmadı, muhafazakâr 0)
ROOF_SHARE = 0.6            # çatının kullanılabilir oranı (varsayım)
M2_PER_KWP = 6.0            # kWp başına çatı alanı (varsayım)
DEFAULT_CAPEX_PER_KWP = 25_000.0     # ₺/kWp anahtar teslim (varsayım; teklifle değiştirin)


@dataclass
class SolarPlan:
    kwp: float
    production_kwh: float
    self_kwh: float
    export_kwh: float
    saving: float                 # yıllık ₺ (1. yıl)
    capex: float
    finance: FinanceResult
    carbon_avoided_kg: float
    coverage_pct: float           # öz tüketimin yıllık elektrik tüketimine oranı
    monthly_production: list[float] = field(default_factory=list)
    monthly_self: list[float] = field(default_factory=list)


def max_kwp(floor_area_m2: float, floors: int) -> float:
    return max(0.0, floor_area_m2 / max(floors, 1) * ROOF_SHARE / M2_PER_KWP)


def evaluate(kwp: float, yield_m: list[float], consumption_m: list[float], price: float, a: Assumptions,
             capex_per_kwp: float = DEFAULT_CAPEX_PER_KWP) -> SolarPlan:
    prod = [kwp * y for y in yield_m]
    selfc = [min(p, c) * SELF_MATCH for p, c in zip(prod, consumption_m)]
    export = [p - s for p, s in zip(prod, selfc)]
    saving = sum(selfc) * price + sum(export) * price * EXPORT_FACTOR
    capex = kwp * capex_per_kwp
    fin = analyze(capex, saving, a)
    total_cons = sum(consumption_m)
    return SolarPlan(kwp, sum(prod), sum(selfc), sum(export), saving, capex, fin,
                     sum(selfc) * a.emission_factor_kg_per_kwh[UtilityType.ELECTRICITY],
                     100 * sum(selfc) / total_cons if total_cons else 0.0, prod, selfc)


def size_for_best_npv(yield_m: list[float], consumption_m: list[float], price: float, a: Assumptions, kwp_cap: float,
                      capex_per_kwp: float = DEFAULT_CAPEX_PER_KWP, step: float = 5.0) -> tuple[SolarPlan | None, list[SolarPlan]]:
    """5 kWp adımlarla tarar; NPV'yi en yükseğe çıkaran boyutu ve tüm taramayı döndürür. NPV hiç pozitif değilse en iyi None."""
    sweep, k = [], step
    while k <= max(kwp_cap, step) + 1e-9 and k <= 5000:
        sweep.append(evaluate(k, yield_m, consumption_m, price, a, capex_per_kwp))
        k += step
    if not sweep:
        return None, []
    best = max(sweep, key=lambda p: p.finance.npv)
    return (best if best.finance.npv > 0 else None), sweep
