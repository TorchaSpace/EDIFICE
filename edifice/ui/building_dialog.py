"""Bina Ekle penceresi: bina bilgisi, 12 aylık tüketim ve ekipman girişi."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QCompleter, QDialog, QDoubleSpinBox,
                               QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QPushButton, QScrollArea, QSpinBox, QTabBar, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..validation import (COLUMNS, EQUIPMENT_CATEGORIES, EQUIPMENT_NAMES, MONTH_NAMES, USE_TYPES, ValidationError,
                          build_from_inputs)
from .dropdown import PremiumCombo
from .forms import field, scroll, tune_spin
from .widgets import FadeStack, Panel, header, muted, qfont


def make_item(text: str, col: int) -> QTableWidgetItem:
    """Tüketim hücresi: sağa hizalı, mono; tutar sütunları hafif tonlu."""
    it = QTableWidgetItem(text)
    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    it.setFont(qfont(13, mono=True))
    if col % 2 == 1:
        it.setBackground(QColor(255, 255, 255, 7))
    return it


class PasteTable(QTableWidget):
    """Excel'den kopyalanan (sekme/satır ayrımlı) veriyi seçili hücreden itibaren yapıştırır."""

    def keyPressEvent(self, e):
        if e.matches(QKeySequence.Paste):
            text = QGuiApplication.clipboard().text()
            r0, c0 = max(self.currentRow(), 0), max(self.currentColumn(), 0)
            for i, line in enumerate(l for l in text.splitlines() if l.strip()):
                for j, cell in enumerate(line.split("\t")):
                    r, c = r0 + i, c0 + j
                    if r < self.rowCount() and c < self.columnCount():
                        self.setItem(r, c, make_item(cell.strip(), c))
            return
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace) and not self.state() == QAbstractItemView.EditingState:
            for it in self.selectedItems():
                it.setText("")
            return
        super().keyPressEvent(e)


_field, _tune_spin, _scroll = field, tune_spin, scroll


