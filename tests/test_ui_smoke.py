import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from edifice.service import Project
from edifice.ui.main_window import MainWindow
from edifice.ui.report import build_report


def test_window_builds_and_scenario_updates():
    app = QApplication.instance() or QApplication([])
    p = Project.mock()
    w = MainWindow(p)
    sc = w.pages[3][1]
    sc.checks["LED"].setChecked(True)
    assert sc.selected_codes() == ["LED"]
    assert "Rapor" in build_report(p, ["LED"]) or "EDIFI" in build_report(p, ["LED"])
