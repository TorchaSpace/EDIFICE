"""EDIFI'CE tasarım sistemi (Figma "Premium SaaS Dashboard" koyu teması)."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import (Property, QEasingCurve, QParallelAnimationGroup, QPointF, QPropertyAnimation, QRectF, QSize, Qt,
                            QVariantAnimation)
from PySide6.QtGui import (QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath,
                           QPen, QPixmap)
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

# ---- Tasarım tokenları (Figma Make: App.tsx) -------------------------------
G = "#0DDD96"
INDIGO = "#6366F1"
AMBER = "#F59E0B"
RED = "#F43F5E"
BG = "#070C12"
SURFACE = "#0B1624"
SIDEBAR_BG = "#05080E"
TEXT = "#E8F2FF"
SUB = "#A3B6C9"
MUTED = "#7A90A8"
DIM = "#5C7590"
BORDER = "rgba(255,255,255,0.07)"
G_SOFT = "rgba(13,221,150,0.10)"
INK = TEXT  # geriye dönük isim
ACCENT = G

GRADE_COLORS = {"A": G, "B": "#5BE3B4", "C": AMBER, "D": "#FB923C", "E": RED}
SANS = ["Manrope", "SF Pro Display", "Helvetica Neue", "Arial"]
MONO = ["DM Mono", "SF Mono", "Menlo", "Courier New"]
FONT = SANS[0]


def qfont(px: int, weight: int = QFont.Normal, mono: bool = False, spacing: float = 0.0) -> QFont:
    f = QFont()
    f.setFamilies(MONO if mono else SANS)
    f.setPixelSize(px)
    f.setWeight(QFont.Weight(weight))
    if spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


def rgba(hex_color: str, a: float) -> QColor:
    c = QColor(hex_color)
    c.setAlphaF(a)
    return c


_SANS_CSS = ", ".join(f'"{n}"' for n in SANS) + ", sans-serif"
_MONO_CSS = ", ".join(f'"{n}"' for n in MONO) + ", monospace"

STYLE_TEMPLATE = f"""
* {{ font-family: {_SANS_CSS}; }}
QMainWindow, QScrollArea, QWidget#page, QWidget#root {{ background: {BG}; }}
QScrollArea {{ border: none; }}
QWidget#side {{ background: {SIDEBAR_BG}; border-right: 1px solid {BORDER}; }}
QWidget#topbar {{ background: {SIDEBAR_BG}; border-bottom: 1px solid {BORDER}; }}
QWidget#sidehead {{ border-bottom: 1px solid {BORDER}; }}
QWidget#sidefoot {{ border-top: 1px solid {BORDER}; }}
QLabel {{ background: transparent; color: {TEXT}; }}
QPushButton#nav {{ background: transparent; color: {SUB}; border: 1px solid transparent; border-radius: 12px;
    text-align: left; padding: 11px 14px; font-size: 13px; font-weight: 500; }}
QPushButton#nav:hover {{ color: {TEXT}; background: rgba(255,255,255,0.03); }}
QPushButton#nav:checked {{ color: {G}; background: transparent; font-weight: 700; }}
QFrame#navIndicator {{ background: {G_SOFT}; border: 1px solid rgba(13,221,150,0.22); border-radius: 12px; }}
QPushButton#export {{ background: {G_SOFT}; color: {G}; border: 1px solid rgba(13,221,150,0.25); border-radius: 9px;
    padding: 7px 16px; font-size: 13px; font-weight: 700; }}
