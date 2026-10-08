import pytest

from edifice.db import Store
from edifice.validation import ValidationError, build_from_inputs, parse_number

INFO = dict(name="Test Bina", address="Ankara", use_type="Ofis", floor_area_m2=1000, year_built=2005,
            floors=4, occupants=50)


def grid(e=50000, g=20000, w=100):
    return [[str(e), "", str(g), "", str(w), ""] for _ in range(12)]


def test_parse_number_formats():
    assert parse_number("1.234,5") == 1234.5
    assert parse_number("1234,5") == 1234.5
    assert parse_number("1234.5") == 1234.5
    assert parse_number("1.234") == 1234
    assert parse_number("  ") is None
    with pytest.raises(ValueError):
        parse_number("abc")


def test_build_ok_and_default_tariff_for_blank_cost():
    b, readings, eq = build_from_inputs(INFO, {2025: grid()}, [], 2025)
    assert b.name == "Test Bina" and len(readings) == 36
    assert all(r.cost > 0 for r in readings)


def test_validation_collects_errors():
    bad = dict(INFO, name="", floor_area_m2=0)
    with pytest.raises(ValidationError) as e:
        build_from_inputs(bad, {2025: grid(e=0)}, [], 2025)
    msgs = " ".join(e.value.errors)
    assert "Bina adı" in msgs and "alan" in msgs and "Elektrik kWh" in msgs


def test_missing_base_year():
    with pytest.raises(ValidationError):
        build_from_inputs(INFO, {2025: [["", "", "", "", "", ""]] * 12}, [], 2025)


def test_db_roundtrip_and_delete():
    from edifice.models import Equipment
    store = Store(":memory:")
    b, readings, _ = build_from_inputs(INFO, {2025: grid(), 2024: grid(55000)}, [], 2025)
    bid = store.save_building(b, readings, [Equipment("HVAC", "Chiller", 2010, 3)])
    p = store.load_project(bid)
    assert p.building.name == "Test Bina" and len(p.readings) == 72 and p.year == 2025
    assert p.kpis().electricity_kwh == 50000 * 12 and p.yoy()["energy"] < 0
    assert len(p.equipment) == 1
    store.delete_building(bid)
    assert store.count() == 0


def test_settings_roundtrip_and_effect_on_health():
    store = Store(":memory:")
    bid = store.seed_demo()
    base = store.load_project(bid).health().total
    a = store.load_assumptions()
    a.health_weights = {"Enerji yoğunluğu": 1.0, "Karbon yoğunluğu": 0.0, "Su yoğunluğu": 0.0, "Ekipman durumu": 0.0}
    a.benchmark_eui_kwh_m2 = 400
    store.save_assumptions(a)
    p = store.load_project(bid)
    assert p.assumptions.benchmark_eui_kwh_m2 == 400 and p.health().total != base
    opps = store.load_opportunities()
    opps[0].saving_pct = 0.5
    store.save_opportunities(opps)
    assert store.load_project(bid).opportunities[0].saving_pct == 0.5
    store.reset_settings()
    assert store.load_project(bid).assumptions.benchmark_eui_kwh_m2 == 150


def test_update_building():
    store = Store(":memory:")
    bid = store.seed_demo()
    p = store.load_project(bid)
    p.building.name = "Yeni Ad"
    store.update_building(bid, p.building, p.readings[:36], [])
    q = store.load_project(bid)
    assert q.building.name == "Yeni Ad" and len(q.readings) == 36 and q.equipment == []
