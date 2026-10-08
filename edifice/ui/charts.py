"""Özel grafikler (Figma koyu teması): yumuşak alan grafiği ve yuvarlak uçlu çubuk grafik.
Animasyon: değerler taban çizgisinden yukarı doğru yükselir."""
from __future__ import annotations

import math

from PySide6.QtCore import Property, QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .widgets import AMBER, G, INDIGO, MUTED, RED, SUB, TEXT, fmt, qfont, rgba

COLORS = {"green": G, "indigo": INDIGO, "amber": AMBER, "red": RED, "slate": "#5B7089"}


def nice_step(raw: float) -> float:
    if raw <= 0:
        return 1.0
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


class _Chart(QWidget):
    def __init__(self, categories, groups, scale=1.0, decimals=0, colors=None, unit="", min_h=180, fixed_max=None):
        super().__init__()
        self.categories, self.groups = categories, groups
        self.scale, self.decimals, self.unit = scale, decimals, unit
        self.colors = colors or ["green", "indigo", "amber"]
        top = fixed_max if fixed_max else max((v for vals in groups.values() for v in vals), default=1) / scale
        self.step = nice_step(top / 4)
        self.ticks = int(top / self.step) + 1
        self.ymax = self.step * self.ticks
        self.setMinimumHeight(min_h)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self._hover: int | None = None
        self._progress = 0.0
        self._anim = QPropertyAnimation(self, b"progress", self)
        self._anim.setDuration(1600)

    def _get(self) -> float:
        return self._progress

    def _set(self, v: float):
        self._progress = v
        self.update()

    progress = Property(float, _get, _set)

    def replay(self):
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def showEvent(self, e):
        super().showEvent(e)
        self.replay()

    def color(self, gi: int) -> str:
        return COLORS[self.colors[gi % len(self.colors)]]

    def _plot(self) -> QRectF:
        top = 30 if len(self.groups) > 1 else 8
        return QRectF(48, top, self.width() - 58, self.height() - top - 32)

    def leaveEvent(self, e):
        self._hover = None
        self.update()

    @staticmethod
    def _ease(t: float) -> float:
        t = max(0.0, min(1.0, t))
        return 1 - (1 - t) ** 4

    def _grid(self, p: QPainter, plot: QRectF):
        p.setFont(qfont(11, mono=True))
        for i in range(self.ticks + 1):
            y = plot.bottom() - plot.height() * (i * self.step) / self.ymax
            pen = QPen(QColor(255, 255, 255, 12), 1, Qt.DashLine)
            pen.setDashPattern([4, 4])
            p.setPen(pen)
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(0, y - 9, plot.left() - 8, 18), Qt.AlignRight | Qt.AlignVCenter,
                       fmt(i * self.step, self.decimals))

    def _legend(self, p: QPainter, plot: QRectF):
        if len(self.groups) < 2:
            return
        x = plot.left()
        f = qfont(12, QFont_Medium)
        p.setFont(f)
        for gi, name in enumerate(self.groups):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(self.color(gi)))
            p.drawRoundedRect(QRectF(x, 8, 8, 8), 2.5, 2.5)
            p.setPen(QColor(SUB))
            w = QFontMetrics(f).horizontalAdvance(name)
            p.drawText(QRectF(x + 14, 2, w + 4, 20), Qt.AlignVCenter, name)
            x += 14 + w + 20

    def _tooltip(self, p: QPainter, plot: QRectF, cx: float):
        ci = self._hover
        head = self.categories[ci]
        rows = []
        for gi, (name, vals) in enumerate(self.groups.items()):
            d = max(self.decimals, 1 if self.scale > 1 else 0)
            rows.append((self.color(gi), name, f"{fmt(vals[ci] / self.scale, d)} {self.unit}".strip()))
        f_h, f_r = qfont(12, 700), qfont(12, mono=True)
        fm_h, fm_r = QFontMetrics(f_h), QFontMetrics(f_r)
        w = max([fm_h.horizontalAdvance(head)] + [fm_r.horizontalAdvance(f"{n}: {v}") + 16 for _, n, v in rows]) + 28
        h = 24 + 20 * len(rows) + 6
        x = max(4, min(self.width() - w - 4, cx - w / 2))
        y = plot.top() + 2
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, w, h), 10, 10)
        p.fillPath(path, QColor(5, 8, 14, 245))
        p.setPen(QPen(QColor(255, 255, 255, 18), 1))
        p.drawPath(path)
        p.setFont(f_h)
        p.setPen(QColor(SUB))
        p.drawText(QRectF(x + 14, y + 6, w - 20, 18), Qt.AlignVCenter, head)
        p.setFont(f_r)
        for i, (c, n, v) in enumerate(rows):
            yy = y + 26 + 20 * i
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(c))
            p.drawEllipse(QPointF(x + 18, yy + 10), 3, 3)
            p.setPen(QColor(c))
            p.drawText(QRectF(x + 28, yy, w - 30, 20), Qt.AlignVCenter, f"{n}: ")
            p.setPen(QColor(TEXT))
            off = fm_r.horizontalAdvance(f"{n}: ")
            p.drawText(QRectF(x + 28 + off, yy, w - 30 - off, 20), Qt.AlignVCenter, v)


