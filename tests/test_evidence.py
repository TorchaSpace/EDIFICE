import math

from edifice.db import Store
from edifice.engine.health import score_range, service_life
from edifice.evidence import KBTU_FT2_TO_KWH_M2, LEVELS, SOURCES, parameter_rows
from edifice.models import Assumptions, UtilityType


def test_registry_integrity():
    assert all(s["level"] in LEVELS and s["url"].startswith("http") and s["cite"] for s in SOURCES.values())
    a = Assumptions()
    for group, name, value, srcs, level, note in parameter_rows(a):
        assert level in LEVELS and all(x in SOURCES for x in srcs), (name, srcs)
    store = Store(":memory:")
    for o in store.load_opportunities():
        assert o.evidence_level in LEVELS and all(x in SOURCES for x in o.evidence), o.code
        assert o.saving_low <= o.saving_pct <= o.saving_high and o.basis


def test_energy_star_conversion_matches_published_values():
    a = Assumptions()
    assert math.isclose(KBTU_FT2_TO_KWH_M2, 3.15459, rel_tol=1e-9)
    assert math.isclose(a.benchmark_for("Ofis"), 52.9 * 3.15459, abs_tol=0.1)       # 166.9
    assert math.isclose(a.benchmark_for("Hastane"), 234.3 * 3.15459, abs_tol=0.1)   # 739.1
    assert a.benchmark_for("Sanayi") == a.benchmark_eui_kwh_m2                      # kaynakta veri yok -> yedek


def test_emission_factors_follow_sources():
    ef = Assumptions().emission_factor_kg_per_kwh
    assert ef[UtilityType.ELECTRICITY] == 0.437
    assert math.isclose(ef[UtilityType.GAS], 56.1 * 0.0036, abs_tol=0.0005)         # IPCC 56,1 kg/GJ


def test_boiler_range_matches_efficiency_arithmetic():
    from edifice.mock_data import opportunities
    b = {o.code: o for o in opportunities()}["BOILER"]
    assert math.isclose(b.saving_high, 1 - 0.70 / 0.886, abs_tol=0.005)
    assert math.isclose(b.saving_low, 1 - 0.82 / 0.886, abs_tol=0.005)
    assert math.isclose(b.saving_pct, 1 - 0.78 / 0.886, abs_tol=0.005)


def test_scenario_modes_and_sensitivity_ordering():
    store = Store(":memory:")
    p = store.load_project(store.seed_demo())
    codes = ["LED", "VFD", "BOILER"]
    low, typ, high = (p.finance(codes, m).npv for m in ("low", "typ", "high"))
    assert low < typ < high
    rows = dict(p.sensitivity(codes))
    assert len(rows) == 6 and rows["Beklenen (tipik değerler)"].npv == typ
    assert rows["Enerji fiyatı reel artışı %0"].npv < typ and rows["Tasarruf kaybı %3/yıl"].npv < typ


def test_health_score_range_and_service_life():
    store = Store(":memory:")
    p = store.load_project(store.seed_demo())
    lo, hi, equal = p.health_range()
    assert lo <= p.health().total <= hi and 0 <= lo and hi <= 100
    assert service_life("Su soğutmalı chiller", 20) == 20 and service_life("Doğalgazlı kazan", 20) == 25
    assert service_life("Sirkülasyon pompası", 20) == 15 and service_life("Bilinmeyen cihaz", 17) == 17


def test_old_saved_defaults_are_reset_once():
    store = Store(":memory:")
    store.conn.execute("DELETE FROM settings WHERE key='evidence_version'")
    store.conn.execute("INSERT OR REPLACE INTO settings VALUES ('assumptions', '{}')")
    store.conn.commit()
    store._migrate_evidence_defaults()
    assert store.conn.execute("SELECT COUNT(*) FROM settings WHERE key='assumptions'").fetchone()[0] == 0
