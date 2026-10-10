import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QTableWidgetItem

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
    sc = w.sub["Mevcut vs Hedef"]
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
    d.eq.cellWidget(0, 1).inner.setText("Chiller")
    d.use_type.showPopup()
    d.use_type._popup.card.findChildren(type(d.use_type._popup.card.layout().itemAt(1).widget()))[1].click()
    assert d.use_type.currentIndex() == 1
    d.save()
    assert d.result_data is not None
    building, readings, equipment = d.result_data
    bid = store.save_building(building, readings, equipment)
    w.set_project(store.load_project(bid))
    assert w.project.building.name == "Yeni Bina" and store.count() == 2


def test_edit_building_and_settings_flow():
    _app()
    store = Store(":memory:")
    bid = store.seed_demo()
    w = MainWindow(store.load_project(bid), store)
    d = BuildingDialog(w, project=w.project)
    assert d.name.text() == "Demo Ofis Binası" and d.eq.rowCount() == len(w.project.equipment)
    d.name.setText("Düzenlenmiş")
    d.save()
    assert d.result_data is not None and d.result_data[0].name == "Düzenlenmiş"
    assert len(d.result_data[1]) == len(w.project.readings)
    store.update_building(bid, *d.result_data)
    w.set_project(store.load_project(bid))
    assert w.project.building.name == "Düzenlenmiş"
    sp = w.sub["Ayarlar"]
    sp.b_eui.setValue(400)
    sp.opp_widgets[0][2].setValue(30)
    sp.save()
    assert w.project.assumptions.benchmark_eui_kwh_m2 == 400
    assert w.project.opportunities[0].saving_pct == 0.3


def test_scenario_restored_after_reload():
    _app()
    store = Store(":memory:")
    bid = store.seed_demo()
    w = MainWindow(store.load_project(bid), store)
    w.sub["Mevcut vs Hedef"].checks["LED"].setChecked(True)
    w.set_project(store.load_project(bid))
    assert w.sub["Mevcut vs Hedef"].selected_codes() == ["LED"]


def test_pdf_report_generated(tmp_path):
    _app()
    from edifice.ui.report_pdf import build_pdf
    p = Project.mock()
    out = tmp_path / "r.pdf"
    build_pdf(p, ["LED", "CHILLER"], str(out))
    data = out.read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 5000


def test_excel_import_flow(tmp_path, monkeypatch):
    _app()
    from edifice.excel_io import build_template
    from edifice.ui import main_window as mw
    f = tmp_path / "bina.xlsx"
    build_template(str(f), example=True)
    store = Store(":memory:")
    bid = store.seed_demo()
    w = MainWindow(store.load_project(bid), store)

    class FakeChoice:
        Accepted = mw.AddChoiceDialog.Accepted
        choice, path = "excel", str(f)
        def __init__(self, parent=None): pass
        def exec(self): return self.Accepted

    seen = {}

    class FakeDialog(mw.BuildingDialog):
        def exec(self):
            seen["review"] = self.review and self.name.text()
            self.save()
            return QDialog.Accepted

    monkeypatch.setattr(mw, "AddChoiceDialog", FakeChoice)
    monkeypatch.setattr(mw, "BuildingDialog", FakeDialog)
    w.add_building()
    assert seen["review"] == "Örnek Ofis Binası"
    assert w.project.building.name == "Örnek Ofis Binası" and store.count() == 2


def test_budget_slider_selects_package_and_finance_updates():
    _app()
    store = Store(":memory:")
    bid = store.seed_demo()
    w = MainWindow(store.load_project(bid), store)
    sc = w.sub["Mevcut vs Hedef"]
    sc.slider.setValue(0)
    assert sc.selected_codes() == []
    sc.slider.setValue(60)           # 3,0 M ₺
    assert sc.selected_codes() and w.project.finance(sc.selected_codes()).npv > 0
    assert store.load_scenario(bid) == sc.selected_codes()


def test_assistant_chat_answers_locally_and_keeps_history():
    import time
    from PySide6.QtWidgets import QApplication
    from edifice.db import Store
    from edifice.ui.main_window import MainWindow

    store = Store(":memory:")
    store.seed_demo()
    w = MainWindow(store.load_project(store.latest_id()), store)
    chat = w.sub["Sohbet"]
    chat.send("Hangi öneriyle başlamalıyım?")
    for _ in range(300):
        QApplication.processEvents()
        if chat.worker.isFinished():
            break
        time.sleep(0.02)
    QApplication.processEvents()
    role, text = w.chat_state.display[-1]
    assert role == "assistant" and "geri ödeme" in text
    w.set_project(store.load_project(store.latest_id()))   # bina değişince geçmiş korunur
    assert len(w.chat_state.display) == 2
