import csv
from pathlib import Path

import pytest

from edifice.bulk_import import ImportResult, merge_readings, parse_file, parse_number, parse_period, sample_csv
from edifice.models import UtilityType
from edifice.service import Project

TARIFFS = {UtilityType.ELECTRICITY: 4.0, UtilityType.GAS: 1.0, UtilityType.WATER: 30.0}


@pytest.mark.parametrize("raw,val", [("1.234,56", 1234.56), ("1,234.56", 1234.56), ("1234,5", 1234.5), ("1.234", 1234.0),
                                      ("12,5", 12.5), ("1,234", 1234.0), (" 7 ", 7.0), ("", None), ("abc", None), (3.5, 3.5), ("-4,2", -4.2)])
def test_parse_number_variants(raw, val):
    assert parse_number(raw) == val


@pytest.mark.parametrize("raw,per", [("2025-03", (2025, 3)), ("03/2025", (2025, 3)), ("Mart 2025", (2025, 3)), ("Şubat 2024", (2024, 2)),
                                      ("01.03.2025", (2025, 3)), ("Mar-2025", (2025, 3)), ("Ocak 2023", (2023, 1)), ("???", None)])
def test_parse_period_variants(raw, per):
    assert parse_period(raw) == per


def _write(tmp_path, name, text, enc="utf-8-sig"):
    p = tmp_path / name
    p.write_bytes(text.encode(enc))
    return str(p)


def test_wide_csv_turkish_formats(tmp_path):
    txt = "Yıl;Ay;Elektrik kWh;Elektrik ₺;Doğalgaz kWh;Su m³\n2025;1;\"12.500,5\";\"52.502\";8000;310\n2025;2;11000;;7000;300\n"
    res = parse_file(_write(tmp_path, "a.csv", txt), TARIFFS)
    assert res.rows_used == 2 and len(res.readings) == 6
    e1 = next(r for r in res.readings if r.utility == UtilityType.ELECTRICITY and r.month == 1)
    assert e1.consumption == 12500.5 and e1.cost == 52502
    e2 = next(r for r in res.readings if r.utility == UtilityType.ELECTRICITY and r.month == 2)
    assert e2.cost == pytest.approx(11000 * 4.0)           # boş tutar tarifeden
    assert any("tarifeyle tahmin" in w for w in res.warnings)


def test_cp1254_encoding_and_period_column(tmp_path):
    txt = "Dönem,Elektrik kWh,Doğalgaz kWh\nMart 2025,1000,500\nNisan 2025,900,400\n"
    res = parse_file(_write(tmp_path, "b.csv", txt, "cp1254"), TARIFFS)
    assert sorted({(r.year, r.month) for r in res.readings}) == [(2025, 3), (2025, 4)]


def test_long_format(tmp_path):
    txt = "Tarih;Tür;Miktar;Tutar\n2025-01;Elektrik;1000;4000\n2025-01;Doğalgaz;500;500\n2025-01;Su;20;600\n"
    res = parse_file(_write(tmp_path, "c.csv", txt), TARIFFS)
    assert {r.utility for r in res.readings} == set(UtilityType) and len(res.readings) == 3


def test_bad_rows_are_reported_not_fatal(tmp_path):
    txt = "Yıl;Ay;Elektrik kWh\n2025;1;100\n2025;13;50\n2025;2;-5\n2025;3;300\n2025;3;310\n"
    res = parse_file(_write(tmp_path, "d.csv", txt), TARIFFS)
    assert {(r.month) for r in res.readings} == {1, 3}                 # ay 13 ve negatif atıldı
    assert next(r for r in res.readings if r.month == 3).consumption == 310     # tekrarda son değer
    msgs = " ".join(res.warnings)
    assert "negatif" in msgs and "tekrar" in msgs and "dönem anlaşılamadı" in msgs


def test_unrecognized_file_gives_helpful_message(tmp_path):
    res = parse_file(_write(tmp_path, "e.csv", "a;b;c\n1;2;3\n"), TARIFFS)
    assert not res.readings and "Başlık satırı tanınamadı" in res.warnings[0]


def test_xlsx_and_sample_roundtrip(tmp_path):
    p = Project.mock()
    out = sample_csv(str(tmp_path / "ornek.csv"), p.readings)
    res = parse_file(out, TARIFFS)
    year = p.year
    for u in UtilityType:
        got = sorted((r.month, round(r.consumption)) for r in res.readings if r.utility == u)
        want = sorted((r.month, round(r.consumption)) for r in p.readings if r.utility == u and r.year == year)
        assert got == want
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["Yıl", "Ay", "Elektrik kWh", "Elektrik ₺"])
    ws.append([2025, 1, 1000, 4000])
    wb.save(tmp_path / "x.xlsx")
    assert len(parse_file(str(tmp_path / "x.xlsx"), TARIFFS).readings) == 1


def test_merge_replaces_and_adds():
    p = Project.mock()
    year = p.year
    res = ImportResult(readings=[r for r in p.readings if r.year == year and r.utility == UtilityType.GAS][:3])
    for r in res.readings:
        r.consumption += 1
    merged, added, replaced = merge_readings(p.readings, res.readings)
    assert replaced == 3 and added == 0 and len(merged) == len(p.readings)
