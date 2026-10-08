from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QListWidget, QMainWindow, QMessageBox,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from ..service import Project
from .pages import ConsumptionPage, OpportunitiesPage, OverviewPage, ScenarioPage
from .report import build_report
from .widgets import STYLE


class MainWindow(QMainWindow):
    def __init__(self, project: Project):
        super().__init__()
        self.project = project
        self.setWindowTitle("EDIFI'CE")
        self.resize(1200, 780)
        self.setStyleSheet(STYLE)

        self.pages = [
            ("Genel Bakış", OverviewPage(project)),
            ("Tüketim", ConsumptionPage(project)),
            ("Öneriler", OpportunitiesPage(project)),
            ("Mevcut vs Hedef", ScenarioPage(project)),
        ]
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(200)
        self.stack = QStackedWidget()
        for name, page in self.pages:
            self.nav.addItem(name)
            self.stack.addWidget(page.widget)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        report_btn = QPushButton("Rapor oluştur")
        report_btn.clicked.connect(self.export_report)
        side = QVBoxLayout()
        side.setContentsMargins(0, 0, 0, 12)
        side.addWidget(self.nav, 1)
        side.addWidget(report_btn)
        side_w = QWidget()
        side_w.setObjectName("side")
        report_btn.setStyleSheet("margin: 0 12px;")
        side_w.setLayout(side)

        root = QWidget()
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(side_w)
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(root)

    def export_report(self):
        scenario_page = self.pages[3][1]
        path, _ = QFileDialog.getSaveFileName(self, "Raporu kaydet", "edifice_rapor.html",
                                              "HTML (*.html)")
        if not path:
            return
        Path(path).write_text(build_report(self.project, scenario_page.selected_codes()),
                              encoding="utf-8")
        QMessageBox.information(self, "Rapor", f"Rapor kaydedildi:\n{path}")
