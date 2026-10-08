import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from edifice.db import Store
from edifice.ui.main_window import MainWindow
from edifice.ui.report_pdf import build_pdf
from edifice.validation import build_from_inputs

INFO = dict(name="Çok Uzun Bir Bina Adı " * 4, address="", use_type="Ofis", floor_area_m2=800, year_built=1990,
            floors=2, occupants=0)


def _single_year_project(store):
    rows = [["30000", "", "9000", "", "70", ""] for _ in range(12)]
    b, readings, eq = build_from_inputs(INFO, {2025: rows}, [], 2025)
    bid = store.save_building(b, readings, eq)
    return store.load_project(bid)


def test_single_year_building_renders_everywhere(tmp_path):
    QApplication.instance() or QApplication([])
    store = Store(":memory:")
    store.seed_demo()
    p = _single_year_project(store)
    assert p.previous_year() is None and p.yoy() == {}
    w = MainWindow(p, store)
    for i in range(len(w.pages)):
        w.select(i)
    out = tmp_path / "r.pdf"
    build_pdf(p, [], str(out))
    assert out.stat().st_size > 5000


def test_no_equipment_and_no_scenario_do_not_crash():
    p = Store(":memory:")
    p.seed_demo()
    proj = _single_year_project(p)
    assert 0 <= proj.health().total <= 100
    s = proj.scenario([])
    assert s.annual_saving == 0 and s.payback_years == float("inf")
