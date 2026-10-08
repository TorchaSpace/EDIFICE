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


# Ekipman türüne göre tipik hizmet ömrü (yıl): ASHRAE çizelgelerinin ikincil aktarımlarının orta değerleri (evidence.ASHRAE_LIFE)
SERVICE_LIFE = [(("chiller", "soğutma grubu", "soğutucu"), 20), (("kazan", "boiler"), 25), (("santral", "ahu"), 20),
                (("pompa",), 15), (("soğutma kulesi",), 20)]


def service_life(name: str, default: int) -> int:
    n = name.lower()
    for words, years in SERVICE_LIFE:
        if any(w in n for w in words):
            return years
    return default


def _equipment_score(equipment: list[Equipment], life: int, today: int | None = None) -> float:
    if not equipment:
        return 50.0
    today = today or date.today().year
    scores = []
    for e in equipment:
        age_score = max(0.0, 1 - (today - e.year_installed) / service_life(e.name, life))
        cond_score = (e.condition - 1) / 4
        scores.append(100 * (0.4 * age_score + 0.6 * cond_score))
    return sum(scores) / len(scores)


def grade(score: float) -> str:
    for limit, g in ((80, "A"), (65, "B"), (50, "C"), (35, "D")):
        if score >= limit:
            return g
    return "E"


def compute_health(kpis: KPIs, equipment: list[Equipment], a: Assumptions,
                   today: int | None = None, use_type: str = "Ofis") -> HealthScore:
    comps = {
        "Enerji yoğunluğu": _ratio_score(kpis.eui_kwh_m2, a.benchmark_for(use_type)),
        "Karbon yoğunluğu": _ratio_score(kpis.carbon_kg_m2, a.carbon_benchmark_for(use_type)),
        "Su yoğunluğu": _ratio_score(kpis.water_m3_m2, a.benchmark_water_m3_m2),
        "Ekipman durumu": _equipment_score(equipment, a.equipment_life_years, today),
    }
    w = a.health_weights
    total = sum(comps[k] * w[k] for k in comps)
    return HealthScore(total=round(total, 1),
                       components={k: (round(v, 1), w[k]) for k, v in comps.items()},
                       grade=grade(total))


def score_range(kpis: KPIs, equipment: list[Equipment], a: Assumptions, use_type: str = "Ofis",
                today: int | None = None, draws: int = 400) -> tuple[float, float, float]:
    """Ağırlık duyarlılığı (OECD/JRC bileşik gösterge önerisi): her ağırlığı ±%50 değiştirerek
    skorun (%5, %95) aralığını ve eşit ağırlıklı skoru döndürür. -> (alt, üst, eşit_ağırlık)."""
    import random
    base = compute_health(kpis, equipment, a, today, use_type)
    comps = {k: v[0] for k, v in base.components.items()}
    rng = random.Random(7)
    scores = []
    for _ in range(draws):
        w = {k: a.health_weights[k] * (1 + rng.uniform(-0.5, 0.5)) for k in comps}
        tot = sum(w.values())
        scores.append(sum(comps[k] * w[k] / tot for k in comps))
    scores.sort()
    equal = sum(comps.values()) / len(comps)
    return round(scores[int(0.05 * draws)], 1), round(scores[int(0.95 * draws) - 1], 1), round(equal, 1)
