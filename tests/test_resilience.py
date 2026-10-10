"""Dayanıklılık: eski veritabanı göçü, ağ yokken yükleyiciler, sayfa yok edilirken çalışan sohbet iş parçacığı."""
import os
import sqlite3
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from edifice import geocode, solar, weather
from edifice.db import Store
from edifice.service import Project

LEGACY = """
CREATE TABLE buildings (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, address TEXT, use_type TEXT,
  floor_area_m2 REAL, year_built INTEGER, floors INTEGER, occupants INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE readings (building_id INTEGER NOT NULL, utility TEXT, year INTEGER, month INTEGER, consumption REAL, cost REAL);
CREATE TABLE equipment (id INTEGER PRIMARY KEY AUTOINCREMENT, building_id INTEGER NOT NULL, category TEXT, name TEXT,
  year_installed INTEGER, condition INTEGER, notes TEXT);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE projects (building_id INTEGER NOT NULL, code TEXT NOT NULL, status TEXT NOT NULL, year INTEGER NOT NULL, PRIMARY KEY (building_id, code));
INSERT INTO buildings (name, address, use_type, floor_area_m2, year_built, floors, occupants) VALUES ('Eski Bina', 'İstanbul', 'Ofis', 5000, 1990, 5, 100);
INSERT INTO projects VALUES (1, 'LED', 'Planlandı', 2027);
"""


def _app():
    return QApplication.instance() or QApplication([])


def test_legacy_database_is_migrated_in_place(tmp_path):
    db = tmp_path / "eski.db"
    con = sqlite3.connect(db)
    con.executescript(LEGACY)
    p = Project.mock()
    con.executemany("INSERT INTO readings VALUES (1,?,?,?,?,?)", [(r.utility.value, r.year, r.month, r.consumption, r.cost) for r in p.readings])
    con.commit()
    con.close()
    st = Store(str(db))                                          # eksik sütunlar/tablolar eklenir
    got = st.load_project(1)
    assert got.building.name == "Eski Bina" and got.building.lat is None
    assert st.load_projects(1) == {"LED": ("Planlandı", 2027)} and st.load_project_months(1) == {"LED": 1}
    st.save_project(1, "LED", "Tamamlandı", 2027, 5)
    assert st.load_project_months(1)["LED"] == 5
    st.save_weather(41, 29, {(2025, 1): (300.0, 0.0, 31)})
    assert st.load_weather(41, 29)
    assert Store(str(db)).load_project(1).building.name == "Eski Bina"    # ikinci açılış sorunsuz


def _wait(signal_owner, signal_name, ms=8000):
    got = []
    loop = QEventLoop()
    getattr(signal_owner, signal_name).connect(lambda *a: (got.append(a), loop.quit()))
    QTimer.singleShot(ms, loop.quit)
    return got, loop


def test_loaders_survive_network_failure(monkeypatch, tmp_path):
    _app()
    dead = "http://127.0.0.1:9/yok"                              # bağlantı reddedilir
    monkeypatch.setattr(weather, "request_url", lambda *a, **k: dead)
    monkeypatch.setattr(weather, "forecast_url", lambda *a, **k: dead)
    monkeypatch.setattr(solar, "request_url", lambda *a, **k: dead)
    monkeypatch.setattr(geocode, "_url", lambda *a, **k: dead)
    from edifice.ui.climate_page import ClimateLoader
    from edifice.ui.solar_page import SolarLoader
    from edifice.ui.weather_loader import WeatherLoader
    st = Store(":memory:")
    bid = st.seed_demo()
    proj = st.load_project(bid)
    keep = []                                                    # yükleyiciler uygulamada ömür boyu yaşar; testte de canlı tutulur
    for loader_cls, call, expected in ((WeatherLoader, lambda l: l.load(st, proj), {"ağ"}),
                                       (ClimateLoader, lambda l: l.refresh(st, proj), {"yok", "ağ"}),
                                       (SolarLoader, lambda l: l.load(st, proj), {"ağ"})):
        loader = loader_cls()
        keep.append(loader)
        got, loop = _wait(loader, "done")
        call(loader)
        if not got:
            loop.exec()
        assert got, loader_cls.__name__
        assert got[0][-1] in expected or got[0][-2] in expected or any(x in expected for x in got[0] if isinstance(x, str))
    t0 = time.time()
    assert geocode.lookup_first("Ankara", timeout_ms=3000) is None and time.time() - t0 < 5        # ağ yok: takılmadan None


def test_closing_page_while_chat_is_running_does_not_crash():
    _app()
    from edifice.ui.main_window import MainWindow
    st = Store(":memory:")
    bid = st.seed_demo()
    w = MainWindow(st.load_project(bid), st)
    chat = w.sub["Sohbet"]
    chat.send("hangi öneriyle başlamalıyım")
    w.set_project(st.load_project(bid))                          # sohbet sayfası yok edilir/yeniden kurulur, iş parçacığı sürerken
    for _ in range(300):
        QApplication.processEvents()
        time.sleep(0.01)
    assert w.chat_state.display                                  # çökmeden tamamlandı
