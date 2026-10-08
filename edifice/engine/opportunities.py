"""Dönüşüm önerileri ve senaryo hesabı.

Aynı kalemi etkileyen önerilerde tasarruflar çarpımsal birleşir
(1 - (1-s1)(1-s2)...), böylece toplam %100'ü aşmaz.
"""
from __future__ import annotations

from dataclasses import replace

from .relevance import assess
from ..models import (Assumptions, Building, KPIs, Opportunity, OpportunityResult,
                      ScenarioResult, UtilityType)


def evaluate_opportunity(opp: Opportunity, building: Building, kpis: KPIs,
                         prices: dict, a: Assumptions) -> OpportunityResult:
    base = kpis.electricity_kwh if opp.affects == UtilityType.ELECTRICITY else kpis.gas_kwh
    saved_kwh = base * opp.saving_pct
    saved_carbon = saved_kwh * a.emission_factor_kg_per_kwh[opp.affects]
    saving = saved_kwh * prices[opp.affects]
    capex = opp.capex_per_m2 * building.floor_area_m2
    payback = capex / saving if saving > 0 else float("inf")
    return OpportunityResult(opp, saved_kwh, saved_carbon, saving, capex, payback)


def unit_prices(readings, year: int) -> dict:
    prices = {}
    for u in (UtilityType.ELECTRICITY, UtilityType.GAS):
        rows = [r for r in readings if r.utility == u and r.year == year]
        cons = sum(r.consumption for r in rows)
        prices[u] = sum(r.cost for r in rows) / cons if cons else 0.0
    return prices


_FIT_WEIGHT = {"high": 0.6, "medium": 0.85, "unknown": 1.0, "low": 1.5}


def evaluate_all(opps, building, kpis, prices, a, equipment=()) -> list[OpportunityResult]:
    """Uygun olanlar önce; aralarında geri ödeme süresine, ekipman önceliği ağırlıklandırılarak sıralanır."""
    results = []
    for o in opps:
        r = evaluate_opportunity(o, building, kpis, prices, a)
        r.fit, r.reason = assess(o.code, list(equipment), a.equipment_life_years)
        results.append(r)
    def key(r):
        if r.fit == "none":
            return (1, r.payback_years)
        return (0, r.payback_years * _FIT_WEIGHT[r.fit])
    return sorted(results, key=key)


def run_scenario(selected: list[Opportunity], building: Building, current: KPIs,
                 prices: dict, a: Assumptions) -> ScenarioResult:
    remaining = {UtilityType.ELECTRICITY: 1.0, UtilityType.GAS: 1.0}
    capex = 0.0
    for o in selected:
        remaining[o.affects] *= (1 - o.saving_pct)
        capex += o.capex_per_m2 * building.floor_area_m2

    elec = current.electricity_kwh * remaining[UtilityType.ELECTRICITY]
    gas = current.gas_kwh * remaining[UtilityType.GAS]
    ef = a.emission_factor_kg_per_kwh
    carbon = elec * ef[UtilityType.ELECTRICITY] + gas * ef[UtilityType.GAS]
    energy_cost = (elec * prices[UtilityType.ELECTRICITY] + gas * prices[UtilityType.GAS])
    area = building.floor_area_m2
    target = replace(
        current, electricity_kwh=elec, gas_kwh=gas, total_energy_kwh=elec + gas,
        eui_kwh_m2=(elec + gas) / area, carbon_kg=carbon, carbon_kg_m2=carbon / area,
        energy_cost=energy_cost, total_cost=energy_cost + current.water_cost,
    )
    saving = current.total_cost - target.total_cost
    return ScenarioResult(
        selected=list(selected), current=current, target=target, capex=capex,
        annual_saving=saving,
        payback_years=capex / saving if saving > 0 else float("inf"),
        carbon_reduction_pct=1 - carbon / current.carbon_kg if current.carbon_kg else 0.0,
        energy_reduction_pct=1 - (elec + gas) / current.total_energy_kwh if current.total_energy_kwh else 0.0,
    )
