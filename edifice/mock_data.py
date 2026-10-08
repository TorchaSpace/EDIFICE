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
    """Kanıta dayalı varsayılan katalog. Oranlar etkilenen kalemde (elektrik ya da gaz) bina düzeyindeki tasarruftur;
    türetme `basis` alanında, kaynaklar `evidence.SOURCES` içinde. Yatırım maliyetleri doğrulanmış kaynaksızdır (varsayım)."""
    E, G = UtilityType.ELECTRICITY, UtilityType.GAS
    return [
        Opportunity("LED", "LED aydınlatma dönüşümü", "Aydınlatma", E, 0.065, 180,
                    "Floresan armatürlerin LED ve sensörle değişimi", 0.04, 0.105, ("PNNL24526", "EIA_OFFICE"), "ikincil",
                    "Aydınlatma ofis enerjisinin ~%12'si (EIA) ≈ elektriğin %17'si (elektrik payı ~%70 varsayımı); LED tasarrufu aydınlatma "
                    "enerjisinde %24-61, ort. %37 (PNNL-24526); kontrolle tahmini %62 → elektrikte %4-10,5."),
        Opportunity("CHILLER", "Yüksek verimli chiller", "HVAC", E, 0.04, 450,
                    "Eski chiller'ların yüksek COP'lu yenileriyle değişimi", 0.02, 0.07, ("CHILLER_CASES", "EIA_OFFICE"), "ikincil",
                    "Soğutma ofis enerjisinde ≤%8 (EIA) ≈ elektriğin ≤%11; soğutucu değişiminde rapor edilen enerji tasarrufu %20-35 "
                    "(satıcı vaka çalışmaları) → elektrikte %2-4; sıcak iklimde soğutma payı yüksekse üst sınır %7."),
        Opportunity("VFD", "Fan/pompa hız kontrolü (VFD)", "HVAC", E, 0.07, 90,
                    "Sürücü ekleyerek fan ve pompa tüketimini azaltma", 0.04, 0.11, ("SCHIBUOLA2018", "ASHRAE_VFD", "EIA_OFFICE"), "ikincil",
                    "Havalandırma ofis enerjisinin ~%20'si (EIA) ≈ elektriğin %29'u; fan+pompa tasarrufu %38,9'a kadar (Schibuola 2018), "
                    "saha gerçekleşmesi idealin ~%40'ına inebilir (ASHRAE 2016) → %15-39 → elektrikte %4-11."),
        Opportunity("ENVELOPE", "Çatı ve cephe yalıtımı", "Bina Kabuğu", G, 0.15, 600,
                    "Isıtma yükünü azaltan kabuk iyileştirmesi", 0.08, 0.21, ("ORNL_ENVELOPE",), "ikincil",
                    "Kabuk iyileştirmesinde ölçülen normalize ısıtma tasarrufu %12-21 (LBL, konut) ve tipik %10-20; ölçülen tasarruf "
                    "çoğunlukla tahminin ~yarısı (ORNL) → temkinli %15. Ofis verisi değil."),
        Opportunity("BOILER", "Yoğuşmalı kazan", "HVAC", G, 0.12, 220,
                    "Eski kazanın yoğuşmalı kazanla değişimi", 0.07, 0.21, ("MNCEE_BOILER",), "ikincil",
                    "Nominal verimi %70-82 olan eski kazandan, ölçülen ortalama %88,6'ya (MnCEE, 12 bina) geçişte yakıt tasarrufu "
                    "1-η_eski/η_yeni = %7-21 (η=%78 için %12). Gazın ısıtmaya gittiği varsayımı."),
    ]
