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


from PySide6.QtCore import (QEasingCurve, QEvent, QParallelAnimationGroup, QPoint, QPropertyAnimation,  # noqa: E402
                            QRect, QTimer)
from PySide6.QtWidgets import QAbstractItemView, QFrame, QGraphicsOpacityEffect, QTableWidget  # noqa: E402


from PySide6.QtCore import Signal  # noqa: E402


class PillTable(QTableWidget):
    """Seçili satırı sistem vurgusu yerine yuvarlak, yeşil bir 'hap' ile gösterir.
    Satır değişince hap, eski satırdan yenisine yumuşakça kayar. Hücre widget'larına odaklanmak satırı seçer."""

    removed = Signal()

    def __init__(self, rows: int, cols: int):
        super().__init__(rows, cols)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self._busy = False
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

    def remove_row_animated(self, r: int):
        """Satır önce solar, sonra alttaki satırlar (ve hap) yumuşakça yukarı kayar."""
        if getattr(self, "_busy", False) or not 0 <= r < self.rowCount():
            return
        self._busy = True
        fade = QParallelAnimationGroup(self)
        for c in range(self.columnCount()):
            w = self.cellWidget(r, c)
            eff = QGraphicsOpacityEffect(w)
            w.setGraphicsEffect(eff)
            a = QPropertyAnimation(eff, b"opacity", w)
            a.setDuration(220)
            a.setStartValue(1.0)
            a.setEndValue(0.0)
            a.setEasingCurve(QEasingCurve.OutQuad)
            fade.addAnimation(a)
        fade.finished.connect(lambda: self._finish_remove(r))
        fade.start()
        self._fade_group = fade
        self._pill.hide() if self.rowCount() == 1 else None

    def _finish_remove(self, r: int):
        n, cols = self.rowCount(), self.columnCount()
        moving = []   # (widget, başlangıç noktası)
        for j in range(r + 1, n):
            for c in range(cols):
                w = self.cellWidget(j, c)
                moving.append((j - 1, c, w.pos()))
        pill_start = self._target(r + 1) if r + 1 < n else self._pill.geometry()
        self.removeRow(r)
        self.doItemsLayout()
        group = QParallelAnimationGroup(self)
        for j, c, start in moving:
            w = self.cellWidget(j, c)
            if w is None:
                continue
            end = w.pos()
            w.move(start)
            a = QPropertyAnimation(w, b"pos", w)
            a.setDuration(380)
            a.setStartValue(start)
            a.setEndValue(end)
            a.setEasingCurve(QEasingCurve.OutQuart)
            group.addAnimation(a)
        self._row = r if r < self.rowCount() else self.rowCount() - 1
        if self._row >= 0:
            self._pill.setGeometry(pill_start)
            self._pill.show()
            self._pill.lower()
            pa = QPropertyAnimation(self._pill, b"geometry", self)
            pa.setDuration(380)
            pa.setStartValue(pill_start)
            pa.setEndValue(self._target(self._row))
            pa.setEasingCurve(QEasingCurve.OutQuart)
            group.addAnimation(pa)
        else:
            self._pill.hide()
        group.finished.connect(self._remove_done)
        group.start()
        self._slide_group = group

    def _remove_done(self):
        self._busy = False
        self._sync(False)
        self.removed.emit()

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



class SmoothSelectTable(QTableWidget):
    """Seçili hücre/satır bölgesini sistem vurgusu yerine yuvarlak köşeli, yumuşakça beliren,
    seçim değişince şekil/konum değiştiren bir panelle gösterir."""

    def __init__(self, *args):
        super().__init__(*args)
        self.setObjectName("smoothSel")
        self._pills: list[QFrame] = []
        self.itemSelectionChanged.connect(lambda: self._sync(True))
        self.verticalScrollBar().valueChanged.connect(lambda _: self._sync(False))
        self.viewport().installEventFilter(self)

    def _rects(self) -> list[QRect]:
        out = []
        for r in self.selectedRanges():
            tl = self.visualRect(self.model().index(r.topRow(), r.leftColumn()))
            br = self.visualRect(self.model().index(r.bottomRow(), r.rightColumn()))
            out.append(tl.united(br).adjusted(2, 2, -2, -2))
        return out

    def _new_pill(self) -> QFrame:
        p = QFrame(self.viewport())
        p.setObjectName("selPill")
        p.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        p._fx = QGraphicsOpacityEffect(p)
        p._fx.setOpacity(0.0)
        p.setGraphicsEffect(p._fx)
        p._fade = QPropertyAnimation(p._fx, b"opacity", p)
        p._fade.setEasingCurve(QEasingCurve.OutQuart)
        p._fade.finished.connect(lambda p=p: p.hide() if p._fx.opacity() < 0.01 else None)
        p._geo = QPropertyAnimation(p, b"geometry", p)
        p._geo.setEasingCurve(QEasingCurve.OutQuart)
        p.hide()
        return p

    def _fade_to(self, p: QFrame, end: float, ms: int):
        p._fade.stop()
        p._fade.setDuration(ms)
        p._fade.setStartValue(p._fx.opacity())
        p._fade.setEndValue(end)
        p._fade.start()

    def _sync(self, animate: bool):
        rects = self._rects()
        while len(self._pills) < len(rects):
            self._pills.append(self._new_pill())
        for i, p in enumerate(self._pills):
            if i < len(rects):
                rect = rects[i]
                p._geo.stop()
                if not p.isVisible() or p._fx.opacity() < 0.05:
                    p.setGeometry(rect)
                    p.show()
                    self._fade_to(p, 1.0, 260)
                elif animate:
                    p._geo.setDuration(180)
                    p._geo.setStartValue(p.geometry())
                    p._geo.setEndValue(rect)
                    p._geo.start()
                    self._fade_to(p, 1.0, 120)
                else:
                    p.setGeometry(rect)
            elif p.isVisible():
                self._fade_to(p, 0.0, 200)

    def eventFilter(self, obj, ev):
        if obj is self.viewport() and ev.type() == QEvent.Resize:
            self._sync(False)
        return super().eventFilter(obj, ev)
