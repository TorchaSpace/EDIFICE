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


from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QPropertyAnimation, QRect  # noqa: E402
from PySide6.QtWidgets import QAbstractItemView, QFrame, QTableWidget  # noqa: E402


class PillTable(QTableWidget):
    """Seçili satırı sistem vurgusu yerine yuvarlak, yeşil bir 'hap' ile gösterir.
    Satır değişince hap, eski satırdan yenisine yumuşakça kayar. Hücre widget'larına odaklanmak satırı seçer."""

    def __init__(self, rows: int, cols: int):
        super().__init__(rows, cols)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self._row = -1
        self._pill = QFrame(self.viewport())
        self._pill.setObjectName("rowPill")
        self._pill.hide()
        self._pill.lower()
        self._anim = QPropertyAnimation(self._pill, b"geometry", self)
        self._anim.setDuration(380)
        self._anim.setEasingCurve(QEasingCurve.OutQuart)
        self.viewport().installEventFilter(self)
        self.verticalScrollBar().valueChanged.connect(lambda _: self._sync(False))

    # ---- genel arayüz
    def selected_row(self) -> int:
        return self._row

    def attach_widget(self, w: QWidget):
        """Hücre içeriğindeki tüm widget'lara odak izleme ekler."""
        for child in [w, *w.findChildren(QWidget)]:
            child.installEventFilter(self)

    def select_row(self, row: int, animate: bool = True):
        self._row = row if 0 <= row < self.rowCount() else -1
        self._sync(animate)

    def refresh_selection(self):
        if self._row >= self.rowCount():
            self._row = self.rowCount() - 1
        self._sync(False)

    # ---- iç
    def _target(self, r: int) -> QRect:
        return QRect(4, self.rowViewportPosition(r) + 3, self.viewport().width() - 8, self.rowHeight(r) - 6)

    def _sync(self, animate: bool):
        if self._row < 0 or self.rowCount() == 0 or not self.isVisible():
            self._pill.hide()
            return
        rect = self._target(self._row)
        self._anim.stop()
        if animate and self._pill.isVisible():
            self._anim.setStartValue(self._pill.geometry())
            self._anim.setEndValue(rect)
            self._anim.start()
        else:
            self._pill.setGeometry(rect)
            self._pill.show()
        self._pill.lower()

    def _row_of(self, w: QWidget) -> int:
        while w is not None and w.parentWidget() is not self.viewport():
            w = w.parentWidget()
        if w is None:
            return -1
        return self.rowAt(w.y() + w.height() // 2)

    def eventFilter(self, obj, ev):
        t = ev.type()
        if obj is self.viewport():
            if t == QEvent.Resize:
                self._sync(False)
            elif t == QEvent.MouseButtonPress:
                r = self.rowAt(int(ev.position().y()))
                if r >= 0:
                    self.select_row(r)
        elif t in (QEvent.FocusIn, QEvent.MouseButtonPress):
            r = self._row_of(obj)
            if r >= 0 and r != self._row:
                self.select_row(r)
        return super().eventFilter(obj, ev)

    def showEvent(self, e):
        super().showEvent(e)
        self._sync(False)
