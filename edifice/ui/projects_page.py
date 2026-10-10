from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QSpinBox, QWidget

from ..db import Store
from ..service import Project
from .dropdown import PremiumCombo
from .pages import _page
from .widgets import AMBER, G, INDIGO, MUTED, SUB, TEXT, Card, Panel, fmt, header, qfont, rgba

STATUSES = ["Planlanmadı", "Planlandı", "Uygulanıyor", "Tamamlandı"]
STATUS_COLORS = {"Planlandı": INDIGO, "Uygulanıyor": AMBER, "Tamamlandı": G, "Planlanmadı": MUTED}


class TimelineChart(QWidget):
    """Proje zaman çizelgesi: her öneri bir satır, uygulanma yılı sütununda durum rengiyle işaretlenir."""

    def __init__(self, rows: list[tuple[str, str, int]] | None = None):
        super().__init__()
        self.rows = rows or []
        self.setMinimumHeight(60)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._sync_height()

    def set_rows(self, rows: list[tuple[str, str, int]]):
        self.rows = rows
        self._sync_height()
        self.update()

    def _sync_height(self):
        self.setFixedHeight(max(60, 46 + 34 * len(self.rows)))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        if not self.rows:
            p.setPen(QColor(SUB))
            p.setFont(qfont(13))
            p.drawText(QRectF(0, 0, w, 60), Qt.AlignVCenter | Qt.AlignLeft,
                       "Henüz planlanmış proje yok. Projeler > Proje takibi sekmesinden bir öneriyi “Planlandı” yapın.")
            return
        y0 = min(r[2] for r in self.rows)
        y1 = max(max(r[2] for r in self.rows), y0 + 3)
        years = list(range(y0, y1 + 1))
        label_w = 230
        col = (w - label_w - 10) / len(years)
        p.setFont(qfont(11, 600, mono=True))
        for i, y in enumerate(years):
            x = label_w + i * col
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(x, 0, col, 24), Qt.AlignCenter, str(y))
            p.setPen(QPen(rgba("#FFFFFF", 0.05), 1))
            p.drawLine(QPointF(x, 28), QPointF(x, self.height()))
        for k, (name, status, year) in enumerate(self.rows):
            y = 36 + k * 34
            p.setPen(QColor(TEXT))
            p.setFont(qfont(12, 600))
            fm = p.fontMetrics()
            p.drawText(QRectF(0, y, label_w - 12, 26), Qt.AlignVCenter | Qt.AlignLeft,
                       fm.elidedText(name, Qt.ElideRight, label_w - 16))
            c = STATUS_COLORS.get(status, MUTED)
            x = label_w + (year - y0) * col + 6
            box = QRectF(x, y + 2, col - 12, 22)
            p.setPen(QPen(rgba(c, 0.55), 1))
            p.setBrush(rgba(c, 0.20))
            p.drawRoundedRect(box, 11, 11)
            p.setPen(QColor(c))
            p.setFont(qfont(10, 700))
            p.drawText(box, Qt.AlignCenter, status)


class ProjectsTrackerPage:
    """Proje takibi: her uygun öneri için durum ve uygulama yılı; veritabanına kaydedilir."""

    def __init__(self, project: Project, store: Store, on_change):
        self.project, self.store, self.on_change = project, store, on_change
        self.widget, lay = _page()
        lay.addWidget(header("Proje takibi", "Dönüşüm projeleri",
                             "Önerileri projeye çevirin: durum ve planlanan yılı seçin. Seçimler kaydedilir; Genel Bakış'taki zaman çizelgesini besler."))
        self.saved = store.load_projects(project.building_id) if project.building_id is not None else {}
        results = [r for r in project.opportunity_results() if r.fit != "none"]
        self.results = {r.opportunity.code: r for r in results}
        self.cards = QGridLayout()
        self.cards.setSpacing(16)
        self.c_plan = Card("Planlanan CAPEX", accent=INDIGO)
        self.c_done = Card("Uygulanan / biten CAPEX", accent=AMBER)
        self.c_save = Card("Biten projelerin tasarrufu", accent=G)
        for i, c in enumerate((self.c_plan, self.c_done, self.c_save)):
            self.cards.addWidget(c, 0, i)
        lay.addLayout(self.cards)

        panel = Panel(eyebrow="Projeler", title="Uygun öneriler", subtitle="Ekipmanına göre elenmiş öneriler; “uygun değil” olanlar listelenmez.")
        self.combos, self.spins = {}, {}
        for r in results:
            code = r.opportunity.code
            status, year = self.saved.get(code, (STATUSES[0], project.year + 1))
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 6, 0, 6)
            h.setSpacing(14)
            name = QLabel(r.opportunity.name)
            name.setStyleSheet("font-size: 13px; font-weight: 700; background: transparent;")
            meta = QLabel(f"CAPEX {fmt(r.capex / 1e6, 2)} M ₺ · tasarruf {fmt(r.annual_saving / 1000)} bin ₺/yıl")
            meta.setStyleSheet(f"color: {SUB}; font-size: 12px; background: transparent;")
            h.addWidget(name, 2)
            h.addWidget(meta, 3)
            cb = PremiumCombo()
            cb.addItems(STATUSES)
            cb.setCurrentText(status)
            cb.setFixedWidth(150)
            cb.setMinimumHeight(34)
            sp = QSpinBox()
            sp.setRange(project.year, project.year + 30)
            sp.setValue(max(year, project.year))
            sp.setFixedWidth(90)
            sp.setMinimumHeight(34)
            cb.currentTextChanged.connect(lambda _t, c=code: self._changed(c))
            sp.valueChanged.connect(lambda _v, c=code: self._changed(c))
            self.combos[code], self.spins[code] = cb, sp
            h.addWidget(cb)
            h.addWidget(sp)
            panel.lay.addWidget(row)
        lay.addWidget(panel)
        lay.addStretch()
        self._summary()

    def state(self) -> dict[str, tuple[str, int]]:
        return {c: (cb.currentText(), self.spins[c].value()) for c, cb in self.combos.items()}

    def rows(self) -> list[tuple[str, str, int]]:
        out = [(self.results[c].opportunity.name, s, y) for c, (s, y) in self.state().items() if s != STATUSES[0]]
        return sorted(out, key=lambda r: (r[2], r[0]))

    def _changed(self, code: str):
        s, y = self.state()[code]
        if self.project.building_id is not None:
            self.store.save_project(self.project.building_id, code, s, y)
        self._summary()
        self.on_change(self.rows())

    def _summary(self):
        st = self.state()
        plan = sum(self.results[c].capex for c, (s, _) in st.items() if s != STATUSES[0])
        done = sum(self.results[c].capex for c, (s, _) in st.items() if s in ("Uygulanıyor", "Tamamlandı"))
        save = sum(self.results[c].annual_saving for c, (s, _) in st.items() if s == "Tamamlandı")
        self.c_plan.set_number(plan / 1e6, lambda v: f"{fmt(v, 2)} M ₺", "Planlandı + Uygulanıyor + Tamamlandı", live=True)
        self.c_done.set_number(done / 1e6, lambda v: f"{fmt(v, 2)} M ₺", "Uygulanıyor + Tamamlandı", live=True)
        self.c_save.set_number(save / 1e6, lambda v: f"{fmt(v, 2)} M ₺/yıl", "yalnız Tamamlandı", live=True)
