"""Bina Ekle penceresi: bina bilgisi, 12 aylık tüketim ve ekipman girişi."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDoubleSpinBox,
                               QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QPushButton, QSpinBox, QTabBar, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..validation import (COLUMNS, EQUIPMENT_CATEGORIES, MONTH_NAMES, USE_TYPES, ValidationError,
                          build_from_inputs)
from .dropdown import PremiumCombo
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


def _field(label: str, widget: QWidget) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(7)
    lb = QLabel(label)
    lb.setObjectName("field")
    lay.addWidget(lb)
    lay.addWidget(widget)
    return w


def _tune_spin(sp):
    """Spin kutularında metnin kenara yapışmasını önler."""
    sp.lineEdit().setTextMargins(10, 0, 0, 0)
    sp.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    sp.setMinimumHeight(40)
    return sp


class BuildingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bina Ekle")
        screen = QGuiApplication.primaryScreen()
        avail = screen.availableGeometry().height() if screen else 900
        self.resize(1100, max(640, min(880, avail - 60)))
        self.setMinimumSize(900, 600)
        self.result_data = None
        self.base_year = date.today().year - 1

        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 30, 36, 26)
        lay.setSpacing(16)
        lay.addWidget(header("Yeni bina", "Bina Ekle",
                             "Bina bilgilerini, 12 aylık tüketimi ve ekipmanları girin. Fatura tutarı boş "
                             "bırakılırsa varsayılan tarife kullanılır."))

        self.tabbar = QTabBar()
        self.tabbar.setDrawBase(False)
        self.tabbar.setExpanding(False)
        self.tabbar.setCursor(Qt.PointingHandCursor)
        for name in ("1 · Bina bilgisi", "2 · Tüketim", "3 · Ekipman"):
            self.tabbar.addTab(name)
        lay.addWidget(self.tabbar)
        self.pages = FadeStack()
        self.pages.addWidget(self._info_tab())
        self.pages.addWidget(self._usage_tab())
        self.pages.addWidget(self._equipment_tab())
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
        save = QPushButton("Binayı kaydet")
        save.setObjectName("primary")
        save.setCursor(Qt.PointingHandCursor)
        save.clicked.connect(self.save)
        row.addWidget(cancel)
        row.addWidget(save)
        lay.addLayout(row)

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
        g.addWidget(_field("Bina adı *", self.name), 0, 0, 1, 2)
        g.addWidget(_field("Kullanım tipi", self.use_type), 0, 2)
        g.addWidget(_field("Adres", self.address), 1, 0, 1, 3)
        for c in range(3):
            g.setColumnStretch(c, 1)
        general.lay.addSpacing(6)
        general.lay.addLayout(g)

        phys = Panel("Fiziksel özellikler", "Enerji yoğunluğu (kWh/m²) bu değerlerle hesaplanır")
        g2 = QGridLayout()
        g2.setHorizontalSpacing(18)
        g2.setVerticalSpacing(14)
        g2.addWidget(_field("Brüt kullanım alanı *", self.area), 0, 0)
        g2.addWidget(_field("Yapım yılı", self.year_built), 0, 1)
        g2.addWidget(_field("Kat sayısı", self.floors), 0, 2)
        g2.addWidget(_field("Kullanıcı / çalışan sayısı", self.occupants), 1, 0)
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
        panel = Panel("Aylık tüketim", "Doğrudan yazın ya da Excel'den kopyalayıp bir hücreye yapıştırın (Cmd+V). "
                                       "Önceki yıl isteğe bağlıdır; girilirse trend karşılaştırması çıkar.")
        panel.lay.addSpacing(8)
        top = QHBoxLayout()
        self.year = _tune_spin(QSpinBox())
        self.year.setRange(1990, date.today().year)
        self.year.setValue(self.base_year)
        self.year.valueChanged.connect(self._year_changed)
        self.year.setFixedWidth(130)
        top.addWidget(_field("Baz yıl", self.year))
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
            heads = [h for _, a, b in COLUMNS for h in (a, b)]
            t.setHorizontalHeaderLabels([h.upper() for h in heads])
            t.setVerticalHeaderLabels([m.upper() for m in MONTH_NAMES])
            t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            t.verticalHeader().setDefaultSectionSize(31)
            t.horizontalHeader().setFixedHeight(40)
            t.verticalHeader().setFixedWidth(84)
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
        panel.lay.addWidget(self.grid_stack, 1)
        self._year_changed()
        return panel

    def _year_changed(self, *_):
        y = self.year.value()
        self.sub_bar.setTabText(0, f"Baz yıl {y}")
        self.sub_bar.setTabText(1, f"Önceki yıl {y - 1} · isteğe bağlı")

    # ---- sekme 3
    def _equipment_tab(self) -> QWidget:
        panel = Panel("Ekipman envanteri", "Saha etüdünden HVAC, aydınlatma ve bina kabuğu ekipmanlarını ekleyin. "
                                           "Durum: 1 çok kötü, 5 çok iyi. Ekipman girilmezse skor ekipmanı nötr sayar.")
        self.eq = QTableWidget(0, 5)
        self.eq.setHorizontalHeaderLabels(["KATEGORİ", "EKİPMAN", "KURULUM YILI", "DURUM (1-5)", "NOT"])
        hh = self.eq.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Stretch)
        for col, width in ((0, 180), (2, 140), (3, 130)):
            hh.setSectionResizeMode(col, QHeaderView.Fixed)
            self.eq.setColumnWidth(col, width)
        self.eq.verticalHeader().setVisible(False)
        self.eq.verticalHeader().setDefaultSectionSize(56)
        self.eq.setShowGrid(False)
        self.eq.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.empty = QLabel("Henüz ekipman eklenmedi.\n«+ Ekipman ekle» ile başlayın.")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setObjectName("muted")
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
        name.setObjectName("cellInput")
        name.setPlaceholderText("Örn. Su soğutmalı chiller")
        yr = _tune_spin(QSpinBox())
        yr.setRange(1900, date.today().year)
        yr.setValue(2010)
        cond = _tune_spin(QSpinBox())
        cond.setRange(1, 5)
        cond.setValue(3)
        note = QLineEdit()
        note.setObjectName("cellInput")
        note.setPlaceholderText("İsteğe bağlı not")
        for col, w in enumerate((cat, name, yr, cond, note)):
            w.setMinimumHeight(38)
            self.eq.setCellWidget(r, col, self._cell(w))
        self._sync_empty()
        self.eq.setCurrentCell(r, 1)
        name.setFocus()

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
        return build_from_inputs(info, grids, eq, y)

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
            self._show_error("•  " + "\n•  ".join(shown) + more)
            first = e.errors[0]
            target = 1 if first.startswith(("Baz yıl", "Önceki yıl")) else 2 if first.startswith("Ekipman") else 0
            if self.tabbar.currentIndex() != target:
                self.tabbar.setCurrentIndex(target)
            return
        self.accept()
