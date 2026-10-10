"""Bozuk/uç girdili binalarda TÜM sayfalar çökmeden açılmalı (sıfır elektrik/gaz/su, ekipmansız, tek yıl, uç alan)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from edifice.db import Store
from edifice.models import UtilityType
from edifice.service import Project
from edifice.ui.main_window import MainWindow


@pytest.fixture(scope="module", autouse=True)
def qapp():
    return QApplication.instance() or QApplication([])


def variants():
    def zero(u):
        def f(p):
            p.readings = [r for r in p.readings if r.utility != u]
        return f

    def tiny_area(p):
        p.building.floor_area_m2 = 1.0

    def huge_values(p):
        for r in p.readings:
            r.consumption *= 500

    def no_equipment(p):
        p.equipment = []

    def single_year(p):
        p.readings = [r for r in p.readings if r.year == max(x.year for x in p.readings)]

    def zero_cost(p):
        for r in p.readings:
            r.cost = 0.0

    return {"elektriksiz": zero(UtilityType.ELECTRICITY), "gazsiz": zero(UtilityType.GAS), "susuz": zero(UtilityType.WATER),
            "1 m²": tiny_area, "500 kat": huge_values, "ekipmansız": no_equipment, "tek yıl": single_year, "sıfır tutar": zero_cost}


@pytest.mark.parametrize("name", list(variants()))
def test_every_page_opens_for_degenerate_building(name):
    st = Store(":memory:")
    p = Project.mock()
    variants()[name](p)
    p.building.name = f"Bozuk · {name}"
    bid = st.save_building(p.building, p.readings, p.equipment)
    w = MainWindow(st.load_project(bid), st)
    for i in range(len(w.pages)):
        w.select(i)
        QApplication.processEvents()
    chat = w.sub["Sohbet"]
    for q in ("binam nasıl", "enerji sınıfım", "hangi öneriyle başlamalıyım", "2 milyon bütçem var", "led ve vfd yaparsam"):
        w.chat_state.memory = type(w.chat_state.memory)()
        from edifice.ai.tools import Toolbox
        chat.ai.answer(q, Toolbox({bid: st.load_project(bid)}, bid), w.chat_state.memory)
