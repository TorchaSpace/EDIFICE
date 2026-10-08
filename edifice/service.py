"""UI ile motor arasındaki tek giriş noktası: tüm analizi tek çağrıda üretir."""
from __future__ import annotations

from dataclasses import dataclass

from . import mock_data
from .engine.health import compute_health
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

    @classmethod
    def mock(cls) -> "Project":
        return cls(mock_data.building(), mock_data.utility_readings(),
                   mock_data.equipment(), mock_data.opportunities(), Assumptions())

    @property
    def year(self) -> int:
        return latest_full_year(self.readings)

    def kpis(self) -> KPIs:
        return compute_kpis(self.building, self.readings, self.assumptions, self.year)

    def health(self) -> HealthScore:
        return compute_health(self.kpis(), self.equipment, self.assumptions)

    def prices(self) -> dict:
        return unit_prices(self.readings, self.year)

    def opportunity_results(self) -> list[OpportunityResult]:
        return evaluate_all(self.opportunities, self.building, self.kpis(),
                            self.prices(), self.assumptions)

    def scenario(self, codes: list[str]) -> ScenarioResult:
        sel = [o for o in self.opportunities if o.code in codes]
        return run_scenario(sel, self.building, self.kpis(), self.prices(), self.assumptions)
