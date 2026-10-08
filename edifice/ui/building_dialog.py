"""Bina Ekle penceresi: bina bilgisi, 12 aylık tüketim ve ekipman girişi."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QKeySequence
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
                               QTabWidget, QVBoxLayout, QWidget, QHeaderView, QAbstractItemView)

from ..validation import (COLUMNS, EQUIPMENT_CATEGORIES, MONTH_NAMES, USE_TYPES, ValidationError,
                          build_from_inputs)
from .widgets import header, muted


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
                        self.setItem(r, c, QTableWidgetItem(cell.strip()))
            return
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            for it in self.selectedItems():
                it.setText("")
            return
        super().keyPressEvent(e)


def _field(label: str, widget: QWidget) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)
    lb = QLabel(label)
    lb.setObjectName("field")
    lay.addWidget(lb)
    lay.addWidget(widget)
    return w


class BuildingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bina Ekle")
        self.resize(1040, 760)
        self.result_data = None
        self.base_year = date.today().year - 1

        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 24)
        lay.setSpacing(14)
        lay.addWidget(header("Yeni bina", "Bina Ekle",
                             "Bina bilgilerini, 12 aylık tüketimi ve ekipmanları girin. Fatura tutarı boş "
                             "bırakılırsa varsayılan tarife kullanılır."))
        self.tabs = QTabWidget()
        self.tabs.addTab(self._info_tab(), "1 · Bina bilgisi")
        self.tabs.addTab(self._usage_tab(), "2 · Tüketim")
        self.tabs.addTab(self._equipment_tab(), "3 · Ekipman")
        lay.addWidget(self.tabs, 1)

        self.error = QLabel("")
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        lay.addWidget(self.error)
        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton("İptal")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Binayı kaydet")
        save.setObjectName("primary")
        save.setCursor(Qt.PointingHandCursor)
        save.clicked.connect(self.save)
        row.addWidget(cancel)
        row.addWidget(save)
        lay.addLayout(row)

    # ---- sekme 1
    def _info_tab(self) -> QWidget:
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(0, 18, 0, 0)
        g.setHorizontalSpacing(18)
        g.setVerticalSpacing(16)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Örn. Merkez Ofis Binası")
        self.address = QLineEdit()
        self.address.setPlaceholderText("İl / ilçe / adres")
        self.use_type = QComboBox()
        self.use_type.addItems(USE_TYPES)
        self.area = QDoubleSpinBox()
        self.area.setRange(0, 5_000_000)
        self.area.setDecimals(0)
        self.area.setSuffix(" m²")
        self.area.setGroupSeparatorShown(True)
        self.year_built = QSpinBox()
        self.year_built.setRange(1800, date.today().year)
        self.year_built.setValue(2000)
        self.floors = QSpinBox()
        self.floors.setRange(1, 200)
        self.occupants = QSpinBox()
        self.occupants.setRange(0, 100000)
        g.addWidget(_field("Bina adı *", self.name), 0, 0, 1, 2)
        g.addWidget(_field("Kullanım tipi", self.use_type), 0, 2)
        g.addWidget(_field("Adres", self.address), 1, 0, 1, 3)
        g.addWidget(_field("Brüt kullanım alanı *", self.area), 2, 0)
        g.addWidget(_field("Yapım yılı", self.year_built), 2, 1)
        g.addWidget(_field("Kat sayısı", self.floors), 2, 2)
        g.addWidget(_field("Kullanıcı / çalışan sayısı", self.occupants), 3, 0)
        g.setRowStretch(4, 1)
        g.setColumnStretch(0, 1)
        g.setColumnStretch(1, 1)
        g.setColumnStretch(2, 1)
        return w

    # ---- sekme 2
    def _usage_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 18, 0, 0)
        lay.setSpacing(10)
        top = QHBoxLayout()
        self.year = QSpinBox()
        self.year.setRange(1990, date.today().year)
        self.year.setValue(self.base_year)
        self.year.valueChanged.connect(self._year_changed)
        self.year.setFixedWidth(110)
        top.addWidget(_field("Baz yıl", self.year))
        top.addSpacing(16)
        top.addWidget(muted("Aylık tüketimi doğrudan yazın ya da Excel'den kopyalayıp bir hücreye yapıştırın "
                            "(Cmd+V). Önceki yıl isteğe bağlıdır; girilirse trend karşılaştırması çıkar."), 1)
        lay.addLayout(top)
        self.usage_tabs = QTabWidget()
        self.grids: dict[str, QTableWidget] = {}
        for key in ("base", "prev"):
            t = PasteTable(12, 6)
            heads = [h for _, a, b in COLUMNS for h in (a, b)]
            t.setHorizontalHeaderLabels([h.upper() for h in heads])
            t.setVerticalHeaderLabels(MONTH_NAMES)
            t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            t.verticalHeader().setDefaultSectionSize(34)
            t.setEditTriggers(QAbstractItemView.AllEditTriggers)
            t.setSelectionMode(QAbstractItemView.ExtendedSelection)
            t.setShowGrid(False)
            self.grids[key] = t
            self.usage_tabs.addTab(t, "")
        lay.addWidget(self.usage_tabs, 1)
        self._year_changed()
        return w

    def _year_changed(self, *_):
        y = self.year.value()
        self.usage_tabs.setTabText(0, f"Baz yıl {y}")
        self.usage_tabs.setTabText(1, f"Önceki yıl {y - 1} (isteğe bağlı)")

    # ---- sekme 3
    def _equipment_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 18, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(muted("Saha etüdünden HVAC, aydınlatma ve bina kabuğu ekipmanlarını ekleyin. "
                            "Durum: 1 çok kötü, 5 çok iyi. Ekipman girilmezse bina skoru ekipmanı nötr sayar."))
        self.eq = QTableWidget(0, 5)
        self.eq.setHorizontalHeaderLabels(["KATEGORİ", "EKİPMAN", "KURULUM YILI", "DURUM (1-5)", "NOT"])
        self.eq.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.eq.verticalHeader().setVisible(False)
        self.eq.verticalHeader().setDefaultSectionSize(42)
        self.eq.setShowGrid(False)
        lay.addWidget(self.eq, 1)
        row = QHBoxLayout()
        add = QPushButton("+ Ekipman ekle")
        add.setObjectName("secondary")
        add.clicked.connect(self.add_equipment_row)
        rm = QPushButton("Seçiliyi sil")
        rm.setObjectName("secondary")
        rm.clicked.connect(self.remove_equipment_row)
        row.addWidget(add)
        row.addWidget(rm)
        row.addStretch()
        lay.addLayout(row)
        return w

    def add_equipment_row(self, data: dict | None = None):
        r = self.eq.rowCount()
        self.eq.insertRow(r)
        cat = QComboBox()
        cat.addItems(EQUIPMENT_CATEGORIES)
        yr = QSpinBox()
        yr.setRange(1900, date.today().year)
        yr.setValue(2010)
        cond = QSpinBox()
        cond.setRange(1, 5)
        cond.setValue(3)
        self.eq.setCellWidget(r, 0, cat)
        self.eq.setItem(r, 1, QTableWidgetItem(""))
        self.eq.setCellWidget(r, 2, yr)
        self.eq.setCellWidget(r, 3, cond)
        self.eq.setItem(r, 4, QTableWidgetItem(""))
        self.eq.editItem(self.eq.item(r, 1))

    def remove_equipment_row(self):
        r = self.eq.currentRow()
        if r >= 0:
            self.eq.removeRow(r)

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
            eq.append(dict(category=self.eq.cellWidget(r, 0).currentText(),
                           name=self.eq.item(r, 1).text() if self.eq.item(r, 1) else "",
                           year_installed=self.eq.cellWidget(r, 2).value(),
                           condition=self.eq.cellWidget(r, 3).value(),
                           notes=self.eq.item(r, 4).text() if self.eq.item(r, 4) else ""))
        return build_from_inputs(info, grids, eq, y)

    def save(self):
        try:
            self.result_data = self.collect()
        except ValidationError as e:
            shown = e.errors[:6]
            more = f" (+{len(e.errors) - 6} hata daha)" if len(e.errors) > 6 else ""
            self.error.setText("• " + "\n• ".join(shown) + more)
            return
        self.accept()
