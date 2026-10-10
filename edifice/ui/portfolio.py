from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..db import Store
from ..engine.rating import CLASS_COLORS
from ..service import Project
from .pages import _page
from .widgets import AMBER, G, INDIGO, MUTED, SUB, Card, Panel, badge, fmt, grade_for, header, score_color


def summarize(project: Project) -> dict:
    """Bir binanın portföy satırı için gerçek hesap çıktıları."""
    k, h = project.kpis(), project.health()
    codes = project.applicable_codes()
    fin = project.finance(codes) if codes else None
    sc = project.scenario(codes) if codes else None
    return {"project": project, "kpis": k, "health": h.total, "grade": h.grade, "rating": project.rating()["class"],
            "saving": sc.annual_saving if sc else 0.0, "capex": sc.capex if sc else 0.0,
            "npv": fin.npv if fin else 0.0, "payback": sc.payback_years if sc else float("inf")}


class PortfolioPage:
    """Tüm kayıtlı binaların toplam görünümü; kart tıklanınca bina açılır."""

    def __init__(self, store: Store, on_open, query: str = ""):
        self.widget, lay = _page()
        self.rows = []
        for bid, name in store.list_buildings():
            if query and query.lower() not in name.lower():
                continue
            self.rows.append((bid, summarize(store.load_project(bid))))
        n = len(self.rows)
        lay.addWidget(header("Portföy", "Binalarım",
                             f"{n} bina" + (f" · arama: “{query}”" if query else "") +
                             " · Her kart seçili binanın gerçek verisinden hesaplanır."))
        if not self.rows:
            empty = QLabel("Eşleşen bina yok.")
            empty.setStyleSheet(f"color: {SUB}; font-size: 14px; background: transparent;")
            lay.addWidget(empty)
            lay.addStretch()
            return

        area = sum(r["project"].building.floor_area_m2 for _, r in self.rows)
        energy = sum(r["kpis"].total_energy_kwh for _, r in self.rows) / 1000
        carbon = sum(r["kpis"].carbon_kg for _, r in self.rows) / 1000
        cost = sum(r["kpis"].total_cost for _, r in self.rows) / 1e6
        saving = sum(r["saving"] for _, r in self.rows) / 1e6
        capex = sum(r["capex"] for _, r in self.rows) / 1e6
        avg_health = sum(r["health"] for _, r in self.rows) / n
        specs = [
            ("Toplam alan", area / 1000, lambda v: f"{fmt(v, 1)} bin m²", f"{n} bina", G),
            ("Toplam enerji", energy, lambda v: f"{fmt(v)} MWh", "yıllık", AMBER),
            ("Toplam karbon", carbon, lambda v: f"{fmt(v, 1)} tCO₂", "yıllık", G),
            ("Enerji maliyeti", cost, lambda v: f"{fmt(v, 2)} M ₺", "yıllık", AMBER),
            ("Ortalama sağlık", avg_health, lambda v: f"{fmt(v)}/100", f"not {grade_for(avg_health)}", INDIGO),
            ("Tasarruf potansiyeli", saving, lambda v: f"{fmt(v, 2)} M ₺/yıl", f"CAPEX {fmt(capex, 2)} M ₺ (uygun öneriler)", G),
        ]
        grid = QGridLayout()
        grid.setSpacing(16)
        for i, (t, v, f, sub, acc) in enumerate(specs):
            c = Card(t, sub=sub, accent=acc)
            c.set_number(v, f, sub)
            grid.addWidget(c, i // 3, i % 3)
        lay.addLayout(grid)

        cards = Panel(eyebrow="Bina listesi", title="Portföydeki binalar",
                      subtitle="Sağlık skoru, enerji sınıfı (tahmini) ve uygun önerilerin tasarruf potansiyeli. Bir binaya tıklayın.")
        for bid, r in sorted(self.rows, key=lambda x: x[1]["health"]):
            cards.lay.addWidget(self._row(bid, r, on_open))
        lay.addWidget(cards)
        lay.addStretch()

    @staticmethod
    def _row(bid: int, r: dict, on_open) -> QPushButton:
        b = r["project"].building
        btn = QPushButton()
        btn.setObjectName("bldgrow")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(76)
        btn.setStyleSheet("QPushButton#bldgrow { background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06);"
                          "border-radius: 14px; text-align: left; } QPushButton#bldgrow:hover { background: rgba(13,221,150,0.06);"
                          "border: 1px solid rgba(13,221,150,0.25); }")
        h = QHBoxLayout(btn)
        h.setContentsMargins(18, 0, 18, 0)
        h.setSpacing(18)
        score = QLabel(f"{r['health']:.0f}")
        score.setFixedSize(46, 46)
        score.setAlignment(Qt.AlignCenter)
        col = score_color(r["health"])
        score.setStyleSheet(f"color: {col}; border: 2px solid {col}; border-radius: 23px; font-size: 15px; font-weight: 800; background: transparent;")
        txt = QVBoxLayout()
        txt.setSpacing(2)
        name = QLabel(b.name)
        name.setStyleSheet("font-size: 14px; font-weight: 700; background: transparent;")
        meta = QLabel(f"{b.use_type} · {fmt(b.floor_area_m2)} m² · {b.year_built} · EUI {fmt(r['kpis'].eui_kwh_m2, 0)} kWh/m²")
        meta.setStyleSheet(f"color: {SUB}; font-size: 12px; background: transparent;")
        txt.addWidget(name)
        txt.addWidget(meta)
        h.addWidget(score)
        h.addLayout(txt, 1)
        cls = r["rating"]
        bd = badge(f"Sınıf {cls}", CLASS_COLORS[cls])
        bd.setFixedHeight(24)
        h.addWidget(bd, 0, Qt.AlignVCenter)
        sv = QLabel(f"{fmt(r['saving'] / 1000)} bin ₺/yıl")
        sv.setMinimumWidth(110)
        sv.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        sv.setStyleSheet(f"color: {G}; font-family: 'DM Mono','SF Mono',Menlo; font-size: 13px; background: transparent;")
        h.addWidget(sv)
        for w in btn.findChildren(QWidget):
            w.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        btn.clicked.connect(lambda _=False, i=bid: on_open(i))
        return btn
