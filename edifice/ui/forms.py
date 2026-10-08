"""Form yardımcıları (Bina Ekle ve Ayarlar ekranlarında ortak)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget


def field(label: str, widget: QWidget, hint: str = "") -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(7)
    lb = QLabel(label)
    lb.setObjectName("field")
    lay.addWidget(lb)
    lay.addWidget(widget)
    if hint:
        h = QLabel(hint)
        h.setObjectName("hint")
        h.setWordWrap(True)
        lay.addWidget(h)
    lay.addStretch()
    return w


def tune_spin(sp):
    """Spin kutularında metnin kenara yapışmasını önler."""
    sp.lineEdit().setTextMargins(10, 0, 0, 0)
    sp.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    sp.setMinimumHeight(40)
    return sp


def scroll(inner: QWidget) -> QScrollArea:
    """İçerik doğal boyutunda kalır; sığmazsa yumuşakça kayar (alanlar asla birbirine girmez)."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    area.setWidget(inner)
    area.viewport().setAutoFillBackground(False)
    inner.setAutoFillBackground(False)
    return area
