import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTableWidgetItem

from edifice.ui.building_dialog import make_item

from edifice.db import Store
from edifice.service import Project
from edifice.ui.building_dialog import BuildingDialog
from edifice.ui.main_window import MainWindow
from edifice.ui.report import build_report


def _app():
    return QApplication.instance() or QApplication([])


def test_window_builds_and_scenario_updates():
    _app()
    p = Project.mock()
    w = MainWindow(p)
    sc = w.pages[3][1]
    sc.checks["LED"].setChecked(True)
    assert sc.selected_codes() == ["LED"]
    assert "EDIFI" in build_report(p, ["LED"])


def test_add_building_dialog_flow():
    _app()
    store = Store(":memory:")
    store.seed_demo()
    w = MainWindow(store.load_project(store.latest_id()), store)
    d = BuildingDialog(w)
    d.save()
    assert d.result_data is None and "Bina adı" in d.error.text()
    d.name.setText("Yeni Bina")
    d.area.setValue(2500)
    for r in range(12):
        for c, v in enumerate(["40000", "", "15000", "", "90", ""]):
            d.grids["base"].setItem(r, c, make_item(v, c))
    d.add_equipment_row()
    d.eq.item(0, 1).setText("Chiller")
    d.save()
    assert d.result_data is not None
    building, readings, equipment = d.result_data
    bid = store.save_building(building, readings, equipment)
    w.set_project(store.load_project(bid))
    assert w.project.building.name == "Yeni Bina" and store.count() == 2
