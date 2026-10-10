from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..db import Store
from ..engine.rating import CLASS_COLORS
from ..service import Project
from .pages import _page
from .widgets import AMBER, G, INDIGO, MUTED, RED, SUB, Card, Panel, badge, fmt, fmt_years, grade_for, header, score_color


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


def _mono_label(text: str, color: str = SUB) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {color}; font-family: 'DM Mono','SF Mono',Menlo; font-size: 13px; background: transparent;")
    return lbl


class FinancePage:
    """Portföy finansı: uygun önerilerin bina bazında CAPEX, tasarruf, NPV, IRR ve geri ödemesi (gerçek hesap)."""

    def __init__(self, store: Store, on_open):
        from .pages import _set_row, _table, _fit_height
        self.widget, lay = _page()
        rows = [(bid, summarize(store.load_project(bid))) for bid, _ in store.list_buildings()]
        a = rows[0][1]["project"].assumptions if rows else None
        lay.addWidget(header("Finans", "Portföy finansı",
                             "Her binada uygun (ekipmana göre elenmiş) tüm önerilerin tipik tasarruf senaryosu. "
                             + (f"{a.horizon_years} yıl · reel · iskonto %{fmt(a.discount_rate * 100, 1)}." if a else "")))
        capex = sum(r["capex"] for _, r in rows)
        saving = sum(r["saving"] for _, r in rows)
        npv = sum(r["npv"] for _, r in rows)
        grid = QGridLayout()
        grid.setSpacing(16)
        specs = [("Toplam CAPEX", capex / 1e6, lambda v: f"{fmt(v, 2)} M ₺", "uygun öneriler", AMBER),
                 ("Yıllık tasarruf", saving / 1e6, lambda v: f"{fmt(v, 2)} M ₺", "her yıl", G),
                 ("Toplam NPV", npv / 1e6, lambda v: f"{fmt(v, 2)} M ₺", "bugünkü değerle", G if npv >= 0 else RED),
                 ("Basit geri ödeme", (capex / saving) if saving else 0, lambda v: f"{fmt(v, 1)} yıl" if v else "-", "CAPEX / yıllık tasarruf (fiyat artışı hariç)", INDIGO)]
        for i, (t, v, f, sub, acc) in enumerate(specs):
            c = Card(t, sub=sub, accent=acc)
            c.set_number(v, f, sub)
            grid.addWidget(c, 0, i)
        lay.addLayout(grid)
        p = Panel(eyebrow="Bina bazında", title="Yatırım getirisi", subtitle="NPV'ye göre sıralı. Satıra çift tıklayınca bina açılır.")
        t = _table(["Bina", "CAPEX (M ₺)", "Tasarruf (M ₺/yıl)", "NPV (M ₺)", "Geri ödeme"])
        order = sorted(rows, key=lambda x: -x[1]["npv"])
        t.setRowCount(len(order))
        for i, (bid, r) in enumerate(order):
            pb = r["payback"]
            _set_row(t, i, [r["project"].building.name, fmt(r["capex"] / 1e6, 2), fmt(r["saving"] / 1e6, 2),
                            fmt(r["npv"] / 1e6, 2), fmt_years(pb)], colors={3: G if r["npv"] >= 0 else RED}, mono_from=1)
        t.cellDoubleClicked.connect(lambda row, _c, o=order: on_open(o[row][0]))
        _fit_height(t, max(len(order), 1))
        p.lay.addWidget(t)
        lay.addWidget(p)
        lay.addStretch()


class EsgPage:
    """Sürdürülebilirlik: karbon, kişi/m² yoğunluğu, hedef paketle azalım ve mevzuat eşikleri (gerçek hesap)."""

    def __init__(self, store: Store, on_open):
        self.widget, lay = _page()
        rows = [(bid, summarize(store.load_project(bid))) for bid, _ in store.list_buildings()]
        lay.addWidget(header("Sürdürülebilirlik", "Karbon ve ESG göstergeleri",
                             "Emisyon faktörleri: elektrik 0,469 kgCO₂e/kWh (ETKB 2023), doğalgaz 0,202 (IPCC). Sınıflar tahminidir, resmî EKB değildir."))
        carbon = sum(r["kpis"].carbon_kg for _, r in rows) / 1000
        after = 0.0
        for _, r in rows:
            codes = r["project"].applicable_codes()
            sc = r["project"].scenario(codes) if codes else None
            after += (sc.target.carbon_kg if sc else r["kpis"].carbon_kg) / 1000
        area = sum(r["project"].building.floor_area_m2 for _, r in rows)
        ok_c = sum(1 for _, r in rows if r["rating"] in ("A", "B", "C"))
        grid = QGridLayout()
        grid.setSpacing(16)
        specs = [("Yıllık karbon", carbon, lambda v: f"{fmt(v, 1)} tCO₂", f"{fmt(carbon * 1000 / area, 1) if area else 0} kg/m²", G),
                 ("Önerilerle hedef", after, lambda v: f"{fmt(v, 1)} tCO₂", f"%{fmt(100 * (1 - after / carbon), 1) if carbon else 0} azalım", G),
                 ("Sınıf C ve üstü", ok_c, lambda v: f"{int(v)}/{len(rows)}", "yeni bina eşiği (BEP)", INDIGO if ok_c else AMBER)]
        for i, (t, v, f, sub, acc) in enumerate(specs):
            c = Card(t, sub=sub, accent=acc)
            c.set_number(v, f, sub)
            grid.addWidget(c, 0, i)
        lay.addLayout(grid)
        p = Panel(eyebrow="Bina bazında", title="Karbon sıralaması", subtitle="En yüksek karbon yoğunluğundan düşüğe. Binaya tıklayın.")
        for bid, r in sorted(rows, key=lambda x: -x[1]["kpis"].carbon_kg_m2):
            p.lay.addWidget(PortfolioPage._row(bid, r, on_open))
        lay.addWidget(p)
        lay.addStretch()
