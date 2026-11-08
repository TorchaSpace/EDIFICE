from __future__ import annotations

from datetime import datetime

from contextlib import contextmanager
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QFontMetrics, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from ..db import Store
from ..excel_io import read_workbook
from ..models import Assumptions
from ..service import Project
from ..validation import ValidationError
from .pages import ConsumptionPage, OpportunitiesPage, OverviewPage, ScenarioPage
from .add_choice import AddChoiceDialog
from .building_dialog import BuildingDialog
from .report_pdf import build_pdf
from .method_page import MethodPage
from .climate_page import ClimateLoader, ClimatePage
from .incentives_page import IncentivesPage
from .records_pages import CertificatesPage, FinancingPage, PartnersPage
from .load_page import LoadPage
from .price_page import PricePage
from .solar_page import SolarLoader, SolarPage
from .weather_loader import WeatherLoader
from .assistant_chat import ChatPage, ChatState, TrainingPage
from .projects_page import ProjectsTrackerPage
from .tabs_page import ComingSoonPage, ReportPage, TabsPage
from .portfolio import AssistantPage, EsgPage, FinancePage, PortfolioPage, summarize
from .settings_page import SettingsPage
from .palette import Command, CommandPalette, ShortcutsDialog
from .widgets import get_style, FadeStack, Logo, NavBar, Toast, WheelGuard

# Komut paletinde sayfaları eş anlamlılarıyla da bulabilmek için (ör. "güneş" yazınca GES sekmesi gelir)
KEYWORDS = {"Genel Bakış": "özet dashboard kpi sağlık skoru enerji sınıfı", "Tüketim": "elektrik doğalgaz su fatura aylık",
            "İklim": "hava sıcaklık tahmin", "Portföy": "binalar harita liste", "Öneriler": "dönüşüm tasarruf led yalıtım",
            "Proje takibi": "gantt durum tamamlandı gerçekleşen tasarruf m&v", "Mevcut vs Hedef": "senaryo bütçe npv",
            "Güneş enerjisi (GES)": "güneş solar panel pv çatı", "Birim fiyat analizi": "kwh fiyat tarife",
            "Yük profili ve tarife": "saatlik sayaç pik t1 t2 t3", "Teşvik bulucu": "hibe kredi destek",
            "Finansman karması": "kredi özkaynak", "Sohbet": "yapay zeka soru", "Karbon ve hedefler": "esg crrem emisyon",
            "Rapor": "pdf excel esg ekb", "Kaynaklar ve Yöntem": "kaynakça formül varsayım", "Ayarlar": "varsayım tarife emisyon yedek"}

TR_MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