QPushButton#export:hover {{ background: rgba(13,221,150,0.18); }}
QFrame#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 18px; }}
QFrame#card:hover {{ border: 1px solid rgba(13,221,150,0.18); }}
QFrame#inner {{ background: rgba(255,255,255,0.02); border: 1px solid {BORDER}; border-radius: 12px; }}
QLabel#eyebrow {{ color: {MUTED}; font-size: 11px; font-weight: 700; letter-spacing: 1.4px; }}
QLabel#h1 {{ font-size: 26px; font-weight: 800; color: {TEXT}; }}
QLabel#title {{ font-size: 17px; font-weight: 700; color: {TEXT}; }}
QLabel#muted {{ color: {SUB}; font-size: 13px; }}
QLabel#cardTitle {{ color: {MUTED}; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; }}
QLabel#cardValue {{ color: {TEXT}; font-size: 27px; font-weight: 500; font-family: {_MONO_CSS}; }}
QLabel#cardSub {{ color: {SUB}; font-size: 12px; }}
QLabel#up {{ color: {G}; background: {G_SOFT}; border-radius: 10px; padding: 3px 9px; font-size: 11px; font-weight: 500; font-family: {_MONO_CSS}; }}
QLabel#down {{ color: {RED}; background: rgba(244,63,94,0.10); border-radius: 10px; padding: 3px 9px; font-size: 11px; font-weight: 500; font-family: {_MONO_CSS}; }}
QLabel#mono {{ font-family: {_MONO_CSS}; color: {MUTED}; font-size: 10px; }}
QLabel#livepill {{ color: {G}; background: rgba(13,221,150,0.05); border: 1px solid rgba(13,221,150,0.16);
    border-radius: 14px; padding: 5px 14px; font-size: 11px; font-weight: 700; }}
QLabel#datepill {{ font-family: {_MONO_CSS}; color: {SUB}; font-size: 11px; background: rgba(255,255,255,0.03);
    border: 1px solid {BORDER}; border-radius: 8px; padding: 5px 11px; }}
QLabel#crumb {{ color: {MUTED}; font-size: 12px; }}
QLabel#crumbnow {{ color: {TEXT}; font-size: 14px; font-weight: 700; }}
QLabel#section {{ color: {DIM}; font-size: 10px; font-weight: 700; letter-spacing: 1.6px; padding: 12px 12px 6px 12px; }}
QPushButton#toggle {{ background: rgba(255,255,255,0.03); color: {TEXT}; border: 1px solid {BORDER}; border-radius: 12px;
    text-align: left; padding: 12px 16px; font-size: 13px; }}
QPushButton#toggle:hover {{ border: 1px solid rgba(13,221,150,0.25); }}
QPushButton#toggle:checked {{ background: {G_SOFT}; border: 1px solid rgba(13,221,150,0.35); font-weight: 700; color: {G}; }}
QTableWidget {{ background: transparent; color: {TEXT}; border: none; outline: 0; font-size: 13px;
    selection-background-color: rgba(13,221,150,0.10); selection-color: {TEXT}; }}
QTableWidget::item {{ color: {TEXT}; border-bottom: 1px solid {BORDER}; padding: 4px 8px; }}
QTableWidget::item:hover {{ background: rgba(255,255,255,0.025); }}
QTableWidget::item:selected {{ background: {G_SOFT}; color: {TEXT}; }}
QHeaderView {{ background: transparent; }}
QTableCornerButton::section {{ background: transparent; border: none; }}
QHeaderView::section {{ background: rgba(255,255,255,0.02); border: none; border-bottom: 1px solid {BORDER}; color: {MUTED};
    padding: 12px 8px; font-size: 10px; font-weight: 700; letter-spacing: 1.2px; }}
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 4px 2px 4px 2px; }}
QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.14); border-radius: 4px; min-height: 40px; margin: 0 2px; }}
QScrollBar::handle:vertical:hover {{ background: rgba(13,221,150,0.5); }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px 4px 2px 4px; }}
QScrollBar::handle:horizontal {{ background: rgba(255,255,255,0.14); border-radius: 4px; min-width: 40px; margin: 2px 0; }}
QScrollBar::handle:horizontal:hover {{ background: rgba(13,221,150,0.5); }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QAbstractScrollArea::corner {{ background: transparent; }}
QDialog {{ background: {BG}; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background: rgba(255,255,255,0.04); color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 10px; padding: 9px 12px; font-size: 13px; selection-background-color: rgba(13,221,150,0.35); }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border: 1px solid rgba(13,221,150,0.55); }}
QComboBox::drop-down {{ border: none; width: 30px; subcontrol-origin: padding; subcontrol-position: center right; }}
QComboBox::down-arrow {{ image: url(__ARROW__); width: 12px; height: 12px; }}
QTableWidget QLineEdit {{ background: #0F1D30; color: {TEXT}; border: 1px solid rgba(13,221,150,0.6); border-radius: 6px;
    padding: 0 8px; font-size: 13px; }}
QComboBox QAbstractItemView {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER}; selection-background-color: {G_SOFT}; outline: 0; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0; border: none; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; color: {MUTED}; padding: 9px 18px; margin-right: 6px; border-radius: 10px;
    border: 1px solid transparent; font-size: 12px; font-weight: 600; }}
