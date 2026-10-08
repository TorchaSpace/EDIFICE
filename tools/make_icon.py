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
# amblem (üst) + dashboard göstergesi (alt): "EDIFI'CE dashboard uygulaması" izlenimi
w = S * 0.44
h = w * emblem.height() / emblem.width()
p.drawImage(QRectF((S - w) / 2, 185, w, h), emblem)
panel = QRectF(212, 590, S - 424, 240)
pp = QPainterPath()
pp.addRoundedRect(panel, 44, 44)
p.fillPath(pp, QColor(255, 255, 255, 30))
p.setPen(QColor(255, 255, 255, 60))
p.drawPath(pp)
p.setPen(Qt.NoPen)
heights = [0.30, 0.46, 0.38, 0.62, 0.78, 0.95]
bw, gap = 54, 26
total = len(heights) * bw + (len(heights) - 1) * gap
x0 = panel.center().x() - total / 2
base = panel.bottom() - 34
for i, f in enumerate(heights):
    bh = (panel.height() - 80) * f
    r = QRectF(x0 + i * (bw + gap), base - bh, bw, bh)
    bp = QPainterPath()
    bp.addRoundedRect(r, 14, 14)
    p.fillPath(bp, QColor(255, 255, 255, 120 + int(135 * f)))
p.end()
img.save(out)
