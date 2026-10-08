"""Premium açılır menü: yuvarlak kart, gölge, aşağı doğru genişleyen + fade animasyonlu."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
                               QLabel, QPushButton, QVBoxLayout, QWidget)


class _Item(QPushButton):
    def __init__(self, text: str, selected: bool):
        super().__init__()
        self.setObjectName("ddItem")
        self.setCheckable(True)
        self.setChecked(selected)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(40)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 14, 0)
        label = QLabel(text)
        label.setObjectName("ddText")
        label.setStyleSheet(f"color: {'#0DDD96' if selected else '#E8F2FF'}; font-size: 13px; background: transparent;"
                            + (" font-weight: 700;" if selected else ""))
        check = QLabel("✓" if selected else "")
        check.setObjectName("ddCheck")
        for w in (label, check):
            w.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        lay.addWidget(label, 1)
        lay.addWidget(check)


class _Popup(QWidget):
    def __init__(self, combo: "PremiumCombo"):
        super().__init__(combo.window(), Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.combo = combo
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 4, 16, 24)
        self.card = QFrame()
        self.card.setObjectName("ddCard")
        fx = QGraphicsDropShadowEffect(self.card)
        fx.setBlurRadius(36)
        fx.setOffset(0, 10)
        fx.setColor(QColor(0, 0, 0, 170))
        self.card.setGraphicsEffect(fx)
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(2)
        for i in range(combo.count()):
            it = _Item(combo.itemText(i), i == combo.currentIndex())
            it.clicked.connect(lambda _=False, idx=i: self._pick(idx))
            lay.addWidget(it)
        outer.addWidget(self.card, 0, Qt.AlignTop)
        self._full = self.card.sizeHint().height()
        self._closing = False

    def open(self):
        w = self.combo.width() + 32
        self.setFixedSize(w, self._full + 28)
        g = self.combo.mapToGlobal(QPoint(0, self.combo.height()))
        screen = QApplication.screenAt(g) or QApplication.primaryScreen()
        y = g.y() - 2
        bottom = screen.availableGeometry().bottom()
        if y + self.height() > bottom:
            y = max(screen.availableGeometry().top(), bottom - self.height())
        self.move(g.x() - 16, y)
        self.card.setMaximumHeight(0)
        self.setWindowOpacity(0.0)
        self.show()
        self._grow = QPropertyAnimation(self.card, b"maximumHeight", self)
        self._grow.setDuration(320)
        self._grow.setStartValue(0)
        self._grow.setEndValue(self._full)
        self._grow.setEasingCurve(QEasingCurve.OutQuart)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(220)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._grow.start()
        self._fade.start()

    def _pick(self, idx: int):
        self.combo.setCurrentIndex(idx)
        self.combo.activated.emit(idx)
        self._close_animated()

    def _close_animated(self):
        if self._closing:
            return
        self._closing = True
        out = QPropertyAnimation(self, b"windowOpacity", self)
        out.setDuration(140)
        out.setStartValue(self.windowOpacity())
        out.setEndValue(0.0)
        out.finished.connect(self.close)
        out.start()
        self._out = out


class PremiumCombo(QComboBox):
    """Sistem listesi yerine özel, animasyonlu açılır menü kullanan QComboBox."""

    def showPopup(self):
        if self.count() == 0:
            return
        self._popup = _Popup(self)
        self._popup.open()

    def hidePopup(self):
        pass
