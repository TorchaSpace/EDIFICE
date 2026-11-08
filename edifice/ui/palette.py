"""Komut paleti (Ctrl+K) ve klavye kısayolları penceresi.

Uygulamada 10 sayfa ve 20'den fazla sekme var; kullanıcı bir yerin adını yazıp Enter'a basarak oraya gidebilsin,
binalar arasında geçebilsin ve sık eylemleri (rapor, bina ekle, içe aktar) menü aramadan çalıştırabilsin.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from PySide6.QtCore import QEvent, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QDialog, QFrame, QGraphicsDropShadowEffect, QGridLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPushButton, QStyle, QStyledItemDelegate, QVBoxLayout)

from .widgets import BORDER, DIM, G, G_SOFT, MUTED, SUB, SURFACE, TEXT, qfont

_TR = str.maketrans({"ı": "i", "İ": "i", "I": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g", "ü": "u", "Ü": "u",
                     "ö": "o", "Ö": "o", "ç": "c", "Ç": "c", "â": "a", "î": "i", "û": "u"})


def norm(text: str) -> str:
    """Türkçe karakterlerden ve büyük/küçük harften bağımsız arama ("gunes" → "Güneş", "isik" → "Işık")."""
    return text.translate(_TR).casefold()


@dataclass
class Command:
    title: str
    group: str                       # "Sayfa", "Bina", "Eylem"
    run: Callable[[], None]
    keywords: str = ""
    shortcut: str = ""
    _hay: str = field(default="", repr=False)

    def __post_init__(self):
        self._hay = norm(f"{self.title} {self.group} {self.keywords}")


def rank(commands: list[Command], query: str) -> list[Command]:
    """Tüm kelimeleri içerenler; başlığı sorguyla başlayanlar ve kelime başı eşleşmeler öne."""
    q = norm(query).split()
    if not q:
        return list(commands)
    scored = []
    for i, c in enumerate(commands):
        if not all(t in c._hay for t in q):
            continue
        t = norm(c.title)
        score = 0
        if t.startswith(q[0]):
            score -= 100
        score -= sum(10 for tok in q if f" {tok}" in f" {t}")
        score -= sum(3 for tok in q if tok in t)
        scored.append((score, i, c))
    return [c for _, _, c in sorted(scored, key=lambda x: (x[0], x[1]))]


class _Delegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 40)

    def paint(self, p: QPainter, option, index):
        cmd: Command = index.data(Qt.UserRole)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(option.rect).adjusted(4, 2, -4, -2)
        sel = bool(option.state & QStyle.State_Selected)
        if sel:
            p.setPen(QColor(13, 221, 150, 70))
            p.setBrush(QColor(13, 221, 150, 26))
            p.drawRoundedRect(r, 10, 10)
        elif option.state & QStyle.State_MouseOver:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 10))
            p.drawRoundedRect(r, 10, 10)
        p.setFont(qfont(13, 700 if sel else 500))
        p.setPen(QColor(G if sel else TEXT))
        text_r = r.adjusted(14, 0, -150, 0)
        p.drawText(text_r, Qt.AlignVCenter | Qt.AlignLeft, p.fontMetrics().elidedText(cmd.title, Qt.ElideRight, int(text_r.width())))
        right = cmd.shortcut or cmd.group
        p.setFont(qfont(11, 600, mono=bool(cmd.shortcut)))
        p.setPen(QColor(MUTED if cmd.shortcut else DIM))
        p.drawText(r.adjusted(0, 0, -14, 0), Qt.AlignVCenter | Qt.AlignRight, right)
        p.restore()


class CommandPalette(QDialog):
    """Ctrl+K: yaz, ok tuşlarıyla seç, Enter ile git. Esc kapatır."""

    def __init__(self, parent, commands: list[Command], placeholder: str = "Sayfa, sekme, bina ya da eylem ara…"):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.commands = commands
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        card = QFrame()
        card.setObjectName("ddCard")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 160))
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 10, 10, 8)
        lay.setSpacing(6)
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.setStyleSheet(f"QLineEdit {{ background: transparent; border: none; border-bottom: 1px solid {BORDER};"
                                 "border-radius: 0; padding: 10px 8px 12px 8px; font-size: 15px; }")
        self.input.textChanged.connect(self._filter)
        self.input.installEventFilter(self)
        lay.addWidget(self.input)
        self.list = QListWidget()
        self.list.setItemDelegate(_Delegate(self.list))
        self.list.setMouseTracking(True)
        self.list.setUniformItemSizes(True)
        self.list.setFocusPolicy(Qt.NoFocus)
        self.list.setStyleSheet("QListWidget { background: transparent; border: none; outline: 0; }")
        self.list.itemClicked.connect(lambda it: self._run(it))
        lay.addWidget(self.list, 1)
        self.empty = QLabel("Eşleşen bir şey yok. Başka bir kelime deneyin.")
        self.empty.setStyleSheet(f"color: {SUB}; font-size: 13px; padding: 14px;")
        self.empty.hide()
        lay.addWidget(self.empty)
        hint = QLabel("↑↓ seç   ·   Enter aç   ·   Esc kapat")
        hint.setStyleSheet(f"color: {DIM}; font-size: 11px; padding: 2px 8px;")
        lay.addWidget(hint)
        self._filter("")
        w = min(640, max(480, parent.width() - 200))
        self.setFixedWidth(w)
        self.adjustSize()
        top = parent.mapToGlobal(parent.rect().topLeft())
        self.move(top.x() + (parent.width() - w) // 2, top.y() + 70)
        self.input.setFocus()

    def _filter(self, text: str):
        self.list.clear()
        found = rank(self.commands, text)[:60]
        for c in found:
            it = QListWidgetItem(c.title)
            it.setData(Qt.UserRole, c)
            self.list.addItem(it)
        if found:
            self.list.setCurrentRow(0)
        self.list.setVisible(bool(found))
        self.empty.setVisible(not found)
        self.list.setFixedHeight(min(len(found), 9) * 40 + 6)      # pencere sonuç sayısına göre büyüyüp küçülür
        if self.isVisible():
            self.adjustSize()

    def eventFilter(self, obj, e):
        if obj is self.input and e.type() == QEvent.KeyPress:
            k = e.key()
            n = self.list.count()
            if k in (Qt.Key_Down, Qt.Key_Up, Qt.Key_PageDown, Qt.Key_PageUp) and n:
                step = {Qt.Key_Down: 1, Qt.Key_Up: -1, Qt.Key_PageDown: 8, Qt.Key_PageUp: -8}[k]
                row = self.list.currentRow() + step
                self.list.setCurrentRow(row % n if abs(step) == 1 else max(0, min(n - 1, row)))
                return True
            if k in (Qt.Key_Return, Qt.Key_Enter):
                if self.list.currentItem() is not None:
                    self._run(self.list.currentItem())
                return True
            if k == Qt.Key_Escape:
                self.reject()
                return True
        return super().eventFilter(obj, e)

    def _run(self, item):
        cmd: Command = item.data(Qt.UserRole)
        self.accept()
        cmd.run()


# (kısayol dizileri, açıklama). Diziler işletim sisteminin gösterimiyle yazılır (macOS'ta Ctrl → ⌘).
SHORTCUTS = [
    (["Ctrl+K"], "Komut paleti: sayfa, sekme, bina ya da eylem ara"),
    (["Ctrl+1", "Ctrl+0"], "Kenar menüdeki sayfalara git (1 … 0)"),
    (["Ctrl+PgDown", "Ctrl+PgUp"], "Sonraki / önceki sekme"),
    (["Alt+Left", "Alt+Right"], "Geri / ileri (son gezilen sayfalar)"),
    (["Ctrl+F"], "Bina ara"),
    (["Ctrl+N"], "Yeni bina ekle"),
    (["Ctrl+E"], "Bu binayı düzenle"),
    (["Ctrl+B"], "Bina menüsü (değiştir, içe aktar, düzenle)"),
    (["Ctrl+I"], "Tüketimi içe aktar (CSV / Excel)"),
    (["Ctrl+P"], "PDF raporu oluştur"),
    (["F1"], "Bu listeyi göster"),
    (["Esc"], "Aramayı temizle / pencereyi kapat"),
]


class ShortcutsDialog(QDialog):
    def __init__(self, parent, keys: Callable[[str], str] = lambda k: k):
        super().__init__(parent)
        self.setWindowTitle("Klavye kısayolları")
        self.setStyleSheet(f"QDialog {{ background: {SURFACE}; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 20)
        lay.setSpacing(14)
        t = QLabel("Klavye kısayolları")
        t.setObjectName("title")
        lay.addWidget(t)
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(9)
        for r, (seqs, what) in enumerate(SHORTCUTS):
            k = QLabel("  /  ".join(keys(q) for q in seqs))
            k.setStyleSheet(f"font-family: 'DM Mono', Menlo, monospace; color: {G}; background: {G_SOFT};"
                            "border: 1px solid rgba(13,221,150,0.22); border-radius: 7px; padding: 3px 9px; font-size: 12px;")
            d = QLabel(what)
            d.setStyleSheet(f"color: {SUB}; font-size: 13px;")
            grid.addWidget(k, r, 0, Qt.AlignLeft)
            grid.addWidget(d, r, 1)
        lay.addLayout(grid)
        ok = QPushButton("Tamam")
        ok.setObjectName("primary")
        ok.setCursor(Qt.PointingHandCursor)
        ok.clicked.connect(self.accept)
        ok.setDefault(True)
        lay.addWidget(ok, 0, Qt.AlignRight)
