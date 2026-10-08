"""Enerji, karbon ve maliyet KPI hesabı. UI'dan bağımsız."""
from __future__ import annotations

from ..models import Assumptions, Building, KPIs, UtilityReading, UtilityType


def latest_full_year(readings: list[UtilityReading]) -> int:
    months: dict[int, set] = {}
    for r in readings:
        months.setdefault(r.year, set()).add(r.month)
    full = [y for y, m in months.items() if len(m) == 12]
    if not full:
        raise ValueError("12 aylık tam yıl verisi bulunamadı")
    return max(full)


def compute_kpis(building: Building, readings: list[UtilityReading],
                 assumptions: Assumptions, year: int | None = None) -> KPIs:
    year = year or latest_full_year(readings)
    rows = [r for r in readings if r.year == year]

    def total(u: UtilityType, attr: str = "consumption") -> float:
        return sum(getattr(r, attr) for r in rows if r.utility == u)

    elec, gas, water = (total(UtilityType.ELECTRICITY), total(UtilityType.GAS),
                        total(UtilityType.WATER))
    ef = assumptions.emission_factor_kg_per_kwh
    carbon = elec * ef[UtilityType.ELECTRICITY] + gas * ef[UtilityType.GAS]
    energy = elec + gas
    energy_cost = total(UtilityType.ELECTRICITY, "cost") + total(UtilityType.GAS, "cost")
    water_cost = total(UtilityType.WATER, "cost")
    area = building.floor_area_m2
    return KPIs(
        electricity_kwh=elec, gas_kwh=gas, water_m3=water,
        total_energy_kwh=energy, eui_kwh_m2=energy / area,
        carbon_kg=carbon, carbon_kg_m2=carbon / area, water_m3_m2=water / area,
        energy_cost=energy_cost, water_cost=water_cost,
        total_cost=energy_cost + water_cost,
    )


def monthly_series(readings: list[UtilityReading], utility: UtilityType) -> list[tuple[str, float]]:
    rows = sorted((r for r in readings if r.utility == utility), key=lambda r: (r.year, r.month))
    return [(f"{r.year}-{r.month:02d}", r.consumption) for r in rows]
