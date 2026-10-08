from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from ..service import Project
from .pages import ConsumptionPage, OpportunitiesPage, OverviewPage, ScenarioPage
from .report import build_report
from .widgets import STYLE, FadeStack, Logo, NavBar, section

TR_MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


class MainWindow(QMainWindow):
    def __init__(self, project: Project):
        super().__init__()
        self.project = project
        self.setWindowTitle("EDIFI'CE")
        self.resize(1440, 900)
        self.setMinimumSize(1180, 720)
        self.setStyleSheet(STYLE)

        specs = [
            ("Genel Bakış", "overview", OverviewPage(project)),
            ("Tüketim", "consumption", ConsumptionPage(project)),
            ("Öneriler", "opportunities", OpportunitiesPage(project)),
            ("Mevcut vs Hedef", "scenario", ScenarioPage(project)),
        ]
        self.pages = [(name, page) for name, _, page in specs]
        self.stack = FadeStack()

        # ---- sidebar
        side = QVBoxLayout()
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(0)
        side.addWidget(Logo())
        side.addWidget(section_label("Platform"))
        self.nav = NavBar([(name, icon) for name, icon, _ in specs])
        self.buttons = self.nav.buttons
        for i, (_, _, page) in enumerate(specs):
            self.buttons[i].clicked.connect(lambda _=False, idx=i: self.select(idx))
            self.stack.addWidget(page.widget)
        side.addWidget(self.nav)
        side.addStretch()
        foot = QWidget()
        foot.setObjectName("sidefoot")
        fl = QVBoxLayout(foot)
        fl.setContentsMargins(10, 12, 10, 16)
        card = QWidget()
        card.setObjectName("inner")
        card.setStyleSheet("QWidget#inner { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.07); border-radius: 12px; }")
        cl = QHBoxLayout(card)
        cl.setContentsMargins(12, 10, 12, 10)
        av = QLabel("PO")
        av.setFixedSize(30, 30)
        av.setAlignment(Qt.AlignCenter)
        av.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #0DDD96, stop:1 #6366F1); color: #050A0E;"
                         "border-radius: 8px; font-size: 11px; font-weight: 800;")
        txt = QVBoxLayout()
        txt.setSpacing(0)
        n1 = QLabel(project.building.name)
        n1.setStyleSheet("font-size: 12px; font-weight: 700; background: transparent;")
        n2 = QLabel("Pilot bina · mock veri")
        n2.setStyleSheet("font-size: 10px; color: #3A526A; background: transparent;")
        txt.addWidget(n1)
        txt.addWidget(n2)
        cl.addWidget(av)
        cl.addLayout(txt, 1)
        fl.addWidget(card)
        side.addWidget(foot)
        side_w = QWidget()
        side_w.setObjectName("side")
        side_w.setAttribute(Qt.WA_StyledBackground, True)
        side_w.setLayout(side)
        side_w.setFixedWidth(220)

        # ---- top bar
        top = QWidget()
        top.setObjectName("topbar")
        top.setAttribute(Qt.WA_StyledBackground, True)
        top.setFixedHeight(54)
        tl = QHBoxLayout(top)
        tl.setContentsMargins(28, 0, 28, 0)
        tl.setSpacing(14)
        c1, sep, self.crumb = QLabel("Platform"), QLabel("/"), QLabel(specs[0][0])
        c1.setObjectName("crumb")
        sep.setStyleSheet("color: #1E3048; font-size: 11px;")
        self.crumb.setObjectName("crumbnow")
        tl.addWidget(c1)
        tl.addWidget(sep)
        tl.addWidget(self.crumb)
        tl.addStretch()
        self.live = QLabel(f"●  {project.building.name}")
        self.live.setObjectName("livepill")
        self.live.setFixedHeight(28)
        tl.addWidget(self.live)
        now = datetime.now()
        date = QLabel(f"{now.day} {TR_MONTHS[now.month - 1]} {now.year} · {now:%H:%M}")
        date.setObjectName("datepill")
        date.setFixedHeight(28)
        tl.addWidget(date)
        export = QPushButton("↓ Rapor")
        export.setObjectName("export")
        export.setFixedHeight(32)
        export.setCursor(Qt.PointingHandCursor)
        export.clicked.connect(self.export_report)
        tl.addWidget(export)
        self._blink = QTimer(self)
        self._blink.timeout.connect(self._toggle_dot)
        self._blink.start(1000)
        self._dot_on = True

        main = QWidget()
        main.setObjectName("root")
        ml = QVBoxLayout(main)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)
        ml.addWidget(top)
        ml.addWidget(self.stack, 1)

        root = QWidget()
        root.setObjectName("root")
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(side_w)
        lay.addWidget(main, 1)
        self.setCentralWidget(root)
        self.nav.select(0, animate=False)
        self.stack.setCurrentIndex(0)

    def _toggle_dot(self):
        self._dot_on = not self._dot_on
        dot = "●" if self._dot_on else "○"
        self.live.setText(f"{dot}  {self.project.building.name}")

    def select(self, index: int):
        self.nav.select(index)
        self.stack.setCurrentIndex(index)
        self.crumb.setText(self.pages[index][0])

    def export_report(self):
        scenario_page = self.pages[3][1]
        path, _ = QFileDialog.getSaveFileName(self, "Raporu kaydet", "edifice_rapor.html", "HTML (*.html)")
        if not path:
            return
        Path(path).write_text(build_report(self.project, scenario_page.selected_codes()), encoding="utf-8")
        QMessageBox.information(self, "Rapor", f"Rapor kaydedildi:\n{path}")


def section_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setObjectName("section")
    return lbl