QTabBar::tab:selected {{ color: {G}; background: {G_SOFT}; border: 1px solid rgba(13,221,150,0.18); }}
QTabBar::tab:hover:!selected {{ color: {TEXT}; }}
QPushButton#primary {{ background: {G}; color: #04130D; border: none; border-radius: 10px; padding: 10px 22px;
    font-size: 12px; font-weight: 800; }}
QPushButton#primary:hover {{ background: #3AF0B2; }}
QPushButton#secondary {{ background: transparent; color: {SUB}; border: 1px solid {BORDER}; border-radius: 10px;
    padding: 10px 18px; font-size: 12px; font-weight: 600; }}
QPushButton#secondary:hover {{ color: {TEXT}; border: 1px solid rgba(255,255,255,0.18); }}
QPushButton#bldg {{ background: rgba(255,255,255,0.03); border: 1px solid {BORDER}; border-radius: 12px; text-align: left;
    padding: 0; }}
QPushButton#bldg:hover {{ border: 1px solid rgba(13,221,150,0.18); }}
QPushButton#bldg::menu-indicator {{ image: none; }}
QLabel#field {{ color: {SUB}; font-size: 12px; font-weight: 600; }}
QLabel#error {{ color: {RED}; font-size: 12px; }}
QMenu {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 8px 18px; border-radius: 8px; }}
QMenu::item:selected {{ background: {G_SOFT}; color: {G}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 6px 4px; }}
QToolTip {{ background: {SIDEBAR_BG}; color: {TEXT}; border: 1px solid {BORDER}; padding: 6px; }}
"""


# ---- Yardımcılar ----------------------------------------------------------

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
    lay.setContentsMargins(0, 0, 0, 2)
    lay.setSpacing(3)
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
    lbl.setObjectName("title")
    return lbl


def muted(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("muted")
    lbl.setWordWrap(True)
    return lbl


def badge(text: str, color: str) -> QLabel:
    lbl = QLabel(text.upper())
    c = QColor(color)
    lbl.setStyleSheet(
        f"color: {color}; background: rgba({c.red()},{c.green()},{c.blue()},0.10);"
        f"border: 1px solid rgba({c.red()},{c.green()},{c.blue()},0.14); border-radius: 10px;"
        "padding: 2px 9px; font-size: 9px; font-weight: 700; letter-spacing: 0.8px;")
    return lbl


class _Animated(QWidget):
    """0 -> hedef oranına animasyonlu ilerleyen `frac` özelliği."""

    def __init__(self, score: float, ms: int):
        super().__init__()
        self._score, self._frac = score, 0.0
        self._anim = QPropertyAnimation(self, b"frac", self)
        self._anim.setDuration(ms)
        self._anim.setEasingCurve(QEasingCurve.OutQuart)

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
    """KPI kartı: üstte vurgu çizgisi, mono değer, trend rozeti, sayaç animasyonu."""

    def __init__(self, title: str, value: str = "-", sub: str = "", accent: str = G,
                 hero: bool = False, trend: str = "", up: bool = True):
        super().__init__()
        self.setObjectName("card")
        self.setMinimumHeight(118)
        self._accent = accent
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(8)
        self._t, self._v, self._s = QLabel(title.upper()), QLabel(value), QLabel(sub)
        self._t.setObjectName("cardTitle")
        self._v.setObjectName("cardValue")
        self._s.setObjectName("cardSub")
        self._s.setWordWrap(True)
        self._trend = QLabel(trend)
        self._trend.setVisible(bool(trend))
        self._trend.setObjectName("up" if up else "down")
        lay.addWidget(self._t)
        lay.addWidget(self._v)
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(self._s, 1)
        row.addWidget(self._trend)
        lay.addLayout(row)
        self._shown = 0.0
        self._target: float | None = None
        self._fmt: Callable[[float], str] | None = None
        self._anim: QVariantAnimation | None = None

    def set_trend(self, text: str, good: bool):
        self._trend.setText(text)
        self._trend.setObjectName("up" if good else "down")
        self._trend.style().unpolish(self._trend)
        self._trend.style().polish(self._trend)
        self._trend.setVisible(bool(text))

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
        self._anim.setDuration(1100)
        self._anim.setEasingCurve(QEasingCurve.OutQuart)

        def step(v):
            self._shown = v
            self._v.setText(fmt_fn(v))
        self._anim.valueChanged.connect(step)
        self._anim.finished.connect(lambda: (setattr(self, "_shown", target), self._v.setText(fmt_fn(target))))
        self._anim.start()

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        g = QLinearGradient(20, 0, self.width() - 20, 0)
        g.setColorAt(0, rgba(self._accent, 0))
        g.setColorAt(0.5, rgba(self._accent, 0.33))
        g.setColorAt(1, rgba(self._accent, 0))
        p.fillRect(QRectF(20, 0, self.width() - 40, 1), g)


class Panel(QFrame):
    """Başlıklı koyu yüzey (grafik/tablo için)."""

    def __init__(self, title: str = "", subtitle: str = "", eyebrow: str = ""):
        super().__init__()
        self.setObjectName("card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(22, 20, 22, 18)
        self.lay.setSpacing(6)
        if eyebrow:
            e = QLabel(eyebrow.upper())
            e.setObjectName("eyebrow")
            self.lay.addWidget(e)
        if title:
            self.lay.addWidget(section(title))
        if subtitle:
            self.lay.addWidget(muted(subtitle))


class Gauge(_Animated):
    """Animasyonlu dairesel Health Score göstergesi."""

    def __init__(self, score: float, grade: str):
        super().__init__(score, 1300)
        self._grade = grade
        self.setMinimumSize(200, 190)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height()) - 26
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        w = 12
        p.setPen(QPen(QColor(255, 255, 255, 16), w, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 225 * 16, -270 * 16)
        col = QColor(score_color(self._frac * 100))
        glow = QColor(col)
        glow.setAlpha(40)
        p.setPen(QPen(glow, w + 8, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 225 * 16, int(-270 * 16 * self._frac))
        p.setPen(QPen(col, w, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 225 * 16, int(-270 * 16 * self._frac))
        p.setFont(qfont(int(side * 0.28), QFont.Medium, mono=True, spacing=-2))
        p.setPen(QColor(TEXT))
        p.drawText(rect.adjusted(0, -side * 0.08, 0, 0), Qt.AlignCenter, f"{self._frac * 100:.0f}")
        p.setFont(qfont(int(side * 0.075), mono=True))
        p.setPen(QColor(MUTED))
        p.drawText(rect.adjusted(0, side * 0.26, 0, 0), Qt.AlignCenter, "/ 100")
        pill = QRectF(rect.center().x() - 22, rect.bottom() - 24, 44, 24)
        path = QPainterPath()
        path.addRoundedRect(pill, 12, 12)
        p.fillPath(path, rgba(col.name(), 0.14))
        p.setPen(QPen(rgba(col.name(), 0.4), 1))
        p.drawPath(path)
        p.setFont(qfont(13, QFont.Bold))
        p.setPen(col)
        p.drawText(pill, Qt.AlignCenter, self._grade)


class ScoreBar(_Animated):
    """İnce (4px), animasyonlu skor çubuğu; sağda mono puan."""

    def __init__(self, score: float):
        super().__init__(score, 1000)
        self.setFixedHeight(20)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h, y = 4, (self.height() - 4) / 2
        w = self.width() - 36
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 14))
        p.drawRoundedRect(QRectF(0, y, w, h), 2, 2)
        col = QColor(score_color(self._score))
        col.setAlphaF(0.9)
        p.setBrush(col)
        p.drawRoundedRect(QRectF(0, y, max(h, w * self._frac), h), 2, 2)
        p.setFont(qfont(13, QFont.Medium, mono=True))
        p.setPen(QColor(score_color(self._score)))
        p.drawText(QRectF(w + 6, 0, 30, self.height()), Qt.AlignVCenter | Qt.AlignRight,
                   f"{self._frac * 100:.0f}")


class FadeStack(QStackedWidget):
    """Sayfa geçişlerinde yumuşak fade-in + hafif aşağıdan yukarı kayma."""

    def setCurrentIndex(self, index: int):
        super().setCurrentIndex(index)
        w = self.currentWidget()
        if w is None:
            return
        group = QParallelAnimationGroup(w)
        eff = QGraphicsOpacityEffect(w)
        w.setGraphicsEffect(eff)
        fade = QPropertyAnimation(eff, b"opacity", w)
        fade.setDuration(520)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.OutQuart)
        group.addAnimation(fade)
        if w.width() > 0:
            slide = QPropertyAnimation(w, b"pos", w)
            slide.setDuration(520)
            end = w.pos()
            slide.setStartValue(QPointF(end.x(), end.y() + 18).toPoint())
            slide.setEndValue(end)
            slide.setEasingCurve(QEasingCurve.OutQuart)
            group.addAnimation(slide)
        group.finished.connect(lambda: (w.setGraphicsEffect(None), w.move(0, 0)))
        group.start()
        self._anim = group


# ---- Navigasyon -----------------------------------------------------------

def nav_icon(kind: str) -> QIcon:
    icon = QIcon()
    for color, state in ((MUTED, QIcon.Off), (G, QIcon.On)):
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
        self.setAutoExclusive(True)
        self.setIcon(nav_icon(kind))
        self.setIconSize(QSize(18, 18))
        self.setCursor(Qt.PointingHandCursor)


class NavBar(QWidget):
    """Sekmeler + seçili sekmeye kayan yeşil gösterge."""

    def __init__(self, items: list[tuple[str, str]]):
        super().__init__()
        self.indicator = QFrame(self)
        self.indicator.setObjectName("navIndicator")
        self.indicator.lower()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(4)
        self.buttons: list[NavButton] = []
        for text, kind in items:
            b = NavButton(text, kind)
            lay.addWidget(b)
            self.buttons.append(b)
        self._current = 0
        self._anim = QPropertyAnimation(self.indicator, b"geometry", self)
        self._anim.setDuration(520)
        self._anim.setEasingCurve(QEasingCurve.OutQuart)

    def _target(self, i: int):
        return self.buttons[i].geometry()

    def select(self, i: int, animate: bool = True):
        self.buttons[i].setChecked(True)
        self._current = i
        if animate and self.buttons[i].width() > 0 and self.isVisible():
            self._anim.stop()
            self._anim.setStartValue(self.indicator.geometry())
            self._anim.setEndValue(self._target(i))
            self._anim.start()
        else:
            self.indicator.setGeometry(self._target(i))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._anim.state() != QPropertyAnimation.Running:
            self.indicator.setGeometry(self._target(self._current))

    def showEvent(self, e):
        super().showEvent(e)
        self.indicator.setGeometry(self._target(self._current))


class Logo(QWidget):
    """Gradyanlı "E" rozeti + EDIFI'CE + GREEN PROPTECH."""

    def __init__(self):
        super().__init__()
        self.setObjectName("sidehead")
        self.setFixedHeight(70)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        badge_r = QRectF(18, 19, 32, 32)
        glow = QPainterPath()
        glow.addRoundedRect(badge_r.adjusted(-3, -3, 3, 3), 12, 12)
        p.fillPath(glow, rgba(G, 0.10))
        path = QPainterPath()
        path.addRoundedRect(badge_r, 9, 9)
        g = QLinearGradient(badge_r.topLeft(), badge_r.bottomRight())
        g.setColorAt(0, QColor(G))
        g.setColorAt(1, QColor(INDIGO))
        p.fillPath(path, QBrush(g))
        p.setPen(QColor("#050A0E"))
        p.setFont(qfont(15, QFont.Black))
        p.drawText(badge_r, Qt.AlignCenter, "E")
        p.setPen(QColor(TEXT))
        p.setFont(qfont(14, QFont.ExtraBold, spacing=-0.3))
        p.drawText(QPointF(60, 33), "EDIFI'CE")
        p.setPen(QColor(G))
        p.setFont(qfont(8, QFont.Bold, spacing=1.3))
        p.drawText(QPointF(60, 46), "GREEN PROPTECH")


def get_style() -> str:
    """Stil sayfası; açılır kutu oku için geçici bir ok ikonu üretir (QApplication gerekir)."""
    import tempfile
    from pathlib import Path
    path = Path(tempfile.gettempdir()) / "edifice_chevron.png"
    pm = QPixmap(24, 24)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(SUB), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPolyline([QPointF(6, 9), QPointF(12, 15), QPointF(18, 9)])
    p.end()
    pm.save(str(path))
    return STYLE_TEMPLATE.replace("__ARROW__", str(path).replace("\\", "/"))


STYLE = STYLE_TEMPLATE
