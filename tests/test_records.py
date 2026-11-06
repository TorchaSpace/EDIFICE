"""Ortaklar, sertifikalar, finansman, rapor geçmişi, proje harcaması: kayıt katmanı ve sayfalar."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6.QtWidgets import QApplication

from edifice.db import Store


def _app():
    return QApplication.instance() or QApplication([])


def test_records_crud_and_whitelist():
    st = Store(":memory:")
    bid = st.seed_demo()
    rid = st.add_record("partners", {"name": "ABC Enerji", "category": "GES", "rating": 4.5})
    st.add_record("certificates", {"building_id": bid, "scheme": "BREEAM", "level": "Very Good"})
    assert st.list_records("partners")[0]["name"] == "ABC Enerji" and st.list_records("certificates", bid)[0]["level"] == "Very Good"
    assert st.list_records("certificates", bid + 99) == []
    st.delete_record("partners", rid)
    assert st.list_records("partners") == []
    with pytest.raises(KeyError):
        st.add_record("buildings; DROP TABLE x", {})
    with pytest.raises(KeyError):
        st.delete_record("settings", 1)


def test_cascade_on_building_delete():
    st = Store(":memory:")
    bid = st.seed_demo()
    st.add_record("finance_items", {"building_id": bid, "kind": "Kredi", "amount": 5})
    st.delete_building(bid)
    assert st.list_records("finance_items") == []


def test_project_spent_survives_status_change():
    st = Store(":memory:")
    bid = st.seed_demo()
    st.save_project(bid, "LED", "Planlandı", 2026, 3)
    st.save_project_spent(bid, "LED", 12345.0)
    st.save_project(bid, "LED", "Uygulanıyor", 2026, 4)          # durum değişimi harcamayı silmemeli
    assert st.load_project_spent(bid)["LED"] == 12345.0 and st.load_projects(bid)["LED"] == ("Uygulanıyor", 2026)
    st.save_project_spent(bid, "VFD", 5.0)                       # kayıtsız proje için de harcama tutulur
    assert st.load_project_spent(bid)["VFD"] == 5.0


def test_pages_and_report_history(tmp_path, monkeypatch):
    _app()
    from PySide6.QtWidgets import QFileDialog
    from edifice.ui.main_window import MainWindow
    from edifice.ui.records_pages import CertificatesPage, FinancingPage, PartnersPage
    st = Store(str(tmp_path / "r.db"))
    bid = st.seed_demo()
    pr = st.load_project(bid)
    pp = PartnersPage(st)
    pp.panel.inputs["name"].setText("Firma A")
    pp.panel.inputs["rating"].setValue(4)
    pp.panel.add()
    pp.panel.inputs["name"].setText("")
    pp.panel.add()                                                 # zorunlu alan boş: eklenmez
    assert len(st.list_records("partners")) == 1
    fp = FinancingPage(pr, st)
    fp.panel.inputs["name"].setText("Banka kredisi")
    fp.panel.inputs["amount"].setValue(1_000_000)
    fp.panel.add()
    fp.panel.inputs["name"].setText("Reddedilen hibe")
    fp.panel.inputs["kind"].setCurrentText("Hibe")
    fp.panel.inputs["status"].setCurrentText("Reddedildi")
    fp.panel.inputs["amount"].setValue(500_000)
    fp.panel.add()
    assert fp.mix() == {"Özkaynak": 1_000_000.0}                  # ilk türün varsayılanı; reddedilen hariç
    CertificatesPage(pr, st)
    w = MainWindow(pr, st)
    out = str(tmp_path / "rapor.xlsx")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (out, "")))
    from PySide6.QtGui import QDesktopServices
    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda *a, **k: True))
    w.export_pack("esg")
    log = st.list_records("report_log")
    assert log and log[0]["kind"] == "ESG veri paketi" and log[0]["path"] == out and os.path.exists(out)
    assert w.report_page.hist.lay.count() > 3
    tr = w.sub["Proje takibi"]
    tr.spent["LED"].setValue(2_000_000_000 / 1000)
    assert st.load_project_spent(bid).get("LED") == 2_000_000.0
