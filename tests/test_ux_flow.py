"""Akıcılık iyileştirmeleri: bina değişince sayfa/sekme korunur, geri/ileri, komut paleti araması, arama gecikmesi,
odakta olmayan sayı kutusunun tekerlekle değişmemesi, bildirim kartı."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QSpinBox  # noqa: E402

from edifice.db import Store  # noqa: E402
from edifice.ui.main_window import MainWindow  # noqa: E402
from edifice.ui.palette import Command, norm, rank  # noqa: E402
from edifice.ui.widgets import WheelGuard  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def _two_buildings():
    store = Store(":memory:")
    a = store.seed_demo()
    p = store.load_project(a)
    b = store.save_building(p.building.__class__(**{**p.building.__dict__, "name": "İkinci Bina"}), p.readings, p.equipment)
    return store, a, b


def test_switching_building_keeps_page_and_tab():
    _app()
    store, a, b = _two_buildings()
    w = MainWindow(store.load_project(a), store)
    w.go("Finans", "Teşvik bulucu")
    w.set_project(store.load_project(b))
    assert w.project.building.name == "İkinci Bina"
    assert w.pages[w.cur][0] == "Finans" and w._tab_of(w.cur) == "Teşvik bulucu"
    assert w.crumb_tab.text().endswith("Teşvik bulucu")
    w.open_building(a)                                  # portföyden/uyarıdan açınca Genel Bakış'a gider
    assert w.pages[w.cur][0] == "Genel Bakış"


def test_back_and_forward_restore_page_and_tab():
    _app()
    store, a, _ = _two_buildings()
    w = MainWindow(store.load_project(a), store)
    w.go("Projeler", "Mevcut vs Hedef")
    w.select(w.idx["Ayarlar"])
    w.back()
    assert w.pages[w.cur][0] == "Projeler" and w._tab_of(w.cur) == "Mevcut vs Hedef"
    w.forward()
    assert w.pages[w.cur][0] == "Ayarlar"


def test_palette_search_is_turkish_insensitive_and_runs():
    _app()
    assert norm("Güneş IŞIK İklim") == "gunes isik iklim"
    hits = []
    cmds = [Command("Güneş enerjisi (GES)", "Sekme", lambda: hits.append("ges")),
            Command("Genel Bakış", "Sayfa", lambda: hits.append("gb")),
            Command("Teşvik bulucu", "Sekme", lambda: hits.append("t"), "hibe kredi")]
    assert rank(cmds, "gunes")[0].title.startswith("Güneş")
    assert rank(cmds, "hibe")[0].title == "Teşvik bulucu"
    assert rank(cmds, "xyz") == []
    store, a, b = _two_buildings()
    w = MainWindow(store.load_project(a), store)
    found = rank(w.commands(), "ikinci")
    assert found and found[0].group == "Bina"
    found[0].run()
    assert w.project.building_id == b
    titles = {c.title for c in w.commands()}
    assert "Finans  ›  Güneş enerjisi (GES)" in titles and "PDF raporu oluştur" in titles


def test_search_clear_does_not_jump_to_portfolio():
    _app()
    store, a, _ = _two_buildings()
    w = MainWindow(store.load_project(a), store)
    w.select(w.idx["Ayarlar"])
    w._search("ikinci")
    assert w.pages[w.cur][0] == "Portföy"
    w.select(w.idx["Ayarlar"])
    w._search("")
    assert w.pages[w.cur][0] == "Ayarlar"


def test_wheel_over_unfocused_spinbox_does_not_change_value():
    app = _app()
    WheelGuard.install()
    sp = QSpinBox()
    sp.setRange(0, 100)
    sp.setValue(50)
    sp.show()
    ev = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, 120), Qt.NoButton, Qt.NoModifier,
                     Qt.NoScrollPhase, False)
    app.sendEvent(sp, ev)
    assert sp.value() == 50


def test_toast_and_shortcut_tooltips():
    _app()
    store, a, _ = _two_buildings()
    w = MainWindow(store.load_project(a), store)
    w.resize(1300, 800)
    w.show()
    w.notify("Kaydedildi", action=("Aç", lambda: None))
    assert w.toast.isVisible() and w.toast._text.text() == "Kaydedildi"
    assert "(" in w.buttons[0].toolTip()
