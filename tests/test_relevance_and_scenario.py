from edifice.db import Store
from edifice.engine.relevance import assess
from edifice.models import Equipment


def test_old_bad_chiller_is_high_priority():
    eq = [Equipment("HVAC", "Su soğutmalı chiller", 2000, 1)]
    assert assess("CHILLER", eq, today=2026)[0] == "high"


def test_new_led_is_not_applicable():
    eq = [Equipment("Aydınlatma", "LED armatürler", 2023, 5)]
    assert assess("LED", eq, today=2026)[0] == "none"


def test_no_equipment_is_unknown_and_missing_group_unknown():
    assert assess("LED", [])[0] == "unknown"
    assert assess("BOILER", [Equipment("HVAC", "Chiller", 2010, 3)])[0] == "unknown"


def test_ranking_puts_not_applicable_last_and_urgent_first():
    store = Store(":memory:")
    bid = store.seed_demo()
    p = store.load_project(bid)
    p.equipment = [Equipment("Aydınlatma", "LED armatürler", 2024, 5),
                   Equipment("HVAC", "Chiller", 1998, 1)]
    res = p.opportunity_results()
    assert res[-1].opportunity.code == "LED" and res[-1].fit == "none"
    assert res[0].fit in ("high", "unknown")


def test_scenario_persisted_per_building():
    store = Store(":memory:")
    a, b = store.seed_demo(), store.seed_demo()
    store.save_scenario(a, ["LED", "VFD"])
    assert store.load_scenario(a) == ["LED", "VFD"] and store.load_scenario(b) == []
    store.delete_building(a)
    assert store.load_scenario(a) == []
