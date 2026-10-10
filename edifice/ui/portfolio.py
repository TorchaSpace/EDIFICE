from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..db import Store
from ..engine.rating import CLASS_COLORS
from ..models import UtilityType
from ..service import Project
from .pages import MONTHS, _page
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

        pts = [(bid, r["project"].building.name, r["project"].building.lat, r["project"].building.lon, r["health"])
               for bid, r in self.rows if r["project"].building.lat is not None]
        if pts:
            mp = Panel(eyebrow="Konum", title="Bina konumları",
                       subtitle="Girilen enlem/boylama göre; nokta rengi sağlık skoru. Harita altlığı yoktur, ızgara koordinat içindir.")
            mp.lay.addWidget(LocationMap(pts, on_open), 1)
            lay.addWidget(mp)
        else:
            hint = QLabel("Haritada görmek için bina düzenleme ekranında enlem ve boylam girin.")
            hint.setStyleSheet(f"color: {MUTED}; font-size: 12px; background: transparent;")
            lay.addWidget(hint)

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


def insights(project: Project) -> list[tuple[str, str, str]]:
    """Seçili bina için kural tabanlı bulgular: (renk, başlık, açıklama). Yalnız gerçek hesaptan türetilir."""
    out = []
    h, k = project.health(), project.kpis()
    name, (pts, w) = min(h.components.items(), key=lambda kv: kv[1][0])
    out.append((RED if pts < 40 else AMBER, f"En zayıf bileşen: {name}",
                f"Sağlık skorunun {name.lower()} bileşeni {pts:.0f}/100 (ağırlık %{w * 100:.0f}); toplam skor {h.total:.0f}/100, not {h.grade}."))
    for key, label in (("energy", "Enerji tüketimi"), ("cost", "Enerji maliyeti"), ("carbon", "Karbon salımı")):
        v = project.yoy().get(key)
        if v is not None and abs(v) >= 3:
            out.append((RED if v > 0 else G, f"{label} geçen yıla göre %{abs(v):.0f} {'arttı' if v > 0 else 'azaldı'}",
                        f"{project.year} ile {project.year - 1} karşılaştırması."))
    total = [a + b for a, b in zip(project.monthly(project.year, UtilityType.ELECTRICITY), project.monthly(project.year, UtilityType.GAS))]
    avg = sum(total) / 12 if total else 0
    if avg:
        i = max(range(12), key=lambda j: total[j])
        if total[i] > 1.4 * avg:
            out.append((AMBER, f"{MONTHS[i]} ayında tüketim ortalamanın %{(total[i] / avg - 1) * 100:.0f} üstünde",
                        "Mevsimsel pik olabilir; ısıtma/soğutma çizelgesini kontrol edin."))
    r = project.rating()
    out.append((G if r["class"] in "ABC" else AMBER, f"Tahmini enerji sınıfı {r['class']}",
                f"EUI {r['eui']:.0f} kWh/m²·yıl, kıyas {r['benchmark']:.0f}. Resmî EKB değildir."))
    best = [x for x in project.opportunity_results() if x.fit != "none"]
    if best:
        b = min(best, key=lambda x: x.payback_years)
        out.append((G, f"En hızlı geri dönen fırsat: {b.opportunity.name}",
                    f"CAPEX {fmt(b.capex / 1e6, 2)} M ₺, yıllık tasarruf {fmt(b.annual_saving / 1000)} bin ₺, geri ödeme {fmt_years(b.payback_years)}."))
    return out


class AssistantPage:
    """Seçili bina için otomatik bulgular. Bir dil modeli değil; kurallar gerçek hesap çıktısını okur."""

    def __init__(self, project: Project):
        self.widget, lay = _page()
        lay.addWidget(header("Asistan", "Otomatik bulgular",
                             f"{project.building.name} için hesap motorunun çıkardığı öne çıkan noktalar. "
                             "Kural tabanlıdır; yalnız bu binanın verisini okur."))
        p = Panel(eyebrow="EDIFI'CE analiz", title="Öne çıkanlar")
        for color, title, text in insights(project):
            p.lay.addWidget(_insight_card(color, title, text))
        lay.addWidget(p)
        lay.addStretch()