QFont_Medium = 500


class AreaChart(_Chart):
    """Yumuşak eğrili alan grafiği: ilk seri dolgulu, diğerleri çizgi."""

    def _x(self, plot, i, n):
        return plot.left() + plot.width() * i / max(n - 1, 1)

    def mouseMoveEvent(self, e):
        plot, n = self._plot(), len(self.categories)
        idx = None
        if plot.left() - 10 <= e.position().x() <= plot.right() + 10 and n:
            idx = max(0, min(n - 1, round((e.position().x() - plot.left()) / plot.width() * (n - 1))))
        if idx != self._hover:
            self._hover = idx
            self.update()

    @staticmethod
    def _smooth(pts: list[QPointF]) -> QPainterPath:
        path = QPainterPath(pts[0])
        for i in range(len(pts) - 1):
            p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, len(pts) - 1)]
            c1 = QPointF(p1.x() + (p2.x() - p0.x()) / 6, p1.y() + (p2.y() - p0.y()) / 6)
            c2 = QPointF(p2.x() - (p3.x() - p1.x()) / 6, p2.y() - (p3.y() - p1.y()) / 6)
            path.cubicTo(c1, c2, p2)
        return path

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        plot, n = self._plot(), len(self.categories)
        self._grid(p, plot)
        if n < 2:
            return
        t = self._ease(self._progress)
        p.setFont(qfont(11))
        for i, c in enumerate(self.categories):
            p.setPen(QColor(TEXT if i == self._hover else MUTED))
            p.drawText(QRectF(self._x(plot, i, n) - 24, plot.bottom() + 8, 48, 16), Qt.AlignCenter, c)
        if self._hover is not None:
            x = self._x(plot, self._hover, n)
            p.setPen(QPen(QColor(255, 255, 255, 30), 1))
            p.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
        # çizim sırası: önce çizgiler (arka), sonra ilk seri (üstte)
        order = list(range(len(self.groups)))[::-1]
        series = list(self.groups.items())
        for gi in order:
            vals = series[gi][1]
            pts = [QPointF(self._x(plot, i, n), plot.bottom() - plot.height() * (v / self.scale) / self.ymax * t)
                   for i, v in enumerate(vals)]
            line = self._smooth(pts)
            col = QColor(self.color(gi))
            if gi == 0:
                fill = QPainterPath(line)
                fill.lineTo(pts[-1].x(), plot.bottom())
                fill.lineTo(pts[0].x(), plot.bottom())
                fill.closeSubpath()
                g = QLinearGradient(0, plot.top(), 0, plot.bottom())
                g.setColorAt(0, rgba(col.name(), 0.28))
                g.setColorAt(1, rgba(col.name(), 0.0))
                p.fillPath(fill, g)
            p.setPen(QPen(col, 2 if gi == 0 else 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            p.drawPath(line)
            if self._hover is not None:
                pt = pts[self._hover]
                p.setPen(QPen(QColor(BG_DOT), 2))
                p.setBrush(col)
                p.drawEllipse(pt, 4.5, 4.5)
        self._legend(p, plot)
        if self._hover is not None:
            self._tooltip(p, plot, self._x(plot, self._hover, n))


BG_DOT = "#0B1624"


class BarChart(_Chart):
    """Yuvarlak uçlu, gradyan çubuklar; aşağıdan yukarı yükselir."""

    def __init__(self, *a, **k):
        k.setdefault("colors", ["green", "amber", "indigo"])
        super().__init__(*a, **k)
        self._from = {n: list(v) for n, v in self.groups.items()}
        self._mix = 1.0
        self._morph = QPropertyAnimation(self, b"mix", self)
        self._morph.setDuration(650)
        self._morph.setEasingCurve(QEasingCurve.OutQuart)

    def _gm(self) -> float:
        return self._mix

    def _sm(self, v: float):
        self._mix = v
        self.update()

    mix = Property(float, _gm, _sm)

    def _shown(self, name: str, ci: int) -> float:
        a, b = self._from[name][ci], self.groups[name][ci]
        return a + (b - a) * self._ease(self._mix)

    def update_data(self, groups):
        """Değerleri mevcut çizimden yenisine yumuşakça geçirir (grafiği yeniden kurmadan)."""
        self._from = {n: [self._shown(n, i) for i in range(len(v))] for n, v in self.groups.items()}
        self.groups = groups
        self._morph.stop()
        self._morph.setStartValue(0.0)
        self._morph.setEndValue(1.0)
        self._morph.start()

    def mouseMoveEvent(self, e):
        plot, n = self._plot(), len(self.categories)
        idx = None
        if plot.left() <= e.position().x() <= plot.right() and n:
            idx = min(n - 1, int((e.position().x() - plot.left()) / (plot.width() / n)))
        if idx != self._hover:
            self._hover = idx
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        plot = self._plot()
        n, g = len(self.categories), len(self.groups)
        self._grid(p, plot)
        if not n:
            return
        slot = plot.width() / n
        if self._hover is not None:
            hp = QPainterPath()
            hp.addRoundedRect(QRectF(plot.left() + slot * self._hover + 2, plot.top() - 2, slot - 4, plot.height() + 4), 12, 12)
            p.fillPath(hp, QColor(255, 255, 255, 8))
        bw, gap = min(slot * 0.62 / g, 30), 4
        total_w, total = g * bw + (g - 1) * gap, n * g
        f = qfont(11)
        p.setFont(f)
        for ci in range(n):
            x0 = plot.left() + slot * ci + (slot - total_w) / 2
            for gi, (name, vals) in enumerate(self.groups.items()):
                idx = ci * g + gi
                tt = self._ease((self._progress - idx / max(total - 1, 1) * 0.22) / 0.78)
                h = plot.height() * (self._shown(name, ci) / self.scale) / self.ymax * tt
                if h < 0.5:
                    continue
                r = min(bw / 2, 8)
                col = QColor(self.color(gi))
                grad = QLinearGradient(0, plot.bottom() - h, 0, plot.bottom())
                grad.setColorAt(0, col)
                grad.setColorAt(1, rgba(col.name(), 0.38))
                path = QPainterPath()
                path.addRoundedRect(QRectF(x0 + gi * (bw + gap), plot.bottom() - h, bw, h + r), r, r)
                p.save()
                p.setClipRect(QRectF(0, 0, self.width(), plot.bottom()))
                p.fillPath(path, grad)
                p.restore()
            label = QFontMetrics(f).elidedText(self.categories[ci], Qt.ElideRight, int(slot - 6))
            p.setPen(QColor(TEXT if ci == self._hover else MUTED))
            p.drawText(QRectF(plot.left() + slot * ci, plot.bottom() + 8, slot, 16), Qt.AlignCenter, label)
        self._legend(p, plot)
        if self._hover is not None:
            self._tooltip(p, plot, plot.left() + slot * (self._hover + 0.5))


# ============================================================ yatırımcı paketi görselleri
from ..engine.rating import CLASS_COLORS, CLASSES, pdf_curve  # noqa: E402
from PySide6.QtGui import QPolygonF  # noqa: E402
from .widgets import SIDEBAR_BG  # noqa: E402


class _Progress(QWidget):
    """0 -> 1 animasyonlu ilerleme (showEvent'te yeniden oynar)."""

    def __init__(self, ms: int = 1200):
        super().__init__()
        self._p = 0.0
        self._anim = QPropertyAnimation(self, b"progress", self)
        self._anim.setDuration(ms)
        self._anim.setEasingCurve(QEasingCurve.OutQuart)

    def _get(self) -> float:
        return self._p

    def _set(self, v: float):
        self._p = v
        self.update()

    progress = Property(float, _get, _set)

    def replay(self):
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def showEvent(self, e):
        super().showEvent(e)
        self.replay()


class ClassScale(_Progress):
    """A-G enerji sınıfı skalası: 'şimdi' ve (varsa) 'dönüşüm sonrası' işaretçileri yerine kayar."""

    def __init__(self, current: str, after: str | None = None):
        super().__init__(1300)
        self.current, self.after = current, (after if after and after != current else None)
        self.setFixedHeight(168)

    def _chip(self, i: int):
        gap = 8
        cw = (self.width() - 8 - 6 * gap) / 7
        return QRectF(4 + i * (cw + gap), 50, cw, 58)

    def _pointer(self, p: QPainter, x: float, y: float, up: bool, color: QColor):
        poly = QPolygonF([QPointF(x - 7, y + (8 if up else 0)), QPointF(x + 7, y + (8 if up else 0)),
                          QPointF(x, y + (0 if up else 8))])
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawPolygon(poly)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        ci = CLASSES.index(self.current)
        ai = CLASSES.index(self.after) if self.after else None
        for i, letter in enumerate(CLASSES):
            r, col = self._chip(i), QColor(CLASS_COLORS[letter])
            path = QPainterPath()
            path.addRoundedRect(r, 14, 14)
            if i == ci:
                glow = QColor(col)
                glow.setAlpha(60)
                gp = QPainterPath()
                gp.addRoundedRect(r.adjusted(-5, -5, 5, 5), 18, 18)
                p.fillPath(gp, glow)
                p.fillPath(path, col)
                p.setPen(QColor("#04130D"))
            else:
                p.fillPath(path, rgba(col.name(), 0.14))
                if i == ai:
                    p.setPen(QPen(col, 2))
                    p.drawPath(path)
                p.setPen(rgba(col.name(), 0.85 if i == ai else 0.55))
            p.setFont(qfont(20, 800))
            p.drawText(r, Qt.AlignCenter, letter)
        t = self._p
        start_x = self._chip(0).center().x()
        # şimdi işaretçisi
        cur = self._chip(ci)
        x = start_x + (cur.center().x() - start_x) * t
        self._pointer(p, x, 36, False, QColor(CLASS_COLORS[self.current]))
        p.setPen(QColor(TEXT))
        p.setFont(qfont(11, 700, spacing=1.0))
        p.drawText(QRectF(x - 60, 10, 120, 18), Qt.AlignHCenter | Qt.AlignVCenter, "ŞİMDİ")
        if ai is not None:
            tgt = self._chip(ai)
            t2 = max(0.0, (t - 0.35) / 0.65)
            x2 = cur.center().x() + (tgt.center().x() - cur.center().x()) * t2
            c2 = QColor(CLASS_COLORS[self.after])
            c2.setAlphaF(min(1.0, t2 * 2))
            self._pointer(p, x2, 108, True, c2)
            p.setPen(c2)
            p.drawText(QRectF(x2 - 90, 120, 180, 18), Qt.AlignHCenter | Qt.AlignVCenter, "DÖNÜŞÜM SONRASI")


class PercentileBar(_Progress):
    """Benzer binaların dağılım eğrisi üzerinde binanın yeri."""

    def __init__(self, z: float, percentile: float):
        super().__init__(1400)
        self.z, self.percentile = z, percentile
        self.setFixedHeight(150)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width() - 8, self.height()
        base, top = H - 30, 26
        curve = pdf_curve()
        t = self._p

        def pt(z, d, k=1.0):
            return QPointF(4 + (z + 3) / 6 * W, base - (base - top) * d * k)
        col = QColor(RED if self.percentile >= 65 else AMBER if self.percentile >= 35 else G)
        mz = self.z * t                          # işaretçi medyandan yerine kayar
        pts = [pt(z, d, min(1.0, t * 1.4)) for z, d in curve]
        full = QPainterPath(pts[0])
        for q in pts[1:]:
            full.lineTo(q)
        area = QPainterPath(full)
        area.lineTo(pts[-1].x(), base)
        area.lineTo(pts[0].x(), base)
        area.closeSubpath()
        p.fillPath(area, QColor(255, 255, 255, 14))
        p.save()
        p.setClipRect(QRectF(0, 0, 4 + (mz + 3) / 6 * W, H))
        g = QLinearGradient(0, top, 0, base)
        g.setColorAt(0, rgba(col.name(), 0.55))
        g.setColorAt(1, rgba(col.name(), 0.08))
        p.fillPath(area, g)
        p.restore()
        p.setPen(QPen(QColor(255, 255, 255, 70), 1.6))
        p.drawPath(full)
        # medyan çizgisi
        mx = 4 + 3 / 6 * W
        pen = QPen(QColor(255, 255, 255, 60), 1, Qt.DashLine)
        p.setPen(pen)
        p.drawLine(QPointF(mx, top - 6), QPointF(mx, base))
        p.setFont(qfont(10))
        p.setPen(QColor(MUTED))
        p.drawText(QRectF(mx - 70, base + 6, 140, 16), Qt.AlignHCenter, "Kıyas değeri (medyan)")
        p.drawText(QRectF(4, base + 6, 120, 16), Qt.AlignLeft, "← daha az tüketen")
        p.drawText(QRectF(W - 116, base + 6, 120, 16), Qt.AlignRight, "daha çok tüketen →")
        # işaretçi
        x = 4 + (mz + 3) / 6 * W
        p.setPen(QPen(col, 2))
        p.drawLine(QPointF(x, top - 6), QPointF(x, base))
        p.setBrush(col)
        p.setPen(QPen(QColor("#0B1624"), 2))
        p.drawEllipse(QPointF(x, top - 6), 6, 6)
        label = QRectF(min(max(x - 22, 0), W - 44), 0, 44, 18)
        lp = QPainterPath()
        lp.addRoundedRect(label, 9, 9)
        p.fillPath(lp, col)
        p.setPen(QColor("#04130D"))
        p.setFont(qfont(10, 800))
        p.drawText(label, Qt.AlignCenter, "SİZ")


class CashFlowChart(QWidget):
    """Kümülatif nakit akışı (yıl 0..N): sıfırın altı kırmızı, üstü yeşil; geri ödeme noktası işaretli."""

    def __init__(self, years: list[int], cumulative: list[float], payback: float | None, min_h: int = 240):
        super().__init__()
        self.years = years
        self._from = [0.0] * len(cumulative)
        self.values = list(cumulative)
        self.payback = payback
        self.setMinimumHeight(min_h)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self._hover = None
        self._progress = 0.0
        self._anim = QPropertyAnimation(self, b"progress", self)
        self._anim.setDuration(1500)
        self._anim.setEasingCurve(QEasingCurve.OutQuart)
        self._mix = 1.0
        self._morph = QPropertyAnimation(self, b"mix", self)
        self._morph.setDuration(700)
        self._morph.setEasingCurve(QEasingCurve.OutQuart)

    def _gp(self) -> float:
        return self._progress

    def _sp(self, v: float):
        self._progress = v
        self.update()

    progress = Property(float, _gp, _sp)

    def _gm(self) -> float:
        return self._mix

    def _sm(self, v: float):
        self._mix = v
        self.update()

    mix = Property(float, _gm, _sm)

    def showEvent(self, e):
        super().showEvent(e)
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def update_data(self, cumulative: list[float], payback: float | None):
        self._from = self._shown()
        self.values, self.payback = list(cumulative), payback
        self._morph.stop()
        self._morph.setStartValue(0.0)
        self._morph.setEndValue(1.0)
        self._morph.start()

    def _shown(self) -> list[float]:
        return [a + (b - a) * self._mix for a, b in zip(self._from, self.values)]

    def _plot(self) -> QRectF:
        return QRectF(56, 16, self.width() - 70, self.height() - 16 - 32)

    def mouseMoveEvent(self, e):
        plot, n = self._plot(), len(self.years)
        idx = None
        if plot.left() - 8 <= e.position().x() <= plot.right() + 8:
            idx = max(0, min(n - 1, round((e.position().x() - plot.left()) / plot.width() * (n - 1))))
        if idx != self._hover:
            self._hover = idx
            self.update()

    def leaveEvent(self, e):
        self._hover = None
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        plot, n = self._plot(), len(self.years)
        vals_m = [v / 1e6 for v in self._shown()]
        allv = [v / 1e6 for v in self.values] + [v / 1e6 for v in self._from] + [0.0]
        lo, hi = min(allv), max(allv)
        step = nice_step((hi - lo) / 5 or 1)
        lo, hi = math.floor(lo / step) * step, math.ceil(hi / step) * step
        if hi == lo:
            hi = lo + step
        t = 1 - (1 - min(1.0, self._progress)) ** 4

        def y_of(v):
            return plot.bottom() - plot.height() * (v - lo) / (hi - lo)

        def x_of(i):
            return plot.left() + plot.width() * i / max(n - 1, 1)
        zero = y_of(0.0)
        p.setFont(qfont(11, mono=True))
        k = 0
        while lo + k * step <= hi + 1e-9:
            v = lo + k * step
            y = y_of(v)
            pen = QPen(QColor(255, 255, 255, 40 if abs(v) < 1e-9 else 12), 1, Qt.SolidLine if abs(v) < 1e-9 else Qt.DashLine)
            p.setPen(pen)
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(0, y - 9, plot.left() - 8, 18), Qt.AlignRight | Qt.AlignVCenter, fmt(v, 1))
            k += 1
        p.setFont(qfont(11))
        for i, yr in enumerate(self.years):
            if n <= 10 or yr % 2 == 0:
                p.setPen(QColor(TEXT if i == self._hover else MUTED))
                p.drawText(QRectF(x_of(i) - 20, plot.bottom() + 8, 40, 16), Qt.AlignCenter, str(yr))
        pts = [QPointF(x_of(i), zero + (y_of(v * t) - zero)) for i, v in enumerate(vals_m)]
        line = QPainterPath(pts[0])
        for i in range(len(pts) - 1):
            p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, len(pts) - 1)]
            line.cubicTo(QPointF(p1.x() + (p2.x() - p0.x()) / 6, p1.y() + (p2.y() - p0.y()) / 6),
                         QPointF(p2.x() - (p3.x() - p1.x()) / 6, p2.y() - (p3.y() - p1.y()) / 6), p2)
        area = QPainterPath(line)
        area.lineTo(pts[-1].x(), zero)
        area.lineTo(pts[0].x(), zero)
        area.closeSubpath()
        for sign, color in ((1, G), (-1, RED)):
            p.save()
            clip = QRectF(plot.left() - 4, plot.top() - 6, plot.width() + 8, zero - plot.top() + 6) if sign > 0 else \
                QRectF(plot.left() - 4, zero, plot.width() + 8, plot.bottom() - zero + 6)
            p.setClipRect(clip)
            g = QLinearGradient(0, plot.top() if sign > 0 else plot.bottom(), 0, zero)
            g.setColorAt(0, rgba(color, 0.40))
            g.setColorAt(1, rgba(color, 0.02))
            p.fillPath(area, g)
            p.setPen(QPen(QColor(color), 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            p.drawPath(line)
            p.restore()
        # geri ödeme noktası
        if self.payback is not None and self.payback != float("inf") and t > 0.6:
            px = x_of(self.payback)
            c = QPointF(px, zero)
            p.setPen(QPen(QColor("#0B1624"), 2))
            p.setBrush(QColor(TEXT))
            p.drawEllipse(c, 6, 6)
            label = f"Geri ödeme · {fmt(self.payback, 1)} yıl"
            f = qfont(11, 700)
            w = QFontMetrics(f).horizontalAdvance(label) + 24
            r = QRectF(min(max(px - w / 2, plot.left()), plot.right() - w), zero - 40, w, 24)
            lp = QPainterPath()
            lp.addRoundedRect(r, 12, 12)
            p.fillPath(lp, QColor(G))
            p.setPen(QColor("#04130D"))
            p.setFont(f)
            p.drawText(r, Qt.AlignCenter, label)
        if self._hover is not None:
            i = self._hover
            x = x_of(i)
            p.setPen(QPen(QColor(255, 255, 255, 40), 1))
            p.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            v = vals_m[i]
            col = G if v >= 0 else RED
            p.setBrush(QColor(col))
            p.setPen(QPen(QColor("#0B1624"), 2))
            p.drawEllipse(QPointF(x, y_of(v * t)), 5, 5)
            txt = [f"Yıl {self.years[i]}", f"Kümülatif: {fmt(v, 2)} M ₺"]
            f1, f2 = qfont(12, 700), qfont(12, mono=True)
            w = max(QFontMetrics(f1).horizontalAdvance(txt[0]), QFontMetrics(f2).horizontalAdvance(txt[1])) + 28
            r = QRectF(min(max(x - w / 2, 4), self.width() - w - 4), plot.top() + 2, w, 52)
            tp = QPainterPath()
            tp.addRoundedRect(r, 10, 10)
            p.fillPath(tp, QColor(5, 8, 14, 245))
            p.setPen(QPen(QColor(255, 255, 255, 18), 1))
            p.drawPath(tp)
            p.setFont(f1)
            p.setPen(QColor(SUB))
            p.drawText(QRectF(r.x() + 14, r.y() + 6, w - 20, 18), Qt.AlignVCenter, txt[0])
            p.setFont(f2)
            p.setPen(QColor(col))
            p.drawText(QRectF(r.x() + 14, r.y() + 26, w - 20, 18), Qt.AlignVCenter, txt[1])
