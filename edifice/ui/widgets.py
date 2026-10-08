"""EDIFI'CE tasarım sistemi: renkler, tipografi, animasyonlu bileşenler."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCharts import QChart
from PySide6.QtCore import (Property, QEasingCurve, QMargins, QPointF, QPropertyAnimation,
                            QRectF, QSize, Qt, QVariantAnimation)
from PySide6.QtGui import (QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath,
                           QPen, QPixmap)
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QLabel,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

# ---- Renk paleti ----------------------------------------------------------
INK = "#0E2A24"
MUTED = "#6B7873"
BG = "#F5F4F0"
SURFACE = "#FFFFFF"
BORDER = "#ECE9E2"
ACCENT = "#0F9D75"
ACCENT_SOFT = "#E6F5EF"
GOLD = "#C9A24B"
SIDEBAR_TOP, SIDEBAR_BOTTOM = "#0A1D18", "#12382D"
GRADE_COLORS = {"A": "#0F9D75", "B": "#6DB33F", "C": "#E3B341", "D": "#EE8A2B", "E": "#D8483F"}
SERIES_COLORS = ["#A9D5C4", ACCENT, GOLD]
FONT = "SF Pro Display"

STYLE = f"""
* {{ font-family: "SF Pro Display", "Helvetica Neue", "Inter", "Segoe UI", sans-serif; }}
QMainWindow, QScrollArea, QWidget#page {{ background: {BG}; }}
QScrollArea {{ border: none; }}
QWidget#side {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {SIDEBAR_TOP}, stop:1 {SIDEBAR_BOTTOM}); }}
QPushButton#nav {{ background: transparent; color: #9DB7AD; border: none; border-left: 3px solid transparent;
    text-align: left; padding: 13px 20px 13px 22px; font-size: 14px; font-weight: 500; }}
QPushButton#nav:hover {{ color: white; background: rgba(255,255,255,0.05); }}
QPushButton#nav:checked {{ color: white; background: rgba(15,157,117,0.20); border-left: 3px solid #2FD3A0; font-weight: 600; }}
QPushButton#ghost {{ background: transparent; color: #CFE5DC; border: 1px solid rgba(255,255,255,0.25);
    border-radius: 10px; padding: 11px 16px; font-size: 13px; font-weight: 600; margin: 0 18px; }}
QPushButton#ghost:hover {{ background: rgba(255,255,255,0.10); color: white; }}
QFrame#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 16px; }}
QLabel {{ background: transparent; color: {INK}; }}
QLabel#eyebrow {{ color: {ACCENT}; font-size: 11px; font-weight: 700; letter-spacing: 2px; }}
QLabel#h1 {{ font-size: 30px; font-weight: 700; color: {INK}; }}
QLabel#muted {{ color: {MUTED}; font-size: 13px; }}
QLabel#cardTitle {{ color: {MUTED}; font-size: 11px; font-weight: 700; letter-spacing: 1px; }}
QLabel#cardValue {{ color: {INK}; font-size: 28px; font-weight: 700; }}
QLabel#cardSub {{ color: {MUTED}; font-size: 12px; }}
QLabel#section {{ color: {INK}; font-size: 15px; font-weight: 700; }}
QLabel#side {{ color: #6F8C81; font-size: 11px; }}
QPushButton#toggle {{ background: {SURFACE}; color: {INK}; border: 1.5px solid {BORDER}; border-radius: 14px;
    text-align: left; padding: 12px 16px; font-size: 13px; }}
