from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QPushButton, QVBoxLayout, QWidget)

from ..service import Project
from .pages import ConsumptionPage, OpportunitiesPage, OverviewPage, ScenarioPage
from .report import build_report
from .widgets import STYLE, FadeStack, Logo, NavBar


class MainWindow(QMainWindow):
    def __init__(self, project: Project):
        super().__init__()
        self.project = project
        self.setWindowTitle("EDIFI'CE")
        self.resize(1360, 860)
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(STYLE)

        specs = [
            ("Genel Bakış", "overview", OverviewPage(project)),
            ("Tüketim", "consumption", ConsumptionPage(project)),
            ("Öneriler", "opportunities", OpportunitiesPage(project)),
            ("Mevcut vs Hedef", "scenario", ScenarioPage(project)),
        ]
        self.pages = [(name, page) for name, _, page in specs]

        self.stack = FadeStack()
        side = QVBoxLayout()
        side.setContentsMargins(0, 0, 0, 20)
        side.setSpacing(2)
        side.addWidget(Logo())
        self.nav = NavBar([(name, icon) for name, icon, _ in specs])
        self.buttons = self.nav.buttons
        for i, (_, _, page) in enumerate(specs):
            self.buttons[i].clicked.connect(lambda _=False, idx=i: self.select(idx))
            self.stack.addWidget(page.widget)
        side.addWidget(self.nav)
        side.addStretch()
        report_btn = QPushButton("Rapor oluştur")
        report_btn.setObjectName("ghost")
        report_btn.setCursor(self.buttons[0].cursor())
        report_btn.clicked.connect(self.export_report)
        side.addWidget(report_btn)
        note = QLabel("Pilot bina · mock veri")
        note.setObjectName("sidenote")
        note.setContentsMargins(22, 12, 0, 0)
        side.addWidget(note)
        side_w = QWidget()
        side_w.setObjectName("side")
        side_w.setAttribute(Qt.WA_StyledBackground, True)
        side_w.setLayout(side)
        side_w.setFixedWidth(236)
        side_wrap = QWidget()
        wl = QVBoxLayout(side_wrap)
        wl.setContentsMargins(14, 14, 0, 14)
        wl.addWidget(side_w)

        root = QWidget()
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(side_wrap)
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.nav.select(0, animate=False)
        self.stack.setCurrentIndex(0)

    def select(self, index: int):
        self.nav.select(index)
        self.stack.setCurrentIndex(index)

    def export_report(self):
        scenario_page = self.pages[3][1]
        path, _ = QFileDialog.getSaveFileName(self, "Raporu kaydet", "edifice_rapor.html",
                                              "HTML (*.html)")
        if not path:
            return
        Path(path).write_text(build_report(self.project, scenario_page.selected_codes()),
                              encoding="utf-8")
        QMessageBox.information(self, "Rapor", f"Rapor kaydedildi:\n{path}")
