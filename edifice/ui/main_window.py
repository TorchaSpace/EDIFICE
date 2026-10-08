from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QButtonGroup, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QPushButton, QVBoxLayout, QWidget)

from ..service import Project
from .pages import ConsumptionPage, OpportunitiesPage, OverviewPage, ScenarioPage
from .report import build_report
from .widgets import STYLE, FadeStack, Logo, NavButton


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
        group = QButtonGroup(self)
        group.setExclusive(True)
        side = QVBoxLayout()
        side.setContentsMargins(0, 0, 0, 20)
        side.setSpacing(2)
        side.addWidget(Logo())
        self.buttons = []
        for i, (name, icon, page) in enumerate(specs):
            btn = NavButton(name, icon)
            group.addButton(btn, i)
            btn.clicked.connect(lambda _=False, idx=i: self.stack.setCurrentIndex(idx))
            side.addWidget(btn)
            self.buttons.append(btn)
            self.stack.addWidget(page.widget)
        side.addStretch()
        report_btn = QPushButton("Rapor oluştur")
        report_btn.setObjectName("ghost")
        report_btn.setCursor(self.buttons[0].cursor())
        report_btn.clicked.connect(self.export_report)
        side.addWidget(report_btn)
        note = QLabel("Pilot bina · mock veri")
        note.setObjectName("side")
        note.setContentsMargins(22, 12, 0, 0)
        side.addWidget(note)
        side_w = QWidget()
        side_w.setObjectName("side")
        side_w.setFixedWidth(232)
        side_w.setLayout(side)

        root = QWidget()
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(side_w)
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.buttons[0].setChecked(True)
        self.stack.setCurrentIndex(0)

    def select(self, index: int):
        self.buttons[index].setChecked(True)
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
