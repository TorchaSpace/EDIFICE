"""Bina ekleme yöntemi seçimi: formu doldur ya da Excel şablonuyla yükle."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog, QFileDialog, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                               QPushButton, QVBoxLayout, QWidget)

from ..excel_io import build_template
from .widgets import G, RED, header, muted


def _card(title: str, text: str) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(26, 24, 26, 24)
    lay.setSpacing(10)
    t = QLabel(title)
    t.setObjectName("title")
    lay.addWidget(t)
    d = muted(text)
    lay.addWidget(d)
    return card, lay


class AddChoiceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bina Ekle")
        self.setMinimumWidth(860)
        self.choice: str | None = None
        self.path: str | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 30, 36, 28)
        lay.setSpacing(18)
        lay.addWidget(header("Yeni bina", "Binayı nasıl eklemek istersiniz?",
                             "Verileri uygulamada doldurabilir ya da hazır Excel şablonunu doldurup yükleyebilirsiniz."))
        row = QHBoxLayout()
        row.setSpacing(18)

        form, fl = _card("Uygulamada doldur",
                         "Adım adım form: bina bilgisi, 12 aylık tüketim ve ekipmanlar. Excel'den kopyalayıp yapıştırabilirsiniz.")
        fl.addStretch()
        b = QPushButton("Formu aç")
        b.setObjectName("primary")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda: self._done("form"))
        fl.addWidget(b)
        row.addWidget(form, 1)

        xl, xl_lay = _card("Excel ile yükle",
                           "1) Şablonu indirin   2) Doldurun   3) Dosyayı seçin. Yüklemeden önce verileri gözden geçirip "
                           "düzeltebilirsiniz.")
        xl_lay.addStretch()
        r1 = QHBoxLayout()
        r1.setSpacing(10)
        for text, example in (("↓ Boş şablon", False), ("↓ Örnek dolu dosya", True)):
            btn = QPushButton(text)
            btn.setObjectName("secondary")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, ex=example: self.download(ex))
            r1.addWidget(btn)
        xl_lay.addLayout(r1)
        pick = QPushButton("Doldurduğum Excel dosyasını seç…")
        pick.setObjectName("primary")
        pick.setCursor(Qt.PointingHandCursor)
        pick.clicked.connect(self.pick_file)
        xl_lay.addWidget(pick)
        row.addWidget(xl, 1)
        lay.addLayout(row)

        self.note = QLabel("")
        self.note.setStyleSheet(f"color: {G}; font-size: 13px; font-weight: 600; background: transparent;")
        self._fx = QGraphicsOpacityEffect(self.note)
        self.note.setGraphicsEffect(self._fx)
        self._fx.setOpacity(0.0)
        self._anim = QPropertyAnimation(self._fx, b"opacity", self)
        self._anim.setEasingCurve(QEasingCurve.OutQuart)
        lay.addWidget(self.note)
        cancel = QPushButton("Vazgeç")
        cancel.setObjectName("secondary")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        bar = QHBoxLayout()
        bar.addStretch()
        bar.addWidget(cancel)
        lay.addLayout(bar)

    def _toast(self, text: str, color: str = G):
        self.note.setText(text)
        self.note.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 600; background: transparent;")
        self._anim.stop()
        self._anim.setDuration(350)
        self._anim.setStartValue(self._fx.opacity())
        self._anim.setEndValue(1.0)
        self._anim.start()

    def _done(self, choice: str, path: str | None = None):
        self.choice, self.path = choice, path
        self.accept()

    def download(self, example: bool):
        name = "EDIFICE_Ornek_Bina.xlsx" if example else "EDIFICE_Bina_Sablonu.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "Excel şablonunu kaydet", name, "Excel (*.xlsx)")
        if not path:
            return
        try:
            build_template(path, example=example)
        except OSError as e:
            self._toast(f"Kaydedilemedi: {e.strerror or e}", RED)
            return
        self._toast("Kaydedildi. Dosya açılıyor; doldurup kaydedin, sonra buradan seçin.")
        QTimer.singleShot(400, lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(path)))

    def pick_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Doldurulmuş Excel dosyasını seç", "", "Excel (*.xlsx)")
        if path:
            self._done("excel", path)
