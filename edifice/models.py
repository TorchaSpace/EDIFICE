"""Alan modelleri. Ham veri, hesaplanan veri ve senaryo verisi ayrı tutulur."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class UtilityType(str, Enum):
    ELECTRICITY = "electricity"  # kWh
    GAS = "gas"                  # kWh (m3 ise import sırasında çevrilir)
    WATER = "water"              # m3


UTILITY_UNITS = {
    UtilityType.ELECTRICITY: "kWh",
    UtilityType.GAS: "kWh",
    UtilityType.WATER: "m³",
}


# ---- Ham veri -------------------------------------------------------------

@dataclass
class Building:
    name: str
    address: str
    use_type: str
    floor_area_m2: float
    year_built: int
    floors: int
    occupants: int


@dataclass
class UtilityReading:
    utility: UtilityType
    year: int
    month: int
    consumption: float   # UTILITY_UNITS birimiyle
    cost: float          # TRY


@dataclass
class Equipment:
    category: str        # HVAC, Aydınlatma, Bina Kabuğu
    name: str
    year_installed: int
    condition: int       # 1 (kötü) - 5 (çok iyi)
    notes: str = ""


# ---- Varsayımlar (hesap girdileri) -----------------------------------------

@dataclass
class Assumptions:
    emission_factor_kg_per_kwh: dict = field(default_factory=lambda: {
        UtilityType.ELECTRICITY: 0.43,
        UtilityType.GAS: 0.20,
    })
    # Bina kullanım tipine göre kıyas değerleri (placeholder, doğrulanmalı)
    benchmark_eui_kwh_m2: float = 150.0        # elektrik + gaz
    benchmark_carbon_kg_m2: float = 45.0
    benchmark_water_m3_m2: float = 0.9
    target_eui_kwh_m2: float = 100.0
    health_weights: dict = field(default_factory=lambda: {
        "Enerji yoğunluğu": 0.35, "Karbon yoğunluğu": 0.25, "Su yoğunluğu": 0.10, "Ekipman durumu": 0.30})
    default_tariffs: dict = field(default_factory=lambda: {
        UtilityType.ELECTRICITY: 4.2, UtilityType.GAS: 1.3, UtilityType.WATER: 38.0})  # TRY/kWh, TRY/kWh, TRY/m3
    equipment_life_years: int = 20
    discount_rate: float = 0.08                # reel iskonto oranı (enflasyondan arındırılmış)
    energy_escalation: float = 0.03            # reel enerji fiyat artışı (yıllık)
    horizon_years: int = 15                    # finansal analiz süresi
    savings_degradation: float = 0.005         # tasarrufun yıllık azalması


# ---- Hesaplanan veri ------------------------------------------------------

@dataclass
class KPIs:
    electricity_kwh: float
    gas_kwh: float
    water_m3: float
    total_energy_kwh: float
    eui_kwh_m2: float
    carbon_kg: float
    carbon_kg_m2: float
    water_m3_m2: float
    energy_cost: float
    water_cost: float
    total_cost: float


@dataclass
class HealthScore:
    total: float
    components: dict     # ad -> (puan 0-100, ağırlık)
    grade: str


@dataclass
class Opportunity:
    code: str
    name: str
    category: str
    affects: UtilityType
    saving_pct: float        # etkilenen kalemde yıllık tasarruf oranı (0-1)
    capex_per_m2: float      # TRY / m²
    description: str = ""


@dataclass
class OpportunityResult:
    opportunity: Opportunity
    saved_kwh: float
    saved_carbon_kg: float
    annual_saving: float
    capex: float
    payback_years: float
    fit: str = "unknown"          # high | medium | low | none | unknown
    reason: str = ""


@dataclass
class ScenarioResult:
    selected: list
    current: KPIs
    target: KPIs
    capex: float
    annual_saving: float
    payback_years: float
    carbon_reduction_pct: float
    energy_reduction_pct: float
