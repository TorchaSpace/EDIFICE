"""Bina Ekle formundan gelen ham metinleri doğrular ve modellere çevirir (UI'dan bağımsız)."""
from __future__ import annotations

import re
from datetime import date

from . import mock_data
from .models import Building, Equipment, UtilityReading, UtilityType

COLUMNS = [
    (UtilityType.ELECTRICITY, "Elektrik kWh", "Elektrik ₺"),
    (UtilityType.GAS, "Doğalgaz kWh", "Doğalgaz ₺"),
    (UtilityType.WATER, "Su m³", "Su ₺"),
]
DEFAULT_TARIFF = {UtilityType.ELECTRICITY: mock_data.ELEC_TARIFF, UtilityType.GAS: mock_data.GAS_TARIFF,
                  UtilityType.WATER: mock_data.WATER_TARIFF}
USE_TYPES = ["Ofis", "Konut", "Ticari / AVM", "Otel", "Hastane", "Okul", "Sanayi", "Karma"]
EQUIPMENT_CATEGORIES = ["HVAC", "Aydınlatma", "Bina Kabuğu"]
MONTH_NAMES = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül",
               "Ekim", "Kasım", "Aralık"]


class ValidationError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def parse_number(text: str) -> float | None:
    """'1.234,5', '1234,5', '1234.5', '1 234' gibi girdileri sayıya çevirir; boşsa None."""
    s = (text or "").strip().replace(" ", "").replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        raise ValueError(f"'{text}' sayı değil")


def _year_rows(year: int, rows: list[list[str]], label: str, errors: list[str], tariffs: dict):
    """12 satır x 6 sütun metin -> UtilityReading listesi. Tamamen boşsa None."""
    parsed, any_value = [], False
    for m, row in enumerate(rows, start=1):
        vals = []
        for c, text in enumerate(row):
            try:
                v = parse_number(text)
            except ValueError as e:
                errors.append(f"{label} · {MONTH_NAMES[m - 1]} · {COLUMNS[c // 2][1 + c % 2]}: “{text}” geçerli bir sayı değil")
                v = None
            if v is not None and v < 0:
                errors.append(f"{label} · {MONTH_NAMES[m - 1]}: değer negatif olamaz")
            vals.append(v)
            any_value = any_value or v is not None
        parsed.append(vals)
    if not any_value:
        return None
    readings = []
    for m, vals in enumerate(parsed, start=1):
        for i, (utility, cons_name, _) in enumerate(COLUMNS):
            cons, cost = vals[i * 2], vals[i * 2 + 1]
            if cons is None or cons <= 0:
                errors.append(f"{label} · {MONTH_NAMES[m - 1]} · {cons_name}: değer girilmeli (0'dan büyük)")
                continue
            if cost is None:
                cost = cons * tariffs[utility]  # fatura tutarı boşsa varsayılan tarife
            readings.append(UtilityReading(utility, year, m, cons, cost))
    return readings


def build_from_inputs(info: dict, grids: dict[int, list[list[str]]], equipment_rows: list[dict],
                      base_year: int, tariffs: dict | None = None):
    """info: ad/adres/kullanım/alan/yıl/kat/kişi. grids: {yıl: 12x6 metin}. -> (Building, readings, equipment)"""
    tariffs = tariffs or DEFAULT_TARIFF
    errors: list[str] = []
    name = (info.get("name") or "").strip()
    if not name:
        errors.append("Bina adı boş olamaz")
    area = info.get("floor_area_m2") or 0
    if area <= 0:
        errors.append("Brüt kullanım alanı (m²) 0'dan büyük olmalı")
    yb = int(info.get("year_built") or 0)
    if not 1800 <= yb <= date.today().year:
        errors.append(f"Yapım yılı 1800-{date.today().year} arasında olmalı")
    floors = int(info.get("floors") or 0)
    if floors < 1:
        errors.append("Kat sayısı en az 1 olmalı")

    readings: list[UtilityReading] = []
    base = _year_rows(base_year, grids.get(base_year, []), f"Baz yıl {base_year}", errors, tariffs)
    if base is None:
        errors.append(f"Baz yıl {base_year} için 12 aylık tüketim girilmeli")
    else:
        readings += base
    prev = _year_rows(base_year - 1, grids.get(base_year - 1, []), f"Önceki yıl {base_year - 1}", errors, tariffs)
    if prev:
        readings += prev

    equipment = []
    for i, r in enumerate(equipment_rows, start=1):
        if not (r.get("name") or "").strip():
            continue
        try:
            yi = int(r.get("year_installed") or 0)
        except ValueError:
            yi = 0
        if not 1900 <= yi <= date.today().year:
            errors.append(f"Ekipman {i} ({r['name'].strip()}): kurulum yılı geçersiz")
            continue
        equipment.append(Equipment(r.get("category") or EQUIPMENT_CATEGORIES[0], r["name"].strip(), yi,
                                   int(r.get("condition") or 3), (r.get("notes") or "").strip()))
    if errors:
        raise ValidationError(errors)
    building = Building(name=name, address=(info.get("address") or "").strip(),
                        use_type=info.get("use_type") or USE_TYPES[0], floor_area_m2=float(area),
                        year_built=yb, floors=floors, occupants=int(info.get("occupants") or 0))
    return building, readings, equipment
