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
