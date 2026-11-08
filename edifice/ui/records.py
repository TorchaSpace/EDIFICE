from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDoubleSpinBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from .dropdown import PremiumCombo
from .widgets import RED, SUB, Panel, muted


class RecordsPanel(Panel):
    """Küçük kayıt tablosu: ekleme formu + liste + sil. `fields`: (anahtar, etiket, tür, seçenekler); tür text | num | combo.
    Kayıtlar `Store.add_record/list_records/delete_record` ile saklanır (tablo adı beyaz listeden)."""

    def __init__(self, store, table: str, fields: list[tuple], title: str, eyebrow: str = "", subtitle: str = "",
                 building_id: int | None = None, on_change=None, line=None):
        super().__init__(eyebrow=eyebrow, title=title, subtitle=subtitle)
        self.store, self.table, self.fields, self.bid, self.on_change = store, table, fields, building_id, on_change
        self.line = line or (lambda r: " · ".join(str(r.get(k)) for k, *_ in fields if r.get(k) not in (None, "")))
        self.inputs: dict = {}
        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
        for i, (key, label, kind, *opts) in enumerate(fields):
            if kind == "combo":
                w = PremiumCombo()
                w.addItems(opts[0])
                w.setMinimumHeight(34)
            elif kind == "num":
                w = QDoubleSpinBox()
                w.setRange(0, 1e12)
                w.setDecimals(opts[0] if opts else 2)
                w.setMinimumHeight(34)
            else:
                w = QLineEdit()
                w.setMinimumHeight(34)
                w.setPlaceholderText(label)
            self.inputs[key] = w
            form.addWidget(muted(label), (i // 3) * 2, i % 3)
            form.addWidget(w, (i // 3) * 2 + 1, i % 3)
        self.lay.addLayout(form)
        add = QPushButton("+ Ekle")
        add.setObjectName("primary")
        add.setCursor(Qt.PointingHandCursor)
        add.setFixedWidth(120)
        add.clicked.connect(self.add)
        self.lay.addWidget(add)
        self.list_box = QVBoxLayout()
        self.list_box.setSpacing(4)
        self.lay.addLayout(self.list_box)
        self.reload()

    def values(self) -> dict:
        out = {}
        for key, label, kind, *opts in self.fields:
            w = self.inputs[key]
            out[key] = w.currentText() if kind == "combo" else w.value() if kind == "num" else w.text().strip()
        return out

    def add(self):
        v = self.values()
        first = self.fields[0][0]
        if not str(v.get(first) or "").strip():
            return                                   # ilk alan zorunlu
        if self.bid is not None:
            v["building_id"] = self.bid
        self.store.add_record(self.table, v)
        for key, label, kind, *opts in self.fields:
            if kind == "text":
                self.inputs[key].clear()
        self.reload()
        if self.on_change:
            self.on_change()

    def records(self) -> list[dict]:
        return self.store.list_records(self.table, self.bid)

    def reload(self):
        while self.list_box.count():
            it = self.list_box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        rows = self.records()
        if not rows:
            self.list_box.addWidget(muted("Henüz kayıt yok."))
        for r in rows:
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 2, 0, 2)
            lbl = QLabel(self.line(r))
            lbl.setStyleSheet(f"color: {SUB}; font-size: 13px; background: transparent;")
            lbl.setWordWrap(True)
            rm = QPushButton("Sil")
            rm.setObjectName("export")
            rm.setFixedWidth(60)
            rm.setStyleSheet(f"color: {RED};")
            rm.clicked.connect(lambda _=False, i=r["id"]: self.remove(i))
            h.addWidget(lbl, 1)
            h.addWidget(rm)
            self.list_box.addWidget(row)

    def remove(self, rid: int):
        self.store.delete_record(self.table, rid)
        self.reload()
        if self.on_change:
            self.on_change()
