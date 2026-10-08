"""Building Health Score (0-100).

Her bileşen 0-100 puana çevrilir, ağırlıklı ortalaması alınır.
Ağırlıklar ve kıyas değerleri varsayımdır; pilot bina ile doğrulanmalıdır.
"""
from __future__ import annotations

from datetime import date

from ..models import Assumptions, Equipment, HealthScore, KPIs



_RATIO_POINTS = [(0.5, 100.0), (1.0, 70.0), (1.6, 0.0)]


def _ratio_score(value: float, benchmark: float) -> float:
    """Kıyas oranı r=değer/kıyas: r<=0.5 -> 100, r=1 -> 70, r>=1.6 -> 0 (aralarda doğrusal)."""
    if benchmark <= 0:
        return 0.0
    r = value / benchmark
    pts = _RATIO_POINTS
    if r <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if r <= x1:
            return y0 + (y1 - y0) * (r - x0) / (x1 - x0)
    return pts[-1][1]


def _equipment_score(equipment: list[Equipment], life: int, today: int | None = None) -> float:
    if not equipment:
        return 50.0
    today = today or date.today().year
    scores = []
    for e in equipment:
        age_score = max(0.0, 1 - (today - e.year_installed) / life)
        cond_score = (e.condition - 1) / 4
        scores.append(100 * (0.4 * age_score + 0.6 * cond_score))
    return sum(scores) / len(scores)


def grade(score: float) -> str:
    for limit, g in ((80, "A"), (65, "B"), (50, "C"), (35, "D")):
        if score >= limit:
            return g
    return "E"


def compute_health(kpis: KPIs, equipment: list[Equipment], a: Assumptions,
                   today: int | None = None) -> HealthScore:
    comps = {
        "Enerji yoğunluğu": _ratio_score(kpis.eui_kwh_m2, a.benchmark_eui_kwh_m2),
        "Karbon yoğunluğu": _ratio_score(kpis.carbon_kg_m2, a.benchmark_carbon_kg_m2),
        "Su yoğunluğu": _ratio_score(kpis.water_m3_m2, a.benchmark_water_m3_m2),
        "Ekipman durumu": _equipment_score(equipment, a.equipment_life_years, today),
    }
    w = a.health_weights
    total = sum(comps[k] * w[k] for k in comps)
    return HealthScore(total=round(total, 1),
                       components={k: (round(v, 1), w[k]) for k, v in comps.items()},
                       grade=grade(total))
