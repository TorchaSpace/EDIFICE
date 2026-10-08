"""EDIFI'CE uygulama ikonu (1024px PNG): lacivert zemin üzerinde logonun anahtar+bina amblemi."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath,
                           QRadialGradient)

app = QGuiApplication(sys.argv)
out = sys.argv[1]
emblem = QImage(str(Path(__file__).resolve().parent.parent / "edifice" / "assets" / "logo_emblem_white.png"))
S = 1024
img = QImage(S, S, QImage.Format_ARGB32)
img.fill(Qt.transparent)
p = QPainter(img)
p.setRenderHint(QPainter.Antialiasing)
p.setRenderHint(QPainter.SmoothPixmapTransform)
rect = QRectF(40, 40, S - 80, S - 80)
path = QPainterPath()
path.addRoundedRect(rect, 220, 220)
bg = QLinearGradient(rect.topLeft(), rect.bottomRight())
bg.setColorAt(0, QColor("#1747B8"))
bg.setColorAt(1, QColor("#071A52"))
p.fillPath(path, QBrush(bg))
glow = QRadialGradient(rect.center().x(), rect.top() + 160, 620)
glow.setColorAt(0, QColor(255, 255, 255, 46))
glow.setColorAt(1, QColor(255, 255, 255, 0))
p.fillPath(path, QBrush(glow))
w = S * 0.56
h = w * emblem.height() / emblem.width()
p.drawImage(QRectF((S - w) / 2, (S - h) / 2 - 10, w, h), emblem)
bar = QRectF(S / 2 - 90, (S + h) / 2 + 40, 180, 14)   # yeşil vurgu çizgisi
bp = QPainterPath()
bp.addRoundedRect(bar, 7, 7)
p.fillPath(bp, QColor("#0DDD96"))
p.end()
img.save(out)
