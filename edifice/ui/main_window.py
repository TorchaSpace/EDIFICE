from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMenu, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from ..db import Store
from ..service import Project
from .pages import ConsumptionPage, OpportunitiesPage, OverviewPage, ScenarioPage
from .building_dialog import BuildingDialog
from .report_pdf import build_pdf
from .settings_page import SettingsPage
from .widgets import get_style, FadeStack, Logo, NavBar, section

TR_MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


class MainWindow(QMainWindow):
    def __init__(self, project: Project, store: Store | None = None):
        super().__init__()
        self.project = project
        self.store = store or Store(":memory:")
        self.setWindowTitle("EDIFI'CE")
        self.resize(1440, 900)
        self.setMinimumSize(1180, 720)
        self.setStyleSheet(get_style())

        self.nav_specs = [("Genel Bakış", "overview"), ("Tüketim", "consumption"),
                          ("Öneriler", "opportunities"), ("Mevcut vs Hedef", "scenario"),
                          ("Ayarlar", "settings")]
        self.pages = []
        self.stack = FadeStack()

        # ---- sidebar
        side = QVBoxLayout()
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(0)
        side.addWidget(Logo())
        side.addWidget(section_label("Platform"))
        self.nav = NavBar(self.nav_specs)
        self.buttons = self.nav.buttons
        for i in range(len(self.nav_specs)):
            self.buttons[i].clicked.connect(lambda _=False, idx=i: self.select(idx))
        side.addWidget(self.nav)
        side.addStretch()
        foot = QWidget()
        foot.setObjectName("sidefoot")
        fl = QVBoxLayout(foot)
        fl.setContentsMargins(10, 12, 10, 16)
        self.bldg_btn = QPushButton()
        self.bldg_btn.setObjectName("bldg")
        self.bldg_btn.setCursor(Qt.PointingHandCursor)
        self.bldg_btn.setFixedHeight(52)
        bl = QHBoxLayout(self.bldg_btn)
        bl.setContentsMargins(12, 0, 12, 0)
        av = QLabel("B")
        av.setFixedSize(30, 30)
        av.setAlignment(Qt.AlignCenter)
        av.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #0DDD96, stop:1 #6366F1); color: #050A0E;"
                         "border-radius: 8px; font-size: 11px; font-weight: 800;")
        self.av = av
        txt = QVBoxLayout()
        txt.setSpacing(0)
        self.n1 = QLabel("")
        self.n1.setStyleSheet("font-size: 12px; font-weight: 700; background: transparent;")
        n2 = QLabel("Bina değiştir  ▾")
        n2.setStyleSheet("font-size: 10px; color: #3A526A; background: transparent;")
        txt.addWidget(self.n1)
        txt.addWidget(n2)
        bl.addWidget(av)
        bl.addLayout(txt, 1)
        for w in (av, self.n1, n2):
            w.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.bldg_btn.clicked.connect(self.show_building_menu)
        fl.addWidget(self.bldg_btn)
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
        c1, sep, self.crumb = QLabel("Platform"), QLabel("/"), QLabel(self.nav_specs[0][0])
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
        add_btn = QPushButton("+ Bina Ekle")
        add_btn.setObjectName("primary")
        add_btn.setFixedHeight(32)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self.add_building)
        add_btn.setStyleSheet("padding: 6px 16px;")
        tl.addWidget(export)
        tl.addWidget(add_btn)
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
        self.set_project(project)

    def set_project(self, project: Project, select: int = 0, notify: bool = False):
        """Seçili binayı değiştirir: sayfaları yeniden kurar."""
        self.project = project
        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.deleteLater()
        self.pages = [(self.nav_specs[0][0], OverviewPage(project)), (self.nav_specs[1][0], ConsumptionPage(project)),
                      (self.nav_specs[2][0], OpportunitiesPage(project)), (self.nav_specs[3][0], ScenarioPage(project, self.store)),
                      (self.nav_specs[4][0], SettingsPage(project, self.store, self._settings_saved))]
        for _, page in self.pages:
            self.stack.addWidget(page.widget)
        self.n1.setText(project.building.name)
        self.av.setText(project.building.name[:1].upper() or "B")
        self.live.setText(f"●  {project.building.name}")
        self.nav.select(select, animate=False)
        self.stack.setCurrentIndex(select)
        self.crumb.setText(self.pages[select][0])
        if notify:
            self.pages[4][1].saved_message()

    def show_building_menu(self):
        menu = QMenu(self)
        for bid, name in self.store.list_buildings():
            act = menu.addAction(("✓  " if bid == self.project.building_id else "     ") + name)
            act.triggered.connect(lambda _=False, i=bid: self.set_project(self.store.load_project(i)))
        menu.addSeparator()
        menu.addAction("+  Yeni bina ekle").triggered.connect(self.add_building)
        if self.project.building_id is not None:
            menu.addAction("✎  Bu binayı düzenle").triggered.connect(self.edit_building)
        if self.store.count() > 1 and self.project.building_id is not None:
            menu.addAction("Bu binayı sil").triggered.connect(self.delete_current)
        menu.exec(self.bldg_btn.mapToGlobal(self.bldg_btn.rect().topLeft() - self.bldg_btn.rect().bottomLeft()))

    def add_building(self):
        dlg = BuildingDialog(self, tariffs=self.project.assumptions.default_tariffs)
        if dlg.exec() == BuildingDialog.Accepted and dlg.result_data:
            building, readings, equipment = dlg.result_data
            bid = self.store.save_building(building, readings, equipment)
            self.set_project(self.store.load_project(bid))

    def edit_building(self):
        dlg = BuildingDialog(self, project=self.project, tariffs=self.project.assumptions.default_tariffs)
        if dlg.exec() == BuildingDialog.Accepted and dlg.result_data:
            building, readings, equipment = dlg.result_data
            self.store.update_building(self.project.building_id, building, readings, equipment)
            self.set_project(self.store.load_project(self.project.building_id))

    def _settings_saved(self):
        self.set_project(self.store.load_project(self.project.building_id), select=4, notify=True)

    def delete_current(self):
        name = self.project.building.name
        if QMessageBox.question(self, "Binayı sil", f"'{name}' ve tüm verileri silinsin mi?") != QMessageBox.Yes:
            return
        self.store.delete_building(self.project.building_id)
        self.set_project(self.store.load_project(self.store.latest_id()))

    def _toggle_dot(self):
        self._dot_on = not self._dot_on
        dot = "●" if self._dot_on else "○"
        self.live.setText(f"{dot}  {self.project.building.name}")

    def select(self, index: int):
        self.nav.select(index)
        self.stack.setCurrentIndex(index)
        self.crumb.setText(self.pages[index][0])

    def export_report(self):
        codes = self.pages[3][1].selected_codes()
        default = f"EDIFICE_{self.project.building.name.replace(' ', '_')}_{datetime.now():%Y-%m-%d}.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "Raporu kaydet", default, "PDF (*.pdf)")
        if not path:
            return
        build_pdf(self.project, codes, path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def section_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setObjectName("section")
    return lbl