def _insight_card(color: str, title: str, text: str) -> QWidget:
    c = QColor(color)
    w = QWidget()
    w.setObjectName("ins")
    w.setStyleSheet(f"QWidget#ins {{ background: rgba({c.red()},{c.green()},{c.blue()},0.05);"
                    f"border: 1px solid rgba({c.red()},{c.green()},{c.blue()},0.16); border-radius: 12px; }}")
    v = QVBoxLayout(w)
    v.setContentsMargins(16, 12, 16, 12)
    v.setSpacing(3)
    t = QLabel(title)
    t.setStyleSheet("font-size: 14px; font-weight: 700; background: transparent;")
    d = QLabel(text)
    d.setWordWrap(True)
    d.setStyleSheet(f"color: {SUB}; font-size: 13px; background: transparent;")
    v.addWidget(t)
    v.addWidget(d)
    return w


class LocationMap(QWidget):
    """Bina konumları: enlem/boylam ızgarası üzerinde nokta grafiği (harita altlığı yok, koordinatlar gerçek).
    Nokta rengi sağlık skoruna göre; üzerine gelince bina adı görünür."""

    def __init__(self, points: list[tuple[int, str, float, float, float]], on_open):
        super().__init__()
        self.points, self.on_open = points, on_open
        self.setMinimumHeight(300)
        self.setMouseTracking(True)
        lats = [p[2] for p in points]
        lons = [p[3] for p in points]
        cl, co = (min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2
        self.span = max(max(lats) - min(lats), max(lons) - min(lons), 4.0) * 1.35
        self.c = (cl, co)
        self._hover = -1

    def _xy(self, lat: float, lon: float) -> QPointF:
        w, h = self.width(), self.height()
        s = min(w, h * 2) / self.span          # px / derece (iki eksen aynı ölçek)
        return QPointF(w / 2 + (lon - self.c[1]) * s, h / 2 - (lat - self.c[0]) * s * 1.0)

    def paintEvent(self, e):
        from PySide6.QtGui import QPainter, QPen
        from .widgets import rgba, qfont
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        step = 1 if self.span < 12 else 2 if self.span < 24 else 5
        p.setPen(QPen(rgba("#FFFFFF", 0.06), 1))
        p.setFont(qfont(10))
        w, h = self.width(), self.height()
        import math
        s = min(w, h * 2) / self.span
        lon0, lon1 = self.c[1] - w / 2 / s, self.c[1] + w / 2 / s
        lat0, lat1 = self.c[0] - h / 2 / s, self.c[0] + h / 2 / s
        for lon in range(math.ceil(lon0 / step) * step, int(lon1) + 1, step):
            x = self._xy(self.c[0], lon).x()
            p.drawLine(QPointF(x, 0), QPointF(x, h))
            p.setPen(QPen(rgba("#7A90A8", 0.7)))
            p.drawText(QPointF(x + 4, h - 6), f"{lon}°E")
            p.setPen(QPen(rgba("#FFFFFF", 0.06), 1))
        for lat in range(math.ceil(lat0 / step) * step, int(lat1) + 1, step):
            y = self._xy(lat, self.c[1]).y()
            p.drawLine(QPointF(0, y), QPointF(w, y))
            p.setPen(QPen(rgba("#7A90A8", 0.7)))
            p.drawText(QPointF(6, y - 4), f"{lat}°N")
            p.setPen(QPen(rgba("#FFFFFF", 0.06), 1))
        for i, (_, name, lat, lon, health) in enumerate(self.points):
            pt = self._xy(lat, lon)
            col = score_color(health)
            r = 9 if i == self._hover else 7
            p.setPen(Qt.NoPen)
            p.setBrush(rgba(col, 0.22))
            p.drawEllipse(pt, r + 7, r + 7)
            p.setBrush(QColor(col))
            p.drawEllipse(pt, r, r)
            if i == self._hover:
                p.setPen(QColor("#E8F2FF"))
                p.setFont(qfont(12, 700))
                p.drawText(pt + QPointF(r + 10, 4), name)
        p.end()

    def _hit(self, pos) -> int:
        for i, (_, _, lat, lon, _) in enumerate(self.points):
            q = self._xy(lat, lon)
            if (q.x() - pos.x()) ** 2 + (q.y() - pos.y()) ** 2 <= 18 ** 2:
                return i
        return -1

    def mouseMoveEvent(self, e):
        i = self._hit(e.position())
        if i != self._hover:
            self._hover = i
            self.setCursor(Qt.PointingHandCursor if i >= 0 else Qt.ArrowCursor)
            self.update()

    def mousePressEvent(self, e):
        i = self._hit(e.position())
        if i >= 0:
            self.on_open(self.points[i][0])
