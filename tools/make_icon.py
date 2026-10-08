"""EDIFI'CE uygulama ikonu (1024px PNG) üretir."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QGuiApplication, QImage, QPainter, QPainterPath

app = QGuiApplication(sys.argv)
out = sys.argv[1]
S = 1024
img = QImage(S, S, QImage.Format_ARGB32)
img.fill(Qt.transparent)
p = QPainter(img)
p.setRenderHint(QPainter.Antialiasing)
path = QPainterPath()
path.addRoundedRect(QRectF(40, 40, S - 80, S - 80), 200, 200)
p.fillPath(path, QBrush(QColor("#17352b")))
p.setBrush(QColor("#1f7a5c"))
p.setPen(Qt.NoPen)
# bina siluetleri
for x, y, w, h in [(230, 380, 190, 420), (440, 250, 200, 550), (660, 460, 140, 340)]:
    p.drawRoundedRect(QRectF(x, y, w, h), 14, 14)
p.setBrush(QColor("#cfe5dc"))
for bx, by, n in [(255, 410, 3), (470, 280, 5), (680, 490, 3)]:
    for i in range(n):
        for j in range(2):
            p.drawRect(QRectF(bx + j * 80 if bx != 680 else bx + j * 55, by + i * 85, 36, 44))
p.setPen(QColor("#cfe5dc"))
f = QFont("Helvetica Neue", 96)
f.setBold(True)
p.setFont(f)
p.drawText(QRectF(0, 810, S, 140), Qt.AlignCenter, "EDIFI'CE")
p.end()
img.save(out)
