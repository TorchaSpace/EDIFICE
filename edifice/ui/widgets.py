from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

ACCENT = "#1f7a5c"
GRADE_COLORS = {"A": "#1f9d55", "B": "#7cb342", "C": "#f2c200", "D": "#f08a00", "E": "#d64545"}

STYLE = f"""
QWidget#side {{ background: #17352b; }}
QMainWindow, QWidget#page {{ background: #f4f6f5; }}
QListWidget#nav {{ background: #17352b; color: #cfe5dc; border: none; font-size: 14px; outline: 0; }}
QListWidget#nav::item {{ padding: 14px 18px; }}
QListWidget#nav::item:selected {{ background: {ACCENT}; color: white; }}
QFrame#card {{ background: white; border: 1px solid #dde3e0; border-radius: 10px; }}
QLabel#cardTitle {{ color: #6b7a74; font-size: 12px; }}
QLabel#cardValue {{ color: #17352b; font-size: 26px; font-weight: 600; }}
QLabel#cardSub {{ color: #6b7a74; font-size: 12px; }}
QLabel#h1 {{ font-size: 22px; font-weight: 600; color: #17352b; }}
QLabel#muted {{ color: #6b7a74; }}
QPushButton {{ background: {ACCENT}; color: white; border: none; padding: 8px 16px; border-radius: 6px; }}
QPushButton:hover {{ background: #17634a; }}
QTableWidget {{ background: white; border: 1px solid #dde3e0; gridline-color: #eef1ef; }}
QHeaderView::section {{ background: #eef3f0; border: none; padding: 6px; font-weight: 600; }}
"""


class Card(QFrame):
    """Başlık, büyük değer ve alt metin gösteren KPI kartı."""

    def __init__(self, title: str, value: str = "-", sub: str = ""):
        super().__init__()
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        self._t, self._v, self._s = QLabel(title), QLabel(value), QLabel(sub)
        self._t.setObjectName("cardTitle")
        self._v.setObjectName("cardValue")
        self._s.setObjectName("cardSub")
        for w in (self._t, self._v, self._s):
            lay.addWidget(w)

    def set(self, value: str, sub: str = "", color: str | None = None):
        self._v.setText(value)
        self._s.setText(sub)
        self._v.setStyleSheet(f"color: {color};" if color else "")


def h1(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("h1")
    return lbl


def muted(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("muted")
    lbl.setWordWrap(True)
    return lbl


def fmt(n: float, digits: int = 0) -> str:
    s = f"{n:,.{digits}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_years(y: float) -> str:
    return "-" if y == float("inf") else f"{fmt(y, 1)} yıl"
