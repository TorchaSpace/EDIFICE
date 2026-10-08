"""Pilot bina için mock veri (gerçek veri gelene kadar)."""
from __future__ import annotations

import math

from .models import Building, Equipment, Opportunity, UtilityReading, UtilityType

ELEC_TARIFF = 4.2   # TRY/kWh
GAS_TARIFF = 1.3    # TRY/kWh
WATER_TARIFF = 38.0  # TRY/m3


def building() -> Building:
    return Building(
        name="Pilot Ofis Binası",
        address="İstanbul",
        use_type="Ofis",
        floor_area_m2=6000,
        year_built=1998,
        floors=8,
        occupants=320,
    )


def utility_readings() -> list[UtilityReading]:
    out = []
    for year in (2024, 2025):
        growth = 1.0 if year == 2024 else 0.97
        for m in range(1, 13):
            winter = max(0.0, math.cos((m - 1) / 12 * 2 * math.pi))  # ocak=1
            summer = max(0.0, -math.cos((m - 1) / 12 * 2 * math.pi))  # temmuz=1
            elec = (62000 + 18000 * summer + 6000 * winter) * growth
            gas = (8000 + 72000 * winter) * growth
            water = (330 + 40 * summer) * growth
            out.append(UtilityReading(UtilityType.ELECTRICITY, year, m, round(elec), round(elec * ELEC_TARIFF)))
            out.append(UtilityReading(UtilityType.GAS, year, m, round(gas), round(gas * GAS_TARIFF)))
            out.append(UtilityReading(UtilityType.WATER, year, m, round(water), round(water * WATER_TARIFF)))
    return out


def equipment() -> list[Equipment]:
    return [
        Equipment("HVAC", "Su soğutmalı chiller (2 adet)", 2005, 2, "Düşük COP"),
        Equipment("HVAC", "Doğalgazlı kazan", 2008, 3),
        Equipment("HVAC", "Klima santralleri", 2010, 3),
        Equipment("Aydınlatma", "Floresan armatürler", 2000, 2, "LED'e dönüşüme uygun"),
        Equipment("Bina Kabuğu", "Çift cam doğrama", 1998, 2, "Yalıtım zayıf"),
        Equipment("Bina Kabuğu", "Çatı yalıtımı", 1998, 1),
    ]


def opportunities() -> list[Opportunity]:
    E, G = UtilityType.ELECTRICITY, UtilityType.GAS
    return [
        Opportunity("LED", "LED aydınlatma dönüşümü", "Aydınlatma", E, 0.12, 180,
                    "Floresan armatürlerin LED ve sensörle değişimi"),
        Opportunity("CHILLER", "Yüksek verimli chiller", "HVAC", E, 0.15, 450,
                    "Eski chiller'ların yüksek COP'lu yenileriyle değişimi"),
        Opportunity("VFD", "Fan/pompa hız kontrolü (VFD)", "HVAC", E, 0.06, 90,
                    "Sürücü ekleyerek fan ve pompa tüketimini azaltma"),
        Opportunity("ENVELOPE", "Çatı ve cephe yalıtımı", "Bina Kabuğu", G, 0.22, 600,
                    "Isıtma yükünü azaltan kabuk iyileştirmesi"),
        Opportunity("BOILER", "Yoğuşmalı kazan", "HVAC", G, 0.10, 220,
                    "Eski kazanın yoğuşmalı kazanla değişimi"),
    ]
