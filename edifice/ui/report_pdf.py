"""Markalı tek sayfalık PDF rapor (A4). QPdfWriter ile doğrudan çizilir, ek bağımlılık yok."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPageSize, QPainter, QPainterPath,
                           QPdfWriter, QPen)

from ..engine.relevance import LABELS as FIT_LABELS
from ..service import Project
from .widgets import MONO, SANS, fmt, fmt_years, grade_for

INK, MUTED, LINE, SOFT = "#0E2A24", "#5B6B66", "#E3EAE7", "#F4F7F6"
GREEN, AMBER, RED, INDIGO = "#08A878", "#D98A06", "#D8354F", "#5B5BD6"
GRADE = {"A": "#08A878", "B": "#4DBF8F", "C": "#D98A06", "D": "#E0721D", "E": "#D8354F"}
FIT_COLOR = {"high": GREEN, "medium": "#4DBF8F", "low": AMBER, "none": RED, "unknown": MUTED}
PAGE_W, PAGE_H, MARGIN = 595.0, 842.0, 40.0


def _font(pt: float, weight=QFont.Normal, mono=False, spacing=0.0) -> QFont:
    f = QFont()
    f.setFamilies(MONO if mono else SANS)
    f.setPointSizeF(pt / 2)  # 144 dpi + 2x painter scale
    f.setWeight(QFont.Weight(int(weight)))
    if spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


class _Canvas:
    def __init__(self, p: QPainter):
        self.p = p

    def text(self, x, y, w, h, s, pt=9, color=INK, weight=QFont.Normal, align=Qt.AlignLeft, mono=False, spacing=0.0):
        self.p.setFont(_font(pt, weight, mono, spacing))
        self.p.setPen(QColor(color))
        self.p.drawText(QRectF(x, y, w, h), align | Qt.AlignVCenter, s)

    def rrect(self, x, y, w, h, r=8, fill=SOFT, border=LINE):
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, w, h), r, r)
        self.p.setBrush(QColor(fill))
        self.p.setPen(QPen(QColor(border), 0.8) if border else Qt.NoPen)
        self.p.drawPath(path)
        self.p.setBrush(Qt.NoBrush)


def build_pdf(project: Project, codes: list[str], path: str) -> str:
    b, k, h = project.building, project.kpis(), project.health()
    yoy, scen = project.yoy(), project.scenario(codes)
    results = project.opportunity_results()

    writer = QPdfWriter(path)
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    writer.setResolution(144)
    writer.setTitle(f"EDIFI'CE · {b.name}")
    writer.setCreator("EDIFI'CE")
    p = QPainter(writer)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    sc = writer.width() / PAGE_W
    p.scale(sc, sc)
    c = _Canvas(p)
    cw = PAGE_W - 2 * MARGIN

    # ---- üst bant
    p.fillRect(QRectF(0, 0, PAGE_W, 88), QColor("#070C12"))
    badge = QRectF(MARGIN, 24, 38, 38)
    path_b = QPainterPath()
    path_b.addRoundedRect(badge, 10, 10)
    g = QLinearGradient(badge.topLeft(), badge.bottomRight())
    g.setColorAt(0, QColor("#0DDD96"))
    g.setColorAt(1, QColor("#6366F1"))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#0DDD96"))  # düz renk: gradyan bazı PDF görüntüleyicilerde çizilmiyor
    p.drawPath(path_b)
    p.setBrush(Qt.NoBrush)
    c.text(badge.x(), badge.y(), badge.width(), badge.height(), "E", 16, "#050A0E", QFont.Black, Qt.AlignHCenter)
    c.text(MARGIN + 50, 22, 240, 24, "EDIFI'CE", 17, "#E8F2FF", QFont.ExtraBold)
    c.text(MARGIN + 50, 44, 280, 16, "ENERJİ VE DÖNÜŞÜM RAPORU", 7.5, "#0DDD96", QFont.Bold, spacing=1.4)
    now = datetime.now()
    c.text(PAGE_W - MARGIN - 200, 28, 200, 16, f"{now:%d.%m.%Y}", 9, "#8FA6BC", align=Qt.AlignRight, mono=True)
    c.text(PAGE_W - MARGIN - 200, 46, 200, 16, f"Baz yıl {project.year}", 9, "#8FA6BC", align=Qt.AlignRight, mono=True)

    # ---- bina
    y = 108
    c.text(MARGIN, y, cw - 120, 30, b.name, 20, INK, QFont.ExtraBold)
    sub = " · ".join(x for x in (b.address, b.use_type, f"{fmt(b.floor_area_m2)} m²", f"{b.floors} kat",
                                  f"{b.year_built} yapım", f"{b.occupants} kişi" if b.occupants else "") if x)
    c.text(MARGIN, y + 30, cw, 16, sub, 9, MUTED)
    gcol = GRADE[h.grade]
    c.rrect(PAGE_W - MARGIN - 112, y + 2, 112, 38, 10, fill="#FFFFFF", border=gcol)
    c.text(PAGE_W - MARGIN - 112, y + 4, 112, 20, f"{h.total:.0f} / 100", 13, gcol, QFont.Bold, Qt.AlignHCenter, mono=True)
    c.text(PAGE_W - MARGIN - 112, y + 22, 112, 14, f"Health Score · {h.grade}", 7.5, MUTED, align=Qt.AlignHCenter)

    # ---- KPI kartları
    y = 164
    gap = 12.0
    kw = (cw - 2 * gap) / 3
    cards = [
        ("TOPLAM ENERJİ", f"{fmt(k.total_energy_kwh / 1000)} MWh", f"EUI {fmt(k.eui_kwh_m2, 1)} kWh/m²", yoy.get("energy")),
        ("KARBON", f"{fmt(k.carbon_kg / 1000, 1)} tCO₂", f"{fmt(k.carbon_kg_m2, 1)} kgCO₂/m²", yoy.get("carbon")),
        ("YILLIK MALİYET", f"{fmt(k.total_cost / 1e6, 2)} M ₺", "enerji + su", yoy.get("cost")),
        ("ELEKTRİK", f"{fmt(k.electricity_kwh / 1000)} MWh", f"%{fmt(100 * k.electricity_kwh / k.total_energy_kwh)} pay", yoy.get("electricity")),
        ("DOĞALGAZ", f"{fmt(k.gas_kwh / 1000)} MWh", f"%{fmt(100 * k.gas_kwh / k.total_energy_kwh)} pay", yoy.get("gas")),
        ("SU", f"{fmt(k.water_m3)} m³", f"{fmt(k.water_m3_m2, 2)} m³/m²", yoy.get("water")),
    ]
    for i, (t, v, s, tr) in enumerate(cards):
        x0, y0 = MARGIN + (i % 3) * (kw + gap), y + (i // 3) * 66
        c.rrect(x0, y0, kw, 58, 10)
        c.text(x0 + 12, y0 + 8, kw - 24, 12, t, 6.8, MUTED, QFont.Bold, spacing=0.8)
        c.text(x0 + 12, y0 + 21, kw - 24, 20, v, 13.5, INK, QFont.DemiBold, mono=True)
        c.text(x0 + 12, y0 + 41, kw - 70, 12, s, 7.5, MUTED)
        if tr is not None:
            col = GREEN if tr <= 0 else RED
            c.text(x0 + kw - 62, y0 + 41, 52, 12, f"{'↓' if tr < 0 else '↑'} {fmt(abs(tr), 1)}%", 7.5, col, QFont.DemiBold,
                   Qt.AlignRight, mono=True)

    # ---- health score
    y = 310
    c.text(MARGIN, y, cw, 18, "Building Health Score", 12, INK, QFont.Bold)
    c.text(MARGIN, y + 17, cw, 14, "Dört bileşenin ağırlıklı ortalaması; ayarlardaki kıyas değerlerine göre hesaplanır.", 8, MUTED)
    cx, cy, r = MARGIN + 62, y + 92, 46
    rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
    p.setPen(QPen(QColor("#E8EEEB"), 9, Qt.SolidLine, Qt.RoundCap))
    p.drawArc(rect, 225 * 16, -270 * 16)
    p.setPen(QPen(QColor(gcol), 9, Qt.SolidLine, Qt.RoundCap))
    p.drawArc(rect, 225 * 16, int(-270 * 16 * h.total / 100))
    c.text(cx - 40, cy - 22, 80, 30, f"{h.total:.0f}", 24, INK, QFont.DemiBold, Qt.AlignHCenter, mono=True)
    c.text(cx - 40, cy + 6, 80, 12, "/ 100", 7.5, MUTED, align=Qt.AlignHCenter, mono=True)
    bx = MARGIN + 150
    for i, (name, (pts, wt)) in enumerate(h.components.items()):
        yy = y + 48 + i * 26
        col = GRADE[grade_for(pts)]
        c.text(bx, yy, 190, 14, name, 9, INK, QFont.DemiBold)
        c.text(bx + 150, yy, 60, 14, f"ağırlık %{wt * 100:.0f}", 7.5, MUTED)
        track = QRectF(bx, yy + 15, cw - 150 - 40, 5)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#E8EEEB"))
        p.drawRoundedRect(track, 2.5, 2.5)
        p.setBrush(QColor(col))
        p.drawRoundedRect(QRectF(track.x(), track.y(), max(5, track.width() * pts / 100), 5), 2.5, 2.5)
        c.text(PAGE_W - MARGIN - 34, yy + 8, 34, 14, f"{pts:.0f}", 10, col, QFont.DemiBold, Qt.AlignRight, mono=True)

    # ---- öneriler tablosu
    y = 470
    c.text(MARGIN, y, cw, 18, "Dönüşüm önerileri", 12, INK, QFont.Bold)
    c.text(MARGIN, y + 17, cw, 14, "Uygunluk ve geri ödeme süresine göre sıralı. Oranlar ve birim maliyetler ayarlardaki varsayımlardır.", 8, MUTED)
    cols = [("Öneri", 0, 172, Qt.AlignLeft), ("Uygunluk", 172, 92, Qt.AlignLeft), ("Tasarruf ₺/yıl", 264, 88, Qt.AlignRight),
            ("CAPEX ₺", 352, 88, Qt.AlignRight), ("Geri ödeme", 440, 75, Qt.AlignRight)]
    ty = y + 40
    c.rrect(MARGIN, ty, cw, 20, 6, fill=SOFT, border=None)
    for name, x0, w, al in cols:
        c.text(MARGIN + x0 + 8, ty, w - 16, 20, name.upper(), 6.8, MUTED, QFont.Bold, al, spacing=0.6)
    for i, r in enumerate(results[:7]):
        ry = ty + 24 + i * 22
        pb = r.payback_years
        pcol = GREEN if pb <= 5 else AMBER if pb <= 15 else RED
        if i:
            p.setPen(QPen(QColor(LINE), 0.6))
            p.drawLine(QPointF(MARGIN, ry), QPointF(PAGE_W - MARGIN, ry))
        vals = [r.opportunity.name, FIT_LABELS[r.fit], fmt(r.annual_saving), fmt(r.capex), fmt_years(pb)]
        for j, ((_, x0, w, al), v) in enumerate(zip(cols, vals)):
            col = FIT_COLOR[r.fit] if j == 1 else pcol if j == 4 else INK
            c.text(MARGIN + x0 + 8, ry + 1, w - 16, 20, v, 8.5, col, QFont.DemiBold if j in (0, 1, 4) else QFont.Normal,
                   al, mono=j in (2, 3, 4))

    # ---- senaryo
    y = 682
    c.text(MARGIN, y, cw, 18, "Seçili senaryo", 12, INK, QFont.Bold)
    names = ", ".join(o.name for o in scen.selected) or "Henüz öneri seçilmedi"
    c.text(MARGIN, y + 17, cw, 14, names, 8, MUTED)
    by = y + 40
    items = [("TOPLAM CAPEX", f"{fmt(scen.capex / 1e6, 2)} M ₺"), ("YILLIK TASARRUF", f"{fmt(scen.annual_saving / 1e6, 2)} M ₺"),
             ("GERİ ÖDEME", fmt_years(scen.payback_years)), ("KARBON AZALIMI", f"%{fmt(scen.carbon_reduction_pct * 100, 1)}")]
    sw = (cw - 3 * 10) / 4
    for i, (t, v) in enumerate(items):
        x0 = MARGIN + i * (sw + 10)
        c.rrect(x0, by, sw, 50, 10, fill="#EAF7F2" if i == 1 else SOFT, border=LINE)
        c.text(x0 + 10, by + 7, sw - 20, 11, t, 6.5, MUTED, QFont.Bold, spacing=0.6)
        c.text(x0 + 10, by + 21, sw - 20, 22, v, 13, GREEN if i == 1 else INK, QFont.DemiBold, mono=True)
    cur, tgt = scen.current, scen.target
    line = (f"EUI {fmt(cur.eui_kwh_m2, 1)} → {fmt(tgt.eui_kwh_m2, 1)} kWh/m²   ·   Karbon {fmt(cur.carbon_kg / 1000, 1)} → "
            f"{fmt(tgt.carbon_kg / 1000, 1)} tCO₂   ·   Yıllık maliyet {fmt(cur.total_cost / 1e6, 2)} → {fmt(tgt.total_cost / 1e6, 2)} M ₺")
    c.text(MARGIN, by + 58, cw, 16, line, 8.2, MUTED, mono=False)

    # ---- alt bilgi
    p.setPen(QPen(QColor(LINE), 0.8))
    p.drawLine(QPointF(MARGIN, 806), QPointF(PAGE_W - MARGIN, 806))
    c.text(MARGIN, 810, cw - 120, 20, "Bu rapor girilen verilere ve ayarlardaki varsayımlara dayanır; yatırım kararı öncesinde saha etüdüyle doğrulanmalıdır.",
           6.8, MUTED)
    c.text(PAGE_W - MARGIN - 110, 810, 110, 20, "EDIFI'CE · Green PropTech", 6.8, MUTED, QFont.DemiBold, Qt.AlignRight)
    p.end()
    return path
