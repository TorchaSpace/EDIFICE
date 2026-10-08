"""Bütçeye göre en yüksek net bugünkü değeri (NPV) veren öneri paketini seçer."""
from __future__ import annotations

from itertools import combinations

from ..models import Opportunity
from .finance import FinanceResult, analyze
from .opportunities import run_scenario

BRUTE_FORCE_LIMIT = 14


def best_package(opps: list[Opportunity], building, kpis, prices, a, budget: float
                 ) -> tuple[list[str], FinanceResult | None]:
    """-> (seçilen öneri kodları, finans sonucu). Bütçeye hiçbiri sığmazsa ([], None)."""
    area = building.floor_area_m2

    def evaluate(subset: tuple[Opportunity, ...]):
        scen = run_scenario(list(subset), building, kpis, prices, a)
        return analyze(scen.capex, scen.annual_saving, a)

    candidates = [o for o in opps if o.capex_per_m2 * area <= budget + 1e-6]
    best_codes: list[str] = []
    best: FinanceResult | None = None
    if len(candidates) <= BRUTE_FORCE_LIMIT:
        for size in range(1, len(candidates) + 1):
            for subset in combinations(candidates, size):
                if sum(o.capex_per_m2 for o in subset) * area > budget + 1e-6:
                    continue
                fin = evaluate(subset)
                if best is None or fin.npv > best.npv + 1e-6 or (abs(fin.npv - best.npv) <= 1e-6 and fin.capex < best.capex):
                    best, best_codes = fin, [o.code for o in subset]
    else:  # çok büyük katalog: NPV/CAPEX oranına göre açgözlü seçim
        chosen: list[Opportunity] = []
        spent = 0.0
        ranked = sorted(candidates, key=lambda o: -evaluate((o,)).npv / max(o.capex_per_m2 * area, 1))
        for o in ranked:
            cost = o.capex_per_m2 * area
            if spent + cost <= budget:
                trial = (*chosen, o)
                if best is None or evaluate(trial).npv > best.npv:
                    chosen.append(o)
                    spent += cost
                    best = evaluate(tuple(chosen))
        best_codes = [o.code for o in chosen]
    if best is not None and best.npv <= 0:
        return [], None   # NPV'si pozitif olmayan paket önerilmez
    return best_codes, best