class BuildingDialog(QDialog):
    def __init__(self, parent=None, project=None, tariffs: dict | None = None, review: bool = False):
        super().__init__(parent)
        self.editing = project if not review else None
        self.review = review
        self.tariffs = tariffs
        self.setWindowTitle("Binayı Gözden Geçir" if review else "Binayı Düzenle" if project else "Bina Ekle")
        screen = QGuiApplication.primaryScreen()
        avail = screen.availableGeometry().height() if screen else 900
        self.resize(1100, max(640, min(880, avail - 60)))
        self.setMinimumSize(900, 600)
        self.result_data = None
        self.base_year = date.today().year - 1

        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 30, 36, 26)
        lay.setSpacing(16)
        lay.addWidget(header("Excel'den okundu" if review else "Düzenle" if project else "Yeni bina",
                             "Binayı Gözden Geçir" if review else "Binayı Düzenle" if project else "Bina Ekle",
                             ("Excel dosyasındaki veriler aşağıya aktarıldı. Kontrol edin, gerekirse düzeltin ve kaydedin."
                              if review else "Üç kısa adımda binayı tanımlayın: bina bilgisi, son yılın aylık tüketimi ve "
                              "(isteğe bağlı) ekipmanlar. * işaretli alanlar zorunludur.")))

        self.tabbar = QTabBar()
        self.tabbar.setDrawBase(False)
        self.tabbar.setExpanding(False)
        self.tabbar.setCursor(Qt.PointingHandCursor)
        for name in ("1   Bina bilgisi", "2   Tüketim", "3   Ekipman"):
            self.tabbar.addTab(name)
        lay.addWidget(self.tabbar)
        self.pages = FadeStack()
        self.pages.addWidget(_scroll(self._info_tab()))
        self.pages.addWidget(_scroll(self._usage_tab()))
        self.pages.addWidget(_scroll(self._equipment_tab()))
        self.tabbar.currentChanged.connect(self.pages.setCurrentIndex)
        lay.addWidget(self.pages, 1)

        self.error = QLabel("")
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        self._err_fx = QGraphicsOpacityEffect(self.error)
        self.error.setGraphicsEffect(self._err_fx)
        self._err_anim = QPropertyAnimation(self._err_fx, b"opacity", self)
        self._err_anim.setDuration(380)
        self._err_anim.setEasingCurve(QEasingCurve.OutQuart)
        lay.addWidget(self.error)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()
        cancel = QPushButton("İptal")
        cancel.setObjectName("secondary")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        save = QPushButton("Değişiklikleri kaydet" if self.editing else "Binayı kaydet")
        save.setObjectName("primary")
        save.setCursor(Qt.PointingHandCursor)
        save.clicked.connect(self.save)
        row.addWidget(cancel)
        row.addWidget(save)
        lay.addLayout(row)

        if project:
            self._prefill(project)
        self._open_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._open_anim.setDuration(320)
        self._open_anim.setStartValue(0.0)
        self._open_anim.setEndValue(1.0)
        self._open_anim.setEasingCurve(QEasingCurve.OutQuart)

    def showEvent(self, e):
        super().showEvent(e)
        self._open_anim.start()

    # ---- sekme 1
    def _info_tab(self) -> QWidget:
        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(16)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Örn. Merkez Ofis Binası")
        self.address = QLineEdit()
        self.address.setPlaceholderText("İl / ilçe / adres")
        self.use_type = PremiumCombo()
        self.use_type.addItems(USE_TYPES)
        self.area = _tune_spin(QDoubleSpinBox())
        self.area.setRange(0, 5_000_000)
        self.area.setDecimals(0)
        self.area.setSuffix(" m²")
        self.area.setGroupSeparatorShown(True)
        self.year_built = _tune_spin(QSpinBox())
        self.year_built.setRange(1800, date.today().year)
        self.year_built.setValue(2000)
        self.floors = _tune_spin(QSpinBox())
        self.floors.setRange(1, 200)
        self.occupants = _tune_spin(QSpinBox())
        self.occupants.setRange(0, 100000)
        for w in (self.name, self.address, self.use_type):
            w.setMinimumHeight(40)

        general = Panel("Genel bilgiler", "Binayı tanımlayan temel bilgiler")
        g = QGridLayout()
        g.setHorizontalSpacing(18)
        g.setVerticalSpacing(14)
        g.addWidget(_field("Bina adı *", self.name, "Raporlarda ve bina listesinde görünecek ad"), 0, 0, 1, 2)
        g.addWidget(_field("Kullanım tipi", self.use_type, "Binanın ana işlevi"), 0, 2)
        g.addWidget(_field("Adres", self.address, "İsteğe bağlı: il, ilçe ve açık adres"), 1, 0, 1, 3)
        for c in range(3):
            g.setColumnStretch(c, 1)
        general.lay.addSpacing(6)
        general.lay.addLayout(g)

        phys = Panel("Fiziksel özellikler", "Enerji yoğunluğu (kWh/m²) bu değerlerle hesaplanır")
        g2 = QGridLayout()
        g2.setHorizontalSpacing(18)
        g2.setVerticalSpacing(14)
        g2.addWidget(_field("Brüt kullanım alanı *", self.area, "Tüm katların toplam alanı (m²)"), 0, 0)
        g2.addWidget(_field("Yapım yılı", self.year_built, "İnşaatın tamamlandığı yıl"), 0, 1)
        g2.addWidget(_field("Kat sayısı", self.floors, "Zemin ve bodrum dahil"), 0, 2)
        g2.addWidget(_field("Kullanıcı / çalışan sayısı", self.occupants, "Günlük ortalama kişi sayısı"), 1, 0)
        for c in range(3):
            g2.setColumnStretch(c, 1)
        phys.lay.addSpacing(6)
        phys.lay.addLayout(g2)
        lay.addWidget(general)
        lay.addWidget(phys)
        lay.addStretch()
        return host

    # ---- sekme 2
    def _usage_tab(self) -> QWidget:
        panel = Panel("Aylık tüketim", "Faturalardaki aylık değerleri yazın ya da Excel'den kopyalayıp bir hücreye yapıştırın (Cmd+V).")
        chips = QHBoxLayout()
        chips.setSpacing(8)
        req = QLabel("Zorunlu: kWh ve m³ sütunları")
        req.setObjectName("chipReq")
        opt = QLabel("İsteğe bağlı: ₺ tutar sütunları (boşsa varsayılan tarife)")
        opt.setObjectName("chipOpt")
        chips.addWidget(req)
        chips.addWidget(opt)
        chips.addStretch()
        panel.lay.addLayout(chips)
        panel.lay.addSpacing(6)
        top = QHBoxLayout()
        self.year = _tune_spin(QSpinBox())
        self.year.setRange(1990, date.today().year)
        self.year.setValue(self.base_year)
        self.year.valueChanged.connect(self._year_changed)
        self.year.setFixedWidth(130)
        top.addWidget(_field("Baz yıl", self.year, "Son tam 12 ay"))
        top.addSpacing(24)
        self.sub_bar = QTabBar()
        self.sub_bar.setDrawBase(False)
        self.sub_bar.setExpanding(False)
        self.sub_bar.setCursor(Qt.PointingHandCursor)
        self.sub_bar.addTab("")
        self.sub_bar.addTab("")
        top.addWidget(self.sub_bar, 0, Qt.AlignBottom)
        top.addStretch()
        panel.lay.addLayout(top)

        self.grids: dict[str, QTableWidget] = {}
        self.grid_stack = FadeStack()
        for key in ("base", "prev"):
            t = PasteTable(12, 6)
            heads = ["Elektrik (kWh)", "Elektrik tutarı (₺)", "Doğalgaz (kWh)", "Doğalgaz tutarı (₺)",
                     "Su (m³)", "Su tutarı (₺)"]
            t.setHorizontalHeaderLabels(heads)
            t.setVerticalHeaderLabels(MONTH_NAMES)
            t.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
            t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            t.verticalHeader().setDefaultSectionSize(31)
            t.horizontalHeader().setFixedHeight(40)
            t.verticalHeader().setFixedWidth(92)
            t.setEditTriggers(QAbstractItemView.AllEditTriggers)
            t.setSelectionMode(QAbstractItemView.ExtendedSelection)
            t.setShowGrid(False)
            t.setFocusPolicy(Qt.StrongFocus)
            for r in range(12):
                for c in range(6):
                    t.setItem(r, c, make_item("", c))
            self.grids[key] = t
            self.grid_stack.addWidget(t)
        self.sub_bar.currentChanged.connect(self.grid_stack.setCurrentIndex)
        self.grid_stack.setMinimumHeight(12 * 31 + 48)
        panel.lay.addWidget(self.grid_stack, 1)
        self._year_changed()
        return panel

    def _year_changed(self, *_):
        y = self.year.value()
        self.sub_bar.setTabText(0, f"Baz yıl {y}")
        self.sub_bar.setTabText(1, f"Önceki yıl {y - 1}  (isteğe bağlı, trend için)")

    # ---- sekme 3
    def _equipment_tab(self) -> QWidget:
        panel = Panel("Ekipman envanteri", "Saha etüdünden HVAC, aydınlatma ve bina kabuğu ekipmanlarını ekleyin. Bu adım isteğe bağlıdır.")
        self.eq = QTableWidget(0, 5)
        self.eq.setHorizontalHeaderLabels(["Kategori", "Ekipman adı", "Kurulum yılı", "Durum (1 kötü – 5 iyi)", "Not"])
        hh = self.eq.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Stretch)
        for col, width in ((0, 180), (2, 140), (3, 190)):
            hh.setSectionResizeMode(col, QHeaderView.Fixed)
            self.eq.setColumnWidth(col, width)
        self.eq.verticalHeader().setVisible(False)
        self.eq.verticalHeader().setDefaultSectionSize(56)
        self.eq.setShowGrid(False)
        self.eq.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.eq.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.empty = QLabel("Henüz ekipman eklenmedi.\nBaşlamak için aşağıdaki «+ Ekipman ekle» düğmesine basın.")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setObjectName("muted")
        self.eq.setMinimumHeight(260)
        self.empty.setMinimumHeight(260)
        panel.lay.addWidget(self.eq, 1)
        panel.lay.addWidget(self.empty, 1)
        row = QHBoxLayout()
        row.setSpacing(10)
        add = QPushButton("+ Ekipman ekle")
        add.setObjectName("secondary")
        add.setCursor(Qt.PointingHandCursor)
        add.clicked.connect(lambda: self.add_equipment_row())
        rm = QPushButton("Seçiliyi sil")
        rm.setObjectName("secondary")
        rm.setCursor(Qt.PointingHandCursor)
        rm.clicked.connect(self.remove_equipment_row)
        row.addWidget(add)
        row.addWidget(rm)
        row.addStretch()
        panel.lay.addLayout(row)
        self._sync_empty()
        return panel

    def _sync_empty(self):
        has = self.eq.rowCount() > 0
        self.eq.setVisible(has)
        self.empty.setVisible(not has)

    @staticmethod
    def _cell(w: QWidget) -> QWidget:
        """Hücre içeriğine nefes payı bırakan kapsayıcı."""
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(w)
        box.inner = w
        return box

    def add_equipment_row(self, data: dict | None = None):
        r = self.eq.rowCount()
        self.eq.insertRow(r)
        cat = PremiumCombo()
        cat.addItems(EQUIPMENT_CATEGORIES)
        name = QLineEdit()
        if data:
            cat.setCurrentText(data["category"])
            name.setText(data["name"])
        name.setObjectName("cellInput")
        name.setPlaceholderText("Yazın ya da listeden seçin · örn. Su soğutmalı chiller")
        comp = QCompleter(EQUIPMENT_NAMES, name)
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setFilterMode(Qt.MatchContains)
        comp.setCompletionMode(QCompleter.PopupCompletion)
        name.setCompleter(comp)
        yr = _tune_spin(QSpinBox())
        yr.setRange(1900, date.today().year)
        yr.setValue(2010)
        cond = _tune_spin(QSpinBox())
        cond.setRange(1, 5)
        cond.setValue(3)
        note = QLineEdit()
        if data:
            yr.setValue(data["year_installed"])
            cond.setValue(data["condition"])
            note.setText(data["notes"])
        note.setObjectName("cellInput")
        note.setPlaceholderText("İsteğe bağlı not")
        for col, w in enumerate((cat, name, yr, cond, note)):
            w.setMinimumHeight(38)
            self.eq.setCellWidget(r, col, self._cell(w))
        self._sync_empty()
        self.eq.setCurrentCell(r, 1)
        if not data:
            name.setFocus()

    def _prefill(self, p):
        b = p.building
        self.name.setText(b.name)
        self.address.setText(b.address)
        self.use_type.setCurrentText(b.use_type)
        self.area.setValue(b.floor_area_m2)
        self.year_built.setValue(b.year_built)
        self.floors.setValue(b.floors)
        self.occupants.setValue(b.occupants)
        self.year.setValue(p.year)
        col = {"electricity": 0, "gas": 2, "water": 4}
        for r in p.readings:
            key = "base" if r.year == p.year else "prev" if r.year == p.year - 1 else None
            if key is None:
                continue
            c = col[r.utility.value]
            self.grids[key].setItem(r.month - 1, c, make_item(f"{r.consumption:.0f}", c))
            self.grids[key].setItem(r.month - 1, c + 1, make_item(f"{r.cost:.0f}", c + 1))
        for e in p.equipment:
            self.add_equipment_row(dict(category=e.category, name=e.name, year_installed=e.year_installed,
                                        condition=e.condition, notes=e.notes))

    def remove_equipment_row(self):
        r = self.eq.currentRow()
        if r >= 0:
            self.eq.removeRow(r)
        self._sync_empty()

    # ---- toplama / kaydetme
    def collect(self):
        info = dict(name=self.name.text(), address=self.address.text(), use_type=self.use_type.currentText(),
                    floor_area_m2=self.area.value(), year_built=self.year_built.value(),
                    floors=self.floors.value(), occupants=self.occupants.value())

        def grid_text(t: QTableWidget):
            return [[(t.item(r, c).text() if t.item(r, c) else "") for c in range(6)] for r in range(12)]

        y = self.year.value()
        grids = {y: grid_text(self.grids["base"]), y - 1: grid_text(self.grids["prev"])}
        eq = []
        for r in range(self.eq.rowCount()):
            w = [self.eq.cellWidget(r, c).inner for c in range(5)]
            eq.append(dict(category=w[0].currentText(), name=w[1].text(), year_installed=w[2].value(),
                           condition=w[3].value(), notes=w[4].text()))
        return build_from_inputs(info, grids, eq, y, self.tariffs)

    def _show_error(self, text: str):
        self.error.setText(text)
        self._err_anim.stop()
        self._err_anim.setStartValue(0.0)
        self._err_anim.setEndValue(1.0 if text else 0.0)
        self._err_anim.start()

    def save(self):
        try:
            self.result_data = self.collect()
        except ValidationError as e:
            shown = e.errors[:6]
            more = f"  (+{len(e.errors) - 6} hata daha)" if len(e.errors) > 6 else ""
            self._show_error("Kaydetmeden önce şunları düzeltin:\n•  " + "\n•  ".join(shown) + more)
            first = e.errors[0]
            target = 1 if first.startswith(("Baz yıl", "Önceki yıl")) else 2 if first.startswith("Ekipman") else 0
            if self.tabbar.currentIndex() != target:
                self.tabbar.setCurrentIndex(target)
            return
        self.accept()