class MainWindow(QMainWindow):
    def __init__(self, project: Project, store: Store | None = None):
        super().__init__()
        self.project = project
        self.store = store or Store(":memory:")
        self.chat_state = ChatState()
        self.setWindowTitle("EDIFI'CE")
        self.resize(1440, 900)
        self.setMinimumSize(1180, 720)
        self.setStyleSheet(get_style())

        self.sections = [
            ("Platform", [("Genel Bakış", "overview"), ("Portföy", "portfolio"), ("Projeler", "projects"),
                          ("Finans", "finance"), ("Ortaklar", "partners")]),
            ("Intelligence", [("Asistan", "assistant", "LIVE"), ("Digital Twin", "twin"), ("Sürdürülebilirlik", "esg"),
                              ("Raporlar", "method"), ("Ayarlar", "settings")])]
        self.nav_specs = [(it[0], it[1]) for _, items in self.sections for it in items]
        self.pages = []
        self.stack = FadeStack()

        # ---- sidebar
        side = QVBoxLayout()
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(0)
        side.addWidget(Logo())
        self.nav = NavBar(self.sections)
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
        self.crumb1 = c1
        c1.setObjectName("crumb")
        sep.setStyleSheet("color: #1E3048; font-size: 11px;")
        self.crumb.setObjectName("crumbnow")
        tl.addWidget(c1)
        tl.addWidget(sep)
        tl.addWidget(self.crumb)
        self.crumb_tab = QLabel("")                        # alt sekme: "Projeler / Öneriler"
        self.crumb_tab.setObjectName("crumb")
        tl.addWidget(self.crumb_tab)
        tl.addStretch()
        self.wx = QLabel("")
        self.wx.setObjectName("datepill")
        self.wx.setFixedHeight(28)
        self.wx.hide()
        tl.addWidget(self.wx)
        self.quick = QPushButton(f"⌕  Hızlı git   {self._keys('Ctrl+K')}")
        self.quick.setFixedHeight(32)
        self.quick.setCursor(Qt.PointingHandCursor)
        self.quick.setToolTip("Sayfa, sekme, bina ya da eylem adını yazıp Enter'a basın")
        self.quick.setStyleSheet("QPushButton { background: rgba(255,255,255,0.04); color: #A3B6C9; border: 1px solid rgba(255,255,255,0.08);"
                                 "border-radius: 16px; padding: 0 14px; font-size: 12px; }"
                                 "QPushButton:hover { color: #E8F2FF; border: 1px solid rgba(13,221,150,0.35); }")
        self.quick.clicked.connect(lambda: self.open_palette())
        tl.addWidget(self.quick)
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText(f"Bina ara…   {self._keys('Ctrl+F')}")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedSize(190, 32)
        self.search.setStyleSheet("QLineEdit#search { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);"
                                  "border-radius: 16px; padding: 0 14px; font-size: 12px; }"
                                  "QLineEdit#search:focus { border: 1px solid rgba(13,221,150,0.45); }")
        self._search_timer = QTimer(self)                 # her tuşta portföyü yeniden kurmak yerine yazmaya ara verince ara
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(220)
        self._search_timer.timeout.connect(lambda: self._search(self.search.text()))
        self.search.textChanged.connect(lambda _t: self._search_timer.start())
        self.search.returnPressed.connect(lambda: (self._search_timer.stop(), self._search(self.search.text())))
        tl.addWidget(self.search)
        self.bell = QPushButton("🔔")
        self.bell.setFixedSize(32, 32)
        self.bell.setCursor(Qt.PointingHandCursor)
        self.bell.setStyleSheet("QPushButton { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);"
                                "border-radius: 16px; font-size: 13px; } QPushButton:hover { background: rgba(255,255,255,0.08); }")
        self.bell.clicked.connect(self.show_alerts)
        self.bell.setToolTip("Uyarılar")
        tl.addWidget(self.bell)
        self.live = QLabel(f"●  {project.building.name}")
        self.live.setObjectName("livepill")
        self.live.setFixedHeight(28)
        tl.addWidget(self.live)
        self.date = QLabel("")
        self.date.setObjectName("datepill")
        self.date.setFixedHeight(28)
        self._tick_clock()
        tl.addWidget(self.date)
        export = QPushButton("↓ Rapor")
        export.setObjectName("export")
        export.setFixedHeight(32)
        export.setCursor(Qt.PointingHandCursor)
        export.clicked.connect(self.export_report)
        export.setToolTip(f"Seçili öneri paketiyle PDF yatırımcı raporu  ({self._keys('Ctrl+P')})")
        add_btn = QPushButton("+ Bina Ekle")
        add_btn.setObjectName("primary")
        add_btn.setFixedHeight(32)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self.add_building)
        add_btn.setToolTip(f"Formla ya da Excel şablonuyla yeni bina  ({self._keys('Ctrl+N')})")
        add_btn.setStyleSheet("padding: 6px 16px;")
        tl.addWidget(export)
        tl.addWidget(add_btn)
        self._clock = QTimer(self)                        # üst çubuktaki saat dakikada bir güncellensin
        self._clock.timeout.connect(self._tick_clock)
        self._clock.start(20 * 1000)
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
        self.toast = Toast(main)
        WheelGuard.install()
        self._history: list[tuple[int, str | None]] = []
        self._future: list[tuple[int, str | None]] = []
        self._persist = False
        self.cur = 0
        self.set_project(project, select=0)
        self._install_shortcuts()

    def set_project(self, project: Project, select: int | None = None, notify: bool = False, tab: str | None = None):
        """Seçili binayı değiştirir: sayfaları yeniden kurar. select verilmezse kullanıcı bulunduğu sayfa ve sekmede kalır
        (bina değiştirmek, düzenlemek ya da içe aktarmak onu Genel Bakış'a fırlatmaz)."""
        if select is None:
            select = getattr(self, "cur", 0)
            if tab is None and self.pages:
                tab = self._tab_of(select)
        with busy():
            self._set_project(project, select, tab)
        if notify:
            self.sub['Ayarlar'].saved_message()

    def _set_project(self, project: Project, select: int, tab: str | None):
        self.project = project
        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.deleteLater()
        self.sub = {"Genel Bakış": OverviewPage(project, self.store, self.open_building), "Tüketim": ConsumptionPage(project),
                    "Öneriler": OpportunitiesPage(project), "Mevcut vs Hedef": ScenarioPage(project, self.store),
                    "Proje takibi": ProjectsTrackerPage(project, self.store, self._projects_changed),
                    "Sohbet": ChatPage(project, self.store, self.chat_state, self._all_projects, self.run_action),
                    "Kaynaklar ve Yöntem": MethodPage(project),
                    "Ayarlar": SettingsPage(project, self.store, self._settings_saved)}
        sub = self.sub
        sub["Eğitim"] = TrainingPage(self.store, sub["Sohbet"].reload_ai)
        sub["GES"] = SolarPage(project, self.store)
        sub["İklim"] = ClimatePage(project, self.store, self._refresh_climate)
        self.report_page = ReportPage(project, self.export_report, self.export_pack, self.store)
        self.pages = [("Genel Bakış", TabsPage([("Genel Bakış", sub["Genel Bakış"]), ("Tüketim", sub["Tüketim"]), ("İklim", sub["İklim"])])),
                      ("Portföy", PortfolioPage(self.store, self.open_building, self.search.text().strip())),
                      ("Projeler", TabsPage([("Öneriler", sub["Öneriler"]), ("Proje takibi", sub["Proje takibi"]), ("Mevcut vs Hedef", sub["Mevcut vs Hedef"])])),
                      ("Finans", TabsPage([("Portföy finansı", FinancePage(self.store, self.open_building)), ("Güneş enerjisi (GES)", sub["GES"]), ("Birim fiyat analizi", PricePage(project)), ("Yük profili ve tarife", LoadPage(project, self.store)), ("Teşvik bulucu", IncentivesPage(project, self.store)), ("Finansman karması", FinancingPage(project, self.store))])),
                      ("Ortaklar", TabsPage([("Ortaklar", PartnersPage(self.store))])),
                      ("Asistan", TabsPage([("Sohbet", sub["Sohbet"]),
                                            ("Eğitim", sub["Eğitim"]), ("Otomatik bulgular", AssistantPage(project))])),
                      ("Digital Twin", ComingSoonPage("Digital Twin", "Digital Twin",
                                                      "Dijital ikiz için BIM modeli ve canlı sensör (IoT/BMS) verisi gerekir; bunlar MVP kapsamı dışında "
                                                      "olduğundan sonraki fazda eklenecek.")),
                      ("Sürdürülebilirlik", TabsPage([("Karbon ve hedefler", EsgPage(self.store, self.open_building)), ("Sertifikalar", CertificatesPage(project, self.store))])),
                      ("Raporlar", TabsPage([("Rapor", self.report_page),
                                             ("Kaynaklar ve Yöntem", sub["Kaynaklar ve Yöntem"])])),
                      ("Ayarlar", TabsPage([("Ayarlar", sub["Ayarlar"])]))]
        self.idx = {n: i for i, (n, _) in enumerate(self.pages)}
        self._start_weather(project)
        self._start_solar(project)
        self._refresh_climate()
        for _, page in self.pages:
            self.stack.addWidget(page.widget)
            if isinstance(page, TabsPage):
                page.on_change = lambda _name, pg=page: self._tab_changed(pg)
        if tab:
            tp = self.pages[select][1]
            if isinstance(tp, TabsPage):
                tp.select(tab)
        name = project.building.name
        self.n1.setText(QFontMetrics(self.n1.font()).elidedText(name, Qt.ElideRight, 120))
        self.n1.setToolTip(name)
        self.av.setText(name[:1].upper() or "B")
        self.live.setText(f"●  {self._short(name)}")
        self.nav.select(select, animate=False)
        self.stack.setCurrentIndex(select)
        self.cur = select
        self._update_crumb()

    def show_building_menu(self):
        menu = QMenu(self)
        for bid, name in self.store.list_buildings():
            act = menu.addAction(("✓  " if bid == self.project.building_id else "     ") + name)
            act.triggered.connect(lambda _=False, i=bid: self.set_project(self.store.load_project(i)))
        menu.addSeparator()
        menu.addAction("+  Yeni bina ekle").triggered.connect(self.add_building)
        if self.project.building_id is not None:
            menu.addAction("⇪  Tüketimi içe aktar (CSV / Excel)…").triggered.connect(self.import_consumption)
            menu.addAction("⇩  Örnek CSV indir").triggered.connect(self.download_sample_csv)
            menu.addAction("🧾  Faturadan oku (PDF / fotoğraf)…").triggered.connect(self.import_invoices)
        if self.project.building_id is not None:
            menu.addAction("✎  Bu binayı düzenle").triggered.connect(self.edit_building)
        if self.store.count() > 1 and self.project.building_id is not None:
            menu.addAction("Bu binayı sil").triggered.connect(self.delete_current)
        menu.exec(self.bldg_btn.mapToGlobal(self.bldg_btn.rect().topLeft() - self.bldg_btn.rect().bottomLeft()))

    def add_building(self):
        choice = AddChoiceDialog(self)
        if choice.exec() != AddChoiceDialog.Accepted:
            return
        tariffs = self.project.assumptions.default_tariffs
        if choice.choice == "form":
            dlg = BuildingDialog(self, tariffs=tariffs)
        else:
            try:
                building, readings, equipment, _ = read_workbook(choice.path, tariffs)
            except ValidationError as e:
                self._show_excel_errors(e.errors)
                return
            imported = Project(building, readings, equipment, [], Assumptions())
            dlg = BuildingDialog(self, project=imported, tariffs=tariffs, review=True)
        if dlg.exec() == BuildingDialog.Accepted and dlg.result_data:
            building, readings, equipment = dlg.result_data
            bid = self.store.save_building(building, readings, equipment)
            self.set_project(self.store.load_project(bid), select=0)
            self.notify(f"«{building.name}» eklendi ve açıldı")

    def _show_excel_errors(self, errors: list[str]):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Excel dosyası yüklenemedi")
        box.setText("Excel dosyasında düzeltilmesi gerekenler var")
        shown = errors[:12]
        more = f"\n… ve {len(errors) - 12} hata daha" if len(errors) > 12 else ""
        box.setInformativeText("•  " + "\n•  ".join(shown) + more + "\n\nDosyayı düzeltip tekrar yükleyin.")
        box.exec()

    def download_sample_csv(self):
        from ..bulk_import import sample_csv
        path, _ = QFileDialog.getSaveFileName(self, "Örnek CSV'yi kaydet", "EDIFICE_tuketim_ornek.csv", "CSV (*.csv)")
        if path:
            sample_csv(path, self.project.readings)
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def import_consumption(self):
        """Fatura dökümü (CSV/Excel) -> önizleme (kaç kayıt, hangi dönem, uyarılar, veri kalitesi önce/sonra) -> onayla -> birleştir."""
        from ..bulk_import import merge_readings, parse_file
        from ..quality import assess
        path, _ = QFileDialog.getOpenFileName(self, "Tüketim dosyası seç", "", "CSV veya Excel (*.csv *.xlsx *.xlsm)")
        if not path:
            return
        res = parse_file(path, self.project.assumptions.default_tariffs)
        box = QMessageBox(self)
        box.setWindowTitle("Tüketimi içe aktar")
        if not res.readings:
            box.setIcon(QMessageBox.Warning)
            box.setText("Dosyadan tüketim kaydı okunamadı")
            box.setInformativeText("•  " + "\n•  ".join(res.warnings[:8] or ["Dosya boş görünüyor."]) +
                                   "\n\nİpucu: menüden «Örnek CSV indir» ile beklenen biçimi görebilirsiniz.")
            box.exec()
            return
        merged, added, replaced = merge_readings(self.project.readings, res.readings)
        before = assess(self.project)
        after = assess(Project(self.project.building, merged, self.project.equipment, [], self.project.assumptions))
        (y0, m0), (y1, m1) = res.period
        box.setIcon(QMessageBox.Question)
        box.setText(f"{len(res.readings)} kayıt okundu ({m0}/{y0} – {m1}/{y1})")
        shown = res.warnings[:6]
        more = f"\n•  … ve {len(res.warnings) - 6} uyarı daha" if len(res.warnings) > 6 else ""
        box.setInformativeText(
            f"Yeni eklenecek: {added} · mevcut kaydı değişecek: {replaced}\n"
            f"Veri güvenilirliği: {before.score:.0f} ({before.level}) → {after.score:.0f} ({after.level})"
            + (("\n\nUyarılar:\n•  " + "\n•  ".join(shown) + more) if shown else "") + "\n\nİçe aktarılsın mı?")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        box.button(QMessageBox.Yes).setText("İçe aktar")
        box.button(QMessageBox.Cancel).setText("Vazgeç")
        if box.exec() != QMessageBox.Yes:
            return
        self.store.update_building(self.project.building_id, self.project.building, merged, self.project.equipment)
        self.set_project(self.store.load_project(self.project.building_id))
        self.notify(f"{added + replaced} tüketim kaydı içe aktarıldı (yeni {added}, güncellenen {replaced})")

    def import_invoices(self):
        """Fatura PDF/fotoğraflarını okur -> dosya dosya ne okunduğunu gösterir -> onayla -> birleştirir."""
        from ..bulk_import import merge_readings
        from ..invoice import read_invoices
        from ..models import UTILITY_UNITS
        from ..quality import assess
        paths, _ = QFileDialog.getOpenFileNames(self, "Fatura dosyalarını seç", "", "Fatura (*.pdf *.png *.jpg *.jpeg *.tif *.tiff)")
        if not paths:
            return
        readings, items = read_invoices(paths, self.project.assumptions.default_tariffs)
        box = QMessageBox(self)
        box.setWindowTitle("Faturadan oku")
        lines = []
        for it in items:
            if it.complete:
                cost = f"{it.cost:,.0f} ₺".replace(",", ".") if it.cost is not None else "tutar yok (tarifeyle tahmin)"
                lines.append(f"✓ {it.source}: {it.month}/{it.year} {it.utility.value} {it.consumption:,.0f} {UTILITY_UNITS[it.utility]}, {cost}".replace(",", "."))
            else:
                lines.append(f"✗ {it.source}: okunamadı")
            lines += [f"      – {w}" for w in it.warnings[:3]]
        if not readings:
            box.setIcon(QMessageBox.Warning)
            box.setText("Faturalardan kayıt okunamadı")
            box.setInformativeText("\n".join(lines[:16]) + "\n\nİpucu: metin katmanlı PDF en iyi sonucu verir; fotoğraf için Tesseract OCR kurulu olmalı.")
            box.exec()
            return
        merged, added, replaced = merge_readings(self.project.readings, readings)
        before = assess(self.project)
        after = assess(Project(self.project.building, merged, self.project.equipment, [], self.project.assumptions))
        box.setIcon(QMessageBox.Question)
        box.setText(f"{len(readings)} fatura kaydı okundu")
        box.setInformativeText("\n".join(lines[:16]) + f"\n\nYeni: {added} · değişecek: {replaced}\n"
                               f"Veri güvenilirliği: {before.score:.0f} ({before.level}) → {after.score:.0f} ({after.level})\n"
                               "Rakamları faturayla karşılaştırın. Eklensin mi?")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        box.button(QMessageBox.Yes).setText("Ekle")
        box.button(QMessageBox.Cancel).setText("Vazgeç")
        if box.exec() != QMessageBox.Yes:
            return
        self.store.update_building(self.project.building_id, self.project.building, merged, self.project.equipment)
        self.set_project(self.store.load_project(self.project.building_id))
        self.notify(f"Faturalardan {added + replaced} kayıt eklendi")

    def edit_building(self):
        dlg = BuildingDialog(self, project=self.project, tariffs=self.project.assumptions.default_tariffs)
        if dlg.exec() == BuildingDialog.Accepted and dlg.result_data:
            building, readings, equipment = dlg.result_data
            self.store.update_building(self.project.building_id, building, readings, equipment)
            self.set_project(self.store.load_project(self.project.building_id))
            self.notify("Bina bilgileri kaydedildi, tüm hesaplar güncellendi")

    def _settings_saved(self):
        self.set_project(self.store.load_project(self.project.building_id), select=self.idx['Ayarlar'], notify=True)

    def delete_current(self):
        name = self.project.building.name
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Binayı sil")
        box.setText(f"«{name}» silinsin mi?")
        box.setInformativeText("Binanın tüketim, ekipman, proje ve senaryo kayıtları da silinir. Bu işlem geri alınamaz "
                               "(günlük otomatik yedekten geri dönülebilir).")
        yes = box.addButton("Sil", QMessageBox.DestructiveRole)
        no = box.addButton("Vazgeç", QMessageBox.RejectRole)
        box.setDefaultButton(no)
        box.exec()
        if box.clickedButton() is not yes:
            return
        self.store.delete_building(self.project.building_id)
        self.set_project(self.store.load_project(self.store.latest_id()), select=0)
        self.notify(f"«{name}» silindi", kind="info")

    @staticmethod
    def _short(name: str, n: int = 28) -> str:
        return name if len(name) <= n else name[: n - 1] + "…"

    def _toggle_dot(self):
        self._dot_on = not self._dot_on
        dot = "●" if self._dot_on else "○"
        self.live.setText(f"{dot}  {self._short(self.project.building.name)}")

    def run_action(self, action: tuple):
        """Asistanın komutlarını uygular: proje durumu, sayfa açma, senaryo seçme, rapor."""
        kind = action[0]
        if kind == "status":
            _, code, status, year = action
            tr = self.sub["Proje takibi"]
            if code in tr.combos:
                if year:
                    tr.spins[code].setValue(max(year, tr.spins[code].minimum()))
                tr.combos[code].setCurrentText(status)
                tr._changed(code)          # aynı değerde bile kaydet ve zaman çizelgesini güncelle
        elif kind == "open":
            self.go(action[1], action[2])
        elif kind == "scenario":
            sc = self.sub["Mevcut vs Hedef"]
            for code, btn in sc.checks.items():
                btn.setChecked(code in action[1])
            self.go("Projeler", "Mevcut vs Hedef")
        elif kind == "report":
            self.export_report()

    def go(self, page: str, tab: str | None = None):
        self.select(self.idx[page])
        if tab:
            tp = self.pages[self.idx[page]][1]
            names = list(tp.tabs)
            if tab in names:
                tp.group.button(names.index(tab)).click()

    def _all_projects(self) -> dict:
        return {bid: self.store.load_project(bid) for bid, _ in self.store.list_buildings()}

    def _start_weather(self, project):
        if not hasattr(self, "_weather_loader"):
            self._weather_loader = WeatherLoader(self)
            self._weather_loader.done.connect(self._on_weather)
        self._weather_loader.load(self.store, project)

    def _refresh_climate(self):
        if not hasattr(self, "_climate_loader"):
            self._climate_loader = ClimateLoader(self)
            self._climate_loader.done.connect(self._on_climate)
            self._climate_timer = QTimer(self)             # uygulama açıkken 30 dakikada bir canlı veriyi yenile
            self._climate_timer.timeout.connect(self._refresh_climate)
            self._climate_timer.start(30 * 60 * 1000)
        self._climate_loader.refresh(self.store, self.project)

    def _on_climate(self, bid, data, status, fetched):
        if bid != self.project.building_id:
            return
        from .. import weather as _wx
        if data is not None:
            name, icon = _wx.describe(data["current"]["code"])
            self.wx.setText(f"{icon} {data['current']['temp']:.0f}°C")
            self.wx.setToolTip(f"{name} · hissedilen {data['current']['feels']:.0f}°C · {self.project.building.name}" + ("" if status == "ok" else " (çevrimdışı, son veri)"))
            self.wx.show()
        else:
            self.wx.hide()
        page = self.sub.get("İklim")
        if page is not None:
            page.set_data(data, status, fetched)

    def _start_solar(self, project):
        if not hasattr(self, "_solar_loader"):
            self._solar_loader = SolarLoader(self)
            self._solar_loader.done.connect(self._on_solar)
        self._solar_loader.load(self.store, project)

    def _on_solar(self, monthly, status):
        page = self.sub.get("GES")
        if page is not None:
            page.set_yield(monthly, status)

    def _on_weather(self, bid, dd, status):
        if bid != self.project.building_id:
            return                          # kullanıcı bu arada başka binaya geçti
        from ..engine.weather_norm import normalize
        b = self.project.building
        if dd and b.lat is not None:                       # arşivin gecikmesini son günlerin canlı gözlemleriyle kapat
            from .. import weather as _wx
            dd = _wx.merge_recent(dd, self.store.load_weather_daily(b.lat, b.lon))
        self._dd = dd
        wn = normalize(self.project, dd) if dd else None
        ov = self.sub.get("Genel Bakış")
        if ov is not None and hasattr(ov, "set_weather"):
            ov.set_weather(wn, status)
        cl = self.sub.get("İklim")
        if cl is not None:
            cl.set_dd(dd or {})
        tr = self.sub.get("Proje takibi")
        if tr is not None:
            tr.set_weather(dd)

    def _projects_changed(self, rows):
        ov = self.sub.get("Genel Bakış")
        if ov is not None:
            ov.timeline.set_rows(rows)

    def open_building(self, bid: int):
        self.set_project(self.store.load_project(bid), select=0)

    def _search(self, text: str):
        """Portföy sayfasını arama metnine göre yeniden kurar. Yazınca Portföy'e geçer; arama temizlenince
        kullanıcıyı başka sayfaya sürüklemez."""
        text = text.strip()
        if text == getattr(self, "_last_search", ""):
            return
        self._last_search = text
        page = PortfolioPage(self.store, self.open_building, text)
        i = self.idx["Portföy"]
        old = self.stack.widget(i)
        self.stack.removeWidget(old)
        old.deleteLater()
        self.stack.insertWidget(i, page.widget)
        self.pages[i] = (self.pages[i][0], page)
        if text or self.cur == i:
            if self.cur == i:
                self.stack.setCurrentWidget(page.widget)
            else:
                self.select(i)

    # ---- akıcılık yardımcıları: kısayollar, komut paleti, geri/ileri, bildirim, oturum hafızası -------------

    @staticmethod
    def _keys(seq) -> str:
        """Kısayolu işletim sisteminin diliyle gösterir (macOS'ta ⌘K, Windows'ta Ctrl+K)."""
        ks = QKeySequence(seq) if not isinstance(seq, QKeySequence) else seq
        return ks.toString(QKeySequence.NativeText)

    def _tick_clock(self):
        now = datetime.now()
        self.date.setText(f"{now.day} {TR_MONTHS[now.month - 1]} {now.year} · {now:%H:%M}")

    def _tab_of(self, index: int) -> str | None:
        if not self.pages or index >= len(self.pages):
            return None
        tp = self.pages[index][1]
        return tp.current() if isinstance(tp, TabsPage) and len(tp.names) > 1 else None

    def _tab_changed(self, page):
        if self.pages and self.pages[self.cur][1] is page:
            self._update_crumb()

    def _update_crumb(self):
        name = self.pages[self.cur][0]
        self.crumb.setText(name)
        self.crumb1.setText("Platform" if self.cur < 5 else "Intelligence")
        tab = self._tab_of(self.cur)
        self.crumb_tab.setText(f"/   {tab}" if tab and tab != name else "")
        self.setWindowTitle(f"EDIFI'CE · {name}" + (f" · {tab}" if tab and tab != name else ""))

    def notify(self, text: str, kind: str = "ok", action=None):
        self.toast.show_message(text, kind, action)

    def _shortcut(self, seq, fn):
        sc = QShortcut(QKeySequence(seq), self)
        sc.setContext(Qt.WindowShortcut)
        sc.activated.connect(fn)
        return sc

    def _install_shortcuts(self):
        for i in range(min(10, len(self.nav_specs))):
            key = f"Ctrl+{(i + 1) % 10}"
            self._shortcut(key, lambda idx=i: self.select(idx))
            self.buttons[i].setToolTip(f"{self.nav_specs[i][0]}  ({self._keys(key)})")
        self._shortcut("Ctrl+K", self.open_palette)
        self._shortcut("Ctrl+F", self.focus_search)
        self._shortcut("Ctrl+N", self.add_building)
        self._shortcut("Ctrl+P", self.export_report)
        self._shortcut("Ctrl+B", self.show_building_menu)
        self._shortcut("Ctrl+E", lambda: self.project.building_id is not None and self.edit_building())
        self._shortcut("Ctrl+I", lambda: self.project.building_id is not None and self.import_consumption())
        self._shortcut("F1", self.show_shortcuts)
        self._shortcut("Ctrl+/", self.show_shortcuts)
        for seq, d in ((QKeySequence.NextChild, 1), ("Ctrl+PgDown", 1), (QKeySequence.PreviousChild, -1), ("Ctrl+PgUp", -1)):
            self._shortcut(seq, lambda d=d: self.step_tab(d))
        for seq, fn in ((QKeySequence.Back, self.back), ("Alt+Left", self.back), (QKeySequence.Forward, self.forward),
                        ("Alt+Right", self.forward)):
            self._shortcut(seq, fn)
        esc = QShortcut(QKeySequence("Esc"), self.search)
        esc.setContext(Qt.WidgetShortcut)
        esc.activated.connect(lambda: (self.search.clear(), self.stack.setFocus()))

    def focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def step_tab(self, delta: int):
        tp = self.pages[self.cur][1]
        if isinstance(tp, TabsPage):
            tp.step(delta)

    def _goto(self, index: int, tab: str | None):
        self.select(index, record=False)
        if tab:
            tp = self.pages[index][1]
            if isinstance(tp, TabsPage):
                tp.select(tab)

    def back(self):
        if self._history:
            self._future.append((self.cur, self._tab_of(self.cur)))
            self._goto(*self._history.pop())

    def forward(self):
        if self._future:
            self._history.append((self.cur, self._tab_of(self.cur)))
            self._goto(*self._future.pop())

    def commands(self) -> list[Command]:
        cmds: list[Command] = []
        for i, (name, page) in enumerate(self.pages):
            sc = self._keys(f"Ctrl+{(i + 1) % 10}") if i < 10 else ""
            cmds.append(Command(name, "Sayfa", lambda i=i: self.select(i), KEYWORDS.get(name, ""), sc))
            if isinstance(page, TabsPage) and len(page.names) > 1:
                for t in page.names:
                    if t != name:
                        cmds.append(Command(f"{name}  ›  {t}", "Sekme", lambda n=name, t=t: self.go(n, t), KEYWORDS.get(t, "")))
        has_id = self.project.building_id is not None
        acts = [("PDF raporu oluştur", self.export_report, "rapor indir yatırımcı", "Ctrl+P"),
                ("Yeni bina ekle", self.add_building, "bina oluştur form excel şablon", "Ctrl+N"),
                ("Bina ara", self.focus_search, "filtre", "Ctrl+F"),
                ("Uyarıları göster", self.show_alerts, "bildirim alarm", ""),
                ("ESG veri paketi (Excel)", lambda: self.export_pack("esg"), "rapor excel kapsam", ""),
                ("EKB hazırlık sayfası (Excel)", lambda: self.export_pack("ekb"), "enerji kimlik belgesi", ""),
                ("Portföy özeti (Excel)", lambda: self.export_pack("portfoy"), "tüm binalar rapor", ""),
                ("Klavye kısayolları", self.show_shortcuts, "yardım tuş", "F1")]
        if has_id:
            acts[2:2] = [("Bu binayı düzenle", self.edit_building, "bilgi tüketim ekipman değiştir", "Ctrl+E"),
                         ("Tüketimi içe aktar (CSV / Excel)", self.import_consumption, "fatura döküm yükle", "Ctrl+I"),
                         ("Faturadan oku (PDF / fotoğraf)", self.import_invoices, "ocr fatura", ""),
                         ("Örnek CSV indir", self.download_sample_csv, "şablon biçim", "")]
        for title, fn, kw, sc in acts:
            cmds.append(Command(title, "Eylem", fn, kw, self._keys(sc) if sc else ""))
        for bid, bname in self.store.list_buildings():
            if bid != self.project.building_id:
                cmds.append(Command(f"Binaya geç: {bname}", "Bina", lambda b=bid: self.set_project(self.store.load_project(b)), bname))
        return cmds

    def open_palette(self):
        CommandPalette(self, self.commands()).exec()

    def show_shortcuts(self):
        ShortcutsDialog(self, self._keys).exec()

    # ---- oturum hafızası: son bina, sayfa, sekme ve pencere boyutu bir sonraki açılışta geri gelir ----

    @staticmethod
    def _settings() -> QSettings:
        return QSettings("EDIFICE", "EDIFICE")

    @classmethod
    def saved_building_id(cls, store) -> int | None:
        try:
            bid = int(cls._settings().value("session/building", -1))
        except (TypeError, ValueError):
            return None
        return bid if any(b == bid for b, _ in store.list_buildings()) else None

    def restore_session(self):
        """Yalnız gerçek uygulama açılışında (main.py) çağrılır; testler kullanıcı ayarlarına dokunmaz."""
        st = self._settings()
        geo = st.value("session/geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        page = st.value("session/page", "")
        if page in self.idx:
            self._goto(self.idx[page], st.value("session/tab") or None)
        self._persist = True

    def save_session(self):
        st = self._settings()
        st.setValue("session/building", self.project.building_id if self.project.building_id is not None else -1)
        st.setValue("session/page", self.pages[self.cur][0])
        st.setValue("session/tab", self._tab_of(self.cur) or "")
        st.setValue("session/geometry", self.saveGeometry())

    def closeEvent(self, e):
        if self._persist:
            try:
                self.save_session()
            except Exception:
                pass
        super().closeEvent(e)

    def alerts(self) -> list[tuple[int, str]]:
        """Gerçek veriden uyarılar: düşük sağlık skoru, kötü enerji sınıfı, maliyet artışı."""
        out = []
        for bid, name in self.store.list_buildings():
            p = self.store.load_project(bid)
            r = summarize(p)
            if r["health"] < 60:
                out.append((bid, f"{name}: sağlık skoru {r['health']:.0f} (60'ın altında)"))
            if r["rating"] in ("E", "F", "G"):
                out.append((bid, f"{name}: enerji sınıfı {r['rating']} (yeni bina eşiği C)"))
            up = p.yoy().get("cost")
            if up is not None and up > 5:
                out.append((bid, f"{name}: yıllık enerji maliyeti geçen yıla göre %{up:.0f} arttı"))
        return out

    def show_alerts(self):
        menu = QMenu(self)
        items = self.alerts()
        if not items:
            menu.addAction("Yeni uyarı yok").setEnabled(False)
        for bid, text in items:
            menu.addAction(text).triggered.connect(lambda _=False, i=bid: self.open_building(i))
        menu.exec(self.bell.mapToGlobal(self.bell.rect().bottomLeft()))

    def select(self, index: int, record: bool = True):
        if record and index != self.cur:
            self._history.append((self.cur, self._tab_of(self.cur)))
            del self._history[:-30]
            self._future.clear()
        self.nav.select(index)
        self.stack.setCurrentIndex(index)
        self.cur = index
        self._update_crumb()

    def export_pack(self, kind: str):
        """Excel raporlama paketi: esg (seçili bina), ekb (seçili bina), portfoy (tüm binalar)."""
        from .. import reports_xlsx as rx
        names = {"esg": ("EDIFICE_ESG_veri_paketi", rx.build_esg_package), "ekb": ("EDIFICE_EKB_hazirlik", rx.build_ekb_sheet),
                 "portfoy": ("EDIFICE_Portfoy_ozeti", None)}
        stem, fn = names[kind]
        default = f"{stem}_{self.project.building.name.replace(' ', '_') if kind != 'portfoy' else ''}{datetime.now():%Y-%m-%d}.xlsx".replace("__", "_")
        path, _ = QFileDialog.getSaveFileName(self, "Excel paketini kaydet", default, "Excel (*.xlsx)")
        if not path:
            return
        with busy():
            if kind == "portfoy":
                rx.build_portfolio_workbook(list(self._all_projects().values()), path)
            else:
                fn(self.project, path)
        self.store.add_record("report_log", {"building_id": None if kind == "portfoy" else self.project.building_id,
                                             "kind": {"esg": "ESG veri paketi", "ekb": "EKB hazırlık sayfası", "portfoy": "Portföy özeti"}[kind], "path": path})
        self.report_page.refresh_history()
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        self.notify(f"{Path(path).name} kaydedildi", action=("Klasörü aç", lambda: _open_folder(path)))

    def export_report(self):
        codes = self.sub['Mevcut vs Hedef'].selected_codes()
        default = f"EDIFICE_{self.project.building.name.replace(' ', '_')}_{datetime.now():%Y-%m-%d}.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "Raporu kaydet", default, "PDF (*.pdf)")
        if not path:
            return
        with busy():
            build_pdf(self.project, codes, path)
        self.store.add_record("report_log", {"building_id": self.project.building_id, "kind": "PDF yatırımcı raporu", "path": path})
        self.report_page.refresh_history()
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        n = len(codes)
        self.notify(f"PDF raporu kaydedildi ({n} öneriyle)" if n else "PDF raporu kaydedildi (öneri seçilmedi: yalnız mevcut durum)",
                    action=("Klasörü aç", lambda: _open_folder(path)))


@contextmanager
def busy():
    """Uzun süren işlerde (bina değişimi, PDF/Excel üretimi) bekleme imleci: uygulama donmuş gibi görünmesin."""
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()


def _open_folder(path: str):
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))


def section_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setObjectName("section")
    return lbl
