"""UI ile motor arasındaki tek giriş noktası: tüm analizi tek çağrıda üretir."""
from __future__ import annotations

from dataclasses import dataclass

from . import mock_data
from .engine.finance import FinanceResult, analyze
from .engine.health import compute_health, score_range
from .engine.optimizer import best_package
from .engine.rating import energy_class, percentile_worse_than
from .engine.kpi import compute_kpis, latest_full_year
from .engine.opportunities import evaluate_all, run_scenario, unit_prices
from .models import (Assumptions, Building, Equipment, HealthScore, KPIs, Opportunity,
                     OpportunityResult, ScenarioResult, UtilityReading)


@dataclass
class Project:
    building: Building
    readings: list[UtilityReading]
    equipment: list[Equipment]
    opportunities: list[Opportunity]
    assumptions: Assumptions
    building_id: int | None = None

    @classmethod
    def mock(cls) -> "Project":
        return cls(mock_data.building(), mock_data.utility_readings(),
                   mock_data.equipment(), mock_data.opportunities(), Assumptions())

    @property
    def year(self) -> int:
        return latest_full_year(self.readings)

    def kpis(self) -> KPIs:
        return compute_kpis(self.building, self.readings, self.assumptions, self.year)

    def kpis_for(self, year: int) -> KPIs:
        return compute_kpis(self.building, self.readings, self.assumptions, year)

    def previous_year(self) -> int | None:
        years = sorted({r.year for r in self.readings})
        prev = self.year - 1
        return prev if prev in years else None

    def yoy(self) -> dict:
        """Baz yıla göre bir önceki yıla kıyasla yüzde değişim (negatif = azalma)."""
        prev = self.previous_year()
        if prev is None:
            return {}
        a, b = self.kpis(), self.kpis_for(prev)
        def ch(x, y):
            return (x / y - 1) * 100 if y else 0.0
        return {"energy": ch(a.total_energy_kwh, b.total_energy_kwh), "carbon": ch(a.carbon_kg, b.carbon_kg),
                "water": ch(a.water_m3, b.water_m3), "electricity": ch(a.electricity_kwh, b.electricity_kwh),
                "gas": ch(a.gas_kwh, b.gas_kwh), "cost": ch(a.total_cost, b.total_cost)}

    def monthly(self, year: int, utility) -> list[float]:
        out = [0.0] * 12
        for r in self.readings:
            if r.year == year and r.utility == utility:
                out[r.month - 1] += r.consumption
        return out

    def monthly_cost(self, year: int) -> list[float]:
        from .models import UtilityType
        out = [0.0] * 12
        for r in self.readings:
            if r.year == year and r.utility != UtilityType.WATER:
                out[r.month - 1] += r.cost
        return out

    def monthly_carbon(self, year: int) -> list[float]:
        from .models import UtilityType
        ef = self.assumptions.emission_factor_kg_per_kwh
        e, g = self.monthly(year, UtilityType.ELECTRICITY), self.monthly(year, UtilityType.GAS)
        return [a * ef[UtilityType.ELECTRICITY] + b * ef[UtilityType.GAS] for a, b in zip(e, g)]

    def health(self) -> HealthScore:
        return compute_health(self.kpis(), self.equipment, self.assumptions, use_type=self.building.use_type)

    def health_range(self) -> tuple[float, float, float]:
        return score_range(self.kpis(), self.equipment, self.assumptions, self.building.use_type)

    def prices(self) -> dict:
        return unit_prices(self.readings, self.year)

    def opportunity_results(self) -> list[OpportunityResult]:
        return evaluate_all(self.opportunities, self.building, self.kpis(),
                            self.prices(), self.assumptions, self.equipment)

    def rating(self) -> dict:
        k, a = self.kpis(), self.assumptions
        bench = a.benchmark_for(self.building.use_type)
        return {"class": energy_class(k.eui_kwh_m2, bench), "percentile": percentile_worse_than(k.eui_kwh_m2, bench),
                "eui": k.eui_kwh_m2, "benchmark": bench}

    def rating_after(self, codes: list[str]) -> str:
        s = self.scenario(codes)
        return energy_class(s.target.eui_kwh_m2, self.assumptions.benchmark_for(self.building.use_type))

    def applicable_codes(self) -> list[str]:
        return [r.opportunity.code for r in self.opportunity_results() if r.fit != "none"]

    def finance(self, codes: list[str], mode: str = "typ", assumptions=None) -> FinanceResult:
        s = self.scenario(codes, mode)
        return analyze(s.capex, s.annual_saving, assumptions or self.assumptions)

    def sensitivity(self, codes: list[str]) -> list[tuple[str, FinanceResult]]:
        """Duyarlılık analizi (AB 244/2012 metodolojisinin istediği gibi): tasarruf aralığı, iskonto, fiyat artışı, tasarruf kaybı."""
        from dataclasses import replace
        a = self.assumptions
        rows = [("Beklenen (tipik değerler)", self.finance(codes)),
                ("Düşük tasarruf (literatür alt sınırı)", self.finance(codes, "low")),
                ("Yüksek tasarruf (literatür üst sınırı)", self.finance(codes, "high")),
                (f"İskonto oranı +2 puan (%{a.discount_rate * 100 + 2:.0f})", self.finance(codes, assumptions=replace(a, discount_rate=a.discount_rate + 0.02))),
                ("Enerji fiyatı reel artışı %0", self.finance(codes, assumptions=replace(a, energy_escalation=0.0))),
                ("Tasarruf kaybı %3/yıl", self.finance(codes, assumptions=replace(a, savings_degradation=0.03)))]
        return rows

    def best_package(self, budget: float):
        ok = {r.opportunity.code for r in self.opportunity_results() if r.fit != "none"}
        opps = [o for o in self.opportunities if o.code in ok]
        return best_package(opps, self.building, self.kpis(), self.prices(), self.assumptions, budget)

    def opportunity_ranges(self) -> dict:
        """Her öneri için (düşük, yüksek) yıllık tasarruf ₺ (literatür aralığı)."""
        from .engine.opportunities import evaluate_opportunity
        k, pr, a = self.kpis(), self.prices(), self.assumptions
        return {o.code: (evaluate_opportunity(o, self.building, k, pr, a, "low").annual_saving,
                         evaluate_opportunity(o, self.building, k, pr, a, "high").annual_saving) for o in self.opportunities}

    def scenario(self, codes: list[str], mode: str = "typ") -> ScenarioResult:
        sel = [o for o in self.opportunities if o.code in codes]
        return run_scenario(sel, self.building, self.kpis(), self.prices(), self.assumptions, mode)