QPushButton#toggle:hover {{ border-color: #BFE3D5; }}
QPushButton#toggle:checked {{ background: {ACCENT_SOFT}; border: 1.5px solid {ACCENT}; font-weight: 600; }}
QTableWidget {{ background: transparent; border: none; outline: 0; font-size: 13px; }}
QTableWidget::item {{ border-bottom: 1px solid #F2F0EA; padding: 4px 8px; }}
QTableWidget::item:hover {{ background: #F8F7F3; }}
QTableWidget::item:selected {{ background: {ACCENT_SOFT}; color: {INK}; }}
QHeaderView {{ background: transparent; }}
QTableCornerButton::section {{ background: transparent; border: none; }}
QHeaderView::section {{ background: transparent; border: none; border-bottom: 1px solid {BORDER}; color: {MUTED};
    padding: 10px 8px; font-size: 11px; font-weight: 700; letter-spacing: 1px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #D5D2C8; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


# ---- Yardımcılar ----------------------------------------------------------

def shadow(widget: QWidget, blur: int = 28, dy: int = 6, alpha: int = 24) -> QGraphicsDropShadowEffect:
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    eff.setColor(QColor(14, 42, 36, alpha))
    widget.setGraphicsEffect(eff)
    return eff


def fmt(n: float, digits: int = 0) -> str:
    s = f"{n:,.{digits}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_years(y: float) -> str:
    return "-" if y == float("inf") else f"{fmt(y, 1)} yıl"


def grade_for(score: float) -> str:
    return "A" if score >= 80 else "B" if score >= 65 else "C" if score >= 50 else "D" if score >= 35 else "E"


def score_color(score: float) -> str:
    return GRADE_COLORS[grade_for(score)]


def header(eyebrow: str, title: str, subtitle: str = "") -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 4)
    lay.setSpacing(2)
    e = QLabel(eyebrow.upper())
    e.setObjectName("eyebrow")
    t = QLabel(title)
    t.setObjectName("h1")
    lay.addWidget(e)
    lay.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("muted")
        s.setWordWrap(True)
        lay.addWidget(s)
    return w


def section(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("section")
    return lbl


def muted(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("muted")
    lbl.setWordWrap(True)
    return lbl


def style_chart(chart: QChart, legend: bool = False):
    chart.setBackgroundVisible(False)
    chart.setPlotAreaBackgroundVisible(False)
    chart.setMargins(QMargins(0, 0, 0, 0))
    chart.layout().setContentsMargins(0, 0, 0, 0)
    chart.setAnimationOptions(QChart.SeriesAnimations)
    chart.setAnimationDuration(900)
    chart.setAnimationEasingCurve(QEasingCurve.OutCubic)
    chart.legend().setVisible(legend)
    chart.legend().setAlignment(Qt.AlignTop)
    chart.legend().setLabelColor(QColor(MUTED))
    f = QFont(FONT)
    f.setPixelSize(12)
    chart.legend().setFont(f)
    for ax in chart.axes():
        ax.setLabelsColor(QColor(MUTED))
        lf = QFont(FONT)
        lf.setPixelSize(11)
        ax.setLabelsFont(lf)
        ax.setGridLineColor(QColor("#EFEDE7"))
        ax.setLinePen(QPen(Qt.NoPen))


class _Animated(QWidget):
    """0 -> hedef oranına animasyonlu ilerleyen `frac` özelliği."""

    def __init__(self, score: float, ms: int):
        super().__init__()
        self._score, self._frac = score, 0.0
        self._anim = QPropertyAnimation(self, b"frac", self)
        self._anim.setDuration(ms)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def _get(self) -> float:
        return self._frac

    def _set(self, v: float):
        self._frac = v
        self.update()

    frac = Property(float, _get, _set)

    def showEvent(self, e):
        super().showEvent(e)
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(self._score / 100)
        self._anim.start()


# ---- Bileşenler -----------------------------------------------------------

class Card(QFrame):
    """KPI kartı: sayaç animasyonu (0 -> değer) ve hover'da yükselen gölge."""

    def __init__(self, title: str, value: str = "-", sub: str = ""):
        super().__init__()
        self.setObjectName("card")
        self.setMinimumHeight(108)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(4)
        self._t, self._v, self._s = QLabel(title.upper()), QLabel(value), QLabel(sub)
        self._t.setObjectName("cardTitle")
        self._v.setObjectName("cardValue")
        self._s.setObjectName("cardSub")
        for w in (self._t, self._v, self._s):
            lay.addWidget(w)
        lay.addStretch()
        self._shown = 0.0
        self._target: float | None = None
        self._fmt: Callable[[float], str] | None = None
        self._anim: QVariantAnimation | None = None
        self._shadow = shadow(self, 28, 6, 22)
        self._lift = QPropertyAnimation(self._shadow, b"blurRadius", self)
        self._lift.setDuration(180)

    def set(self, value: str, sub: str = "", color: str | None = None):
        self._target = None
        self._v.setText(value)
        self._s.setText(sub)
        self._v.setStyleSheet(f"color: {color};" if color else "")

    def set_number(self, target: float, formatter: Callable[[float], str], sub: str = "",
                   color: str | None = None, live: bool = False):
        """live=True: mevcut değerden yeni değere hemen animasyonla geçer."""
        start = self._shown if live else 0.0
        self._target, self._fmt = target, formatter
        self._s.setText(sub)
        self._v.setStyleSheet(f"color: {color};" if color else "")
        if live and self.isVisible():
            self._play(start)
        else:
            self._v.setText(formatter(target))

    def showEvent(self, e):
        super().showEvent(e)
        if self._target is not None and self._fmt is not None:
            self._play(0.0)

    def _play(self, start: float):
        if self._anim:
            self._anim.stop()
        target, fmt_fn = self._target, self._fmt
        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(float(start))
        self._anim.setEndValue(float(target))
        self._anim.setDuration(900)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

        def step(v):
            self._shown = v
            self._v.setText(fmt_fn(v))
        self._anim.valueChanged.connect(step)
        self._anim.finished.connect(lambda: (setattr(self, "_shown", target), self._v.setText(fmt_fn(target))))
        self._anim.start()

    def _hover(self, blur: int, dy: int):
        self._lift.stop()
        self._lift.setEndValue(blur)
        self._lift.start()
        self._shadow.setOffset(0, dy)

    def enterEvent(self, e):
        self._hover(48, 12)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover(28, 6)
        super().leaveEvent(e)


class Panel(QFrame):
    """Başlıklı beyaz yüzey (grafik/tablo için)."""

    def __init__(self, title: str = "", subtitle: str = ""):
        super().__init__()
        self.setObjectName("card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(22, 18, 22, 16)
        self.lay.setSpacing(8)
        if title:
            self.lay.addWidget(section(title))
        if subtitle:
            self.lay.addWidget(muted(subtitle))
        shadow(self, 24, 4, 16)


class Gauge(_Animated):
    """Animasyonlu dairesel Health Score göstergesi."""

    def __init__(self, score: float, grade: str):
        super().__init__(score, 1300)
        self._grade = grade
        self.setMinimumSize(230, 220)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height()) - 30
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        w = 16
        p.setPen(QPen(QColor("#EEECE6"), w, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 225 * 16, -270 * 16)
        p.setPen(QPen(QColor(score_color(self._frac * 100)), w, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 225 * 16, int(-270 * 16 * self._frac))
        f = QFont(FONT)
        f.setPixelSize(int(side * 0.30))
        f.setWeight(QFont.Bold)
        p.setFont(f)
        p.setPen(QColor(INK))
        p.drawText(rect.adjusted(0, -side * 0.10, 0, 0), Qt.AlignCenter, f"{self._frac * 100:.0f}")
        f2 = QFont(FONT)
        f2.setPixelSize(int(side * 0.085))
        p.setFont(f2)
        p.setPen(QColor(MUTED))
        p.drawText(rect.adjusted(0, side * 0.34, 0, 0), Qt.AlignCenter, "/ 100")
        badge = QRectF(rect.center().x() - 24, rect.bottom() - 26, 48, 28)
        path = QPainterPath()
        path.addRoundedRect(badge, 14, 14)
        p.fillPath(path, QColor(GRADE_COLORS[self._grade]))
        f3 = QFont(FONT)
        f3.setPixelSize(15)
        f3.setWeight(QFont.Bold)
        p.setFont(f3)
        p.setPen(Qt.white)
        p.drawText(badge, Qt.AlignCenter, self._grade)


class ScoreBar(_Animated):
    """İnce, animasyonlu skor çubuğu (renk puana göre)."""

    def __init__(self, score: float):
        super().__init__(score, 1000)
        self.setFixedHeight(22)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h, y = 8, (self.height() - 8) / 2
        w = self.width() - 44
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#EEECE6"))
        p.drawRoundedRect(QRectF(0, y, w, h), 4, 4)
        p.setBrush(QColor(score_color(self._score)))
        p.drawRoundedRect(QRectF(0, y, max(h, w * self._frac), h), 4, 4)
        f = QFont(FONT)
        f.setPixelSize(13)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(QColor(INK))
        p.drawText(QRectF(w + 8, 0, 36, self.height()), Qt.AlignVCenter | Qt.AlignRight,
                   f"{self._frac * 100:.0f}")


class FadeStack(QStackedWidget):
    """Sayfa geçişlerinde yumuşak fade-in."""

    def setCurrentIndex(self, index: int):
        super().setCurrentIndex(index)
        w = self.currentWidget()
        if w is None:
            return
        eff = QGraphicsOpacityEffect(w)
        w.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", w)
        anim.setDuration(320)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(lambda: w.setGraphicsEffect(None))
        anim.start()
        self._anim = anim


# ---- Navigasyon -----------------------------------------------------------

def nav_icon(kind: str) -> QIcon:
    icon = QIcon()
    for color, state in (("#9DB7AD", QIcon.Off), ("#FFFFFF", QIcon.On)):
        pm = QPixmap(40, 40)
        pm.setDevicePixelRatio(2)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(color), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        if kind == "overview":
            for x, y in ((2, 2), (11, 2), (2, 11), (11, 11)):
                p.drawRoundedRect(QRectF(x, y, 7, 7), 1.8, 1.8)
        elif kind == "consumption":
            for x, h in ((3, 8), (8.5, 15), (14, 11)):
                p.drawRoundedRect(QRectF(x, 18 - h, 3.5, h), 1, 1)
        elif kind == "opportunities":
            p.drawPolyline([QPointF(2.5, 15), QPointF(8, 9), QPointF(11.5, 12.5), QPointF(17, 4.5)])
            p.drawPolyline([QPointF(12.5, 4.5), QPointF(17, 4.5), QPointF(17, 9)])
        else:
            p.drawEllipse(QRectF(2, 4, 10, 10))
            p.drawEllipse(QRectF(8, 6, 10, 10))
        p.end()
        icon.addPixmap(pm, QIcon.Normal, state)
    return icon


class NavButton(QPushButton):
    def __init__(self, text: str, kind: str):
        super().__init__("   " + text)
        self.setObjectName("nav")
        self.setCheckable(True)
        self.setIcon(nav_icon(kind))
        self.setIconSize(QSize(20, 20))
        self.setCursor(Qt.PointingHandCursor)


class Logo(QWidget):
    """Sidebar logosu: bina siluetleri + EDIFI'CE yazısı."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(96)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        badge = QRectF(22, 28, 40, 40)
        path = QPainterPath()
        path.addRoundedRect(badge, 11, 11)
        g = QLinearGradient(badge.topLeft(), badge.bottomRight())
        g.setColorAt(0, QColor("#2FD3A0"))
        g.setColorAt(1, QColor("#0F9D75"))
        p.fillPath(path, QBrush(g))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#0A1D18"))
        for x, y, w, h in ((8, 18, 7, 14), (17, 9, 8, 23), (27, 15, 6, 17)):
            p.drawRoundedRect(QRectF(badge.x() + x, badge.y() + y, w, h), 1.5, 1.5)
        f = QFont(FONT)
        f.setPixelSize(19)
        f.setWeight(QFont.Bold)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
        p.setFont(f)
        p.setPen(Qt.white)
        p.drawText(QPointF(74, 46), "EDIFI'CE")
        f2 = QFont(FONT)
        f2.setPixelSize(9)
        f2.setLetterSpacing(QFont.AbsoluteSpacing, 1.0)
        p.setFont(f2)
        p.setPen(QColor("#6F8C81"))
        p.drawText(QPointF(75, 62), "BUILDING INTELLIGENCE")
