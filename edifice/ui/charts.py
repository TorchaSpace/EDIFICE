"""Özel çubuk grafik: yuvarlak uçlu, gradyan dolgulu, aşağıdan yukarı yükselen animasyon."""
from __future__ import annotations

import math

from PySide6.QtCore import Property, QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath,
                           QPen)
from PySide6.QtWidgets import QSizePolicy, QWidget

from .widgets import FONT, INK, MUTED, fmt

# (üst, alt) gradyan çiftleri
PAIRS = {
    "soft": ("#CDEBDF", "#8FD3B8"),
    "emerald": ("#35E0AE", "#0A8F69"),
    "gold": ("#FBD983", "#D8962A"),
    "slate": ("#D3DBD8", "#AEBBB6"),
    "violet": ("#A99BFF", "#5B49D6"),
}


def nice_step(raw: float) -> float:
    if raw <= 0:
        return 1.0
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


class BarChart(QWidget):
    def __init__(self, categories: list[str], groups: dict[str, list[float]], scale: float = 1.0,
                 decimals: int = 0, colors: list[str] | None = None, unit: str = "",
                 min_h: int = 180):
        super().__init__()
        self.categories, self.groups = categories, groups
        self.scale, self.decimals, self.unit = scale, decimals, unit
        self.colors = colors or ["soft", "emerald", "gold"]
        top = max((v for vals in groups.values() for v in vals), default=1) / scale
        self.step = nice_step(top / 4)
        self.ticks = int(top / self.step) + 1
        self.ymax = self.step * self.ticks
        self.setMinimumHeight(min_h)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self._hover: int | None = None
        self._progress = 0.0
        self._anim = QPropertyAnimation(self, b"progress", self)
        self._anim.setDuration(1500)
        self._anim.setEasingCurve(QEasingCurve.Linear)

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

    # ---- etkileşim ----
    def _plot(self) -> QRectF:
        top = 34 if len(self.groups) > 1 else 8
        return QRectF(50, top, self.width() - 58, self.height() - top - 32)

    def mouseMoveEvent(self, e):
        plot = self._plot()
        n = len(self.categories)
        idx = None
        if plot.left() <= e.position().x() <= plot.right() and n:
            idx = min(n - 1, int((e.position().x() - plot.left()) / (plot.width() / n)))
        if idx != self._hover:
            self._hover = idx
            self.update()

    def leaveEvent(self, e):
        self._hover = None
        self.update()

    # ---- çizim ----
    def _t(self, idx: int, total: int) -> float:
        delay = (idx / max(total - 1, 1)) * 0.22
        t = max(0.0, min(1.0, (self._progress - delay) / 0.78))
        return 1 - (1 - t) ** 3

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        plot = self._plot()
        n, g = len(self.categories), len(self.groups)
        font = QFont(FONT)
        font.setPixelSize(11)
        p.setFont(font)

        for i in range(self.ticks + 1):
            v = i * self.step
            y = plot.bottom() - plot.height() * v / self.ymax
            p.setPen(QPen(QColor("#F0EEE8"), 1))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(0, y - 9, plot.left() - 10, 18), Qt.AlignRight | Qt.AlignVCenter,
                       fmt(v, self.decimals))
        if not n:
            return
        slot = plot.width() / n

        if self._hover is not None:
            hp = QPainterPath()
            hp.addRoundedRect(QRectF(plot.left() + slot * self._hover + 2, plot.top() - 2,
                                     slot - 4, plot.height() + 4), 12, 12)
            p.fillPath(hp, QColor("#F6F4EE"))

        bw = min(slot * 0.7 / g, 34)
        gap = 4
        total_w = g * bw + (g - 1) * gap
        total = n * g
        for ci in range(n):
            x0 = plot.left() + slot * ci + (slot - total_w) / 2
            for gi, (name, vals) in enumerate(self.groups.items()):
                v = vals[ci] / self.scale
                h = plot.height() * v / self.ymax * self._t(ci * g + gi, total)
                if h < 0.5:
                    continue
                r = min(bw / 2, 9)
                top, bot = PAIRS[self.colors[gi % len(self.colors)]]
                grad = QLinearGradient(0, plot.bottom() - h, 0, plot.bottom())
                grad.setColorAt(0, QColor(top))
                grad.setColorAt(1, QColor(bot))
                path = QPainterPath()
                path.addRoundedRect(QRectF(x0 + gi * (bw + gap), plot.bottom() - h, bw, h + r), r, r)
                p.save()
                p.setClipRect(QRectF(0, 0, self.width(), plot.bottom()))
                p.fillPath(path, grad)
                p.restore()
            fm = QFontMetrics(font)
            label = fm.elidedText(self.categories[ci], Qt.ElideRight, int(slot - 6))
            p.setPen(QColor(INK if ci == self._hover else MUTED))
            p.drawText(QRectF(plot.left() + slot * ci, plot.bottom() + 8, slot, 18),
                       Qt.AlignHCenter | Qt.AlignVCenter, label)

        if g > 1:
            x = plot.left()
            for gi, name in enumerate(self.groups):
                top, bot = PAIRS[self.colors[gi % len(self.colors)]]
                grad = QLinearGradient(x, 6, x, 18)
                grad.setColorAt(0, QColor(top))
                grad.setColorAt(1, QColor(bot))
                dot = QPainterPath()
                dot.addRoundedRect(QRectF(x, 6, 12, 12), 6, 6)
                p.fillPath(dot, grad)
                p.setPen(QColor(MUTED))
                w = QFontMetrics(font).horizontalAdvance(name)
                p.drawText(QRectF(x + 18, 2, w + 4, 20), Qt.AlignVCenter, name)
                x += 18 + w + 22

        if self._hover is not None:
            self._tooltip(p, plot, slot, font)

    def _tooltip(self, p: QPainter, plot: QRectF, slot: float, font: QFont):
        ci = self._hover
        lines = [self.categories[ci]] + [
            f"{name}: {fmt(vals[ci] / self.scale, max(self.decimals, 1 if self.scale > 1 else 0))} {self.unit}".strip()
            for name, vals in self.groups.items()]
        bold = QFont(font)
        bold.setBold(True)
        fm = QFontMetrics(font)
        w = max(fm.horizontalAdvance(s) for s in lines) + 28
        h = 20 * len(lines) + 12
        cx = plot.left() + slot * (ci + 0.5)
        x = max(4, min(self.width() - w - 4, cx - w / 2))
        y = plot.top() + 4
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, w, h), 12, 12)
        grad = QLinearGradient(x, y, x, y + h)
        grad.setColorAt(0, QColor("#17433A"))
        grad.setColorAt(1, QColor("#0B2822"))
        p.fillPath(path, grad)
        for i, s in enumerate(lines):
            p.setFont(bold if i == 0 else font)
            p.setPen(QColor("#FFFFFF") if i == 0 else QColor("#BFE3D5"))
            p.drawText(QRectF(x + 14, y + 6 + 20 * i, w - 20, 20), Qt.AlignVCenter, s)
