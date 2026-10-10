"""Tam tur: her sayfanın her sekmesi, dolu önbelleklerle (hava, iklim, GES, CRREM) açılır; yuvalarda (slot) yakalanmamış hata olmamalı.
PySide yuva hatalarını yutup yazdırır; bu test sys.excepthook ile hepsini yakalayıp başarısız sayar."""
import json
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from edifice import weather
from edifice.db import Store
from edifice.service import Project
from edifice.ui.main_window import MainWindow
from edifice.ui.tabs_page import TabsPage
from test_climate_live import SAMPLE
from test_crrem import synthetic_workbook
from test_weather_norm import synth_daily


def test_full_tour_has_no_hidden_slot_errors(tmp_path):
    app = QApplication.instance() or QApplication([])
    errors = []
    old = sys.excepthook
    sys.excepthook = lambda t, v, tb: errors.append(f"{t.__name__}: {v}")
    try:
        st = Store(":memory:")
        ids = []
        for i, (name, lat, lon) in enumerate((("Merkez", 41.01, 28.98), ("Plaza", 39.93, 32.86), ("Konumsuz", None, None))):
            p = Project.mock()
            p.building.name, p.building.lat, p.building.lon = name, lat, lon
            ids.append(st.save_building(p.building, p.readings, p.equipment))
        st.save_weather(41.01, 28.98, weather.monthly_degree_days(synth_daily(2012, 2026)))
        parsed = weather.parse_forecast(json.dumps(SAMPLE).encode())
        st.save_climate(41.01, 28.98, parsed)
        st.save_solar(41.01, 28.98, 30.0, 0.0, [65, 83, 116, 134, 143, 151, 170, 166, 147, 120, 99, 72])
        from edifice.crrem import parse
        st.import_crrem(parse(synthetic_workbook(str(tmp_path / "c.xlsx"))))
        st.save_project(ids[0], "VFD", "Tamamlandı", 2025, 3)
        st.save_project(ids[0], "LED", "Planlandı", 2028, 1)
        for bid in ids:
            w = MainWindow(st.load_project(bid), st)
            for _ in range(10):
                app.processEvents()
            for i, (name, page) in enumerate(w.pages):
                w.select(i)
                app.processEvents()
                if isinstance(page, TabsPage):
                    for j in range(len(page.tabs)):
                        page.group.button(j).click()
                        app.processEvents()
            chat = w.sub["Sohbet"]
            for q in ("binam nasıl", "bugün hava nasıl", "ges kendini öder mi", "veri kalitesi", "gerçekleşen tasarruf", "2 milyon bütçem var"):
                chat.send(q)
                for _ in range(300):
                    app.processEvents()
                    if chat.worker.isFinished():
                        break
                    time.sleep(0.01)
            for _ in range(20):
                app.processEvents()
    finally:
        sys.excepthook = old
    assert not errors, errors[:5]
