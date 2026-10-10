"""EDIFI'CE uygulama ikonu (1024px PNG). Tamamen vektör çizim: skor halkası içinde, anahtar sapından yükselen
binalar (logonun amblemi). Halka = dashboard/Health Score göstergesi."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath,
                           QPen, QRadialGradient)

app = QGuiApplication(sys.argv)
out = sys.argv[1]
S = 1024
img = QImage(S, S, QImage.Format_ARGB32)
img.fill(Qt.transparent)
p = QPainter(img)
p.setRenderHint(QPainter.Antialiasing)

# ---- zemin: zengin lacivert gradyan, üstten cam parlaması, ince iç çerçeve
tile = QRectF(40, 40, S - 80, S - 80)
tile_path = QPainterPath()
tile_path.addRoundedRect(tile, 228, 228)
bg = QLinearGradient(tile.topLeft(), tile.bottomRight())
bg.setColorAt(0.0, QColor("#2557D6"))
bg.setColorAt(0.55, QColor("#0F2F8F"))
bg.setColorAt(1.0, QColor("#071A52"))
p.fillPath(tile_path, QBrush(bg))
shine = QRadialGradient(tile.center().x() - 80, tile.top() + 40, 720)
shine.setColorAt(0, QColor(255, 255, 255, 70))
shine.setColorAt(0.55, QColor(255, 255, 255, 12))
shine.setColorAt(1, QColor(255, 255, 255, 0))
p.fillPath(tile_path, QBrush(shine))
p.setPen(QPen(QColor(255, 255, 255, 46), 3))
p.setBrush(Qt.NoBrush)
inner = QPainterPath()
inner.addRoundedRect(tile.adjusted(5, 5, -5, -5), 224, 224)
p.drawPath(inner)

# ---- gösterge halkası (Health Score metaforu)
cx, cy, R = S / 2, S / 2 + 6, 330
ring = QRectF(cx - R, cy - R, 2 * R, 2 * R)
p.setPen(QPen(QColor(255, 255, 255, 34), 38, Qt.SolidLine, Qt.RoundCap))
p.drawArc(ring, 225 * 16, -270 * 16)
arc_g = QLinearGradient(ring.left(), ring.bottom(), ring.right(), ring.top())
arc_g.setColorAt(0, QColor(255, 255, 255, 235))
arc_g.setColorAt(1, QColor(190, 214, 255, 235))
p.setPen(QPen(QBrush(arc_g), 38, Qt.SolidLine, Qt.RoundCap))
p.drawArc(ring, 225 * 16, int(-270 * 16 * 0.78))

# ---- amblem (vektör): anahtar başı + sap + dişler, sapın üstünde üç bina
u = 4.7                                     # yerel birim -> piksel
ox, oy = cx - 50 * u, cy - 36 * u - 12      # amblem 100x72 birimlik kutu, halkanın görsel merkezinde


def rr(x, y, w, h, r=1.6):
    path = QPainterPath()
    path.addRoundedRect(QRectF(ox + x * u, oy + y * u, w * u, h * u), r * u, r * u)
    return path


def circ(x, y, r):
    path = QPainterPath()
    path.addEllipse(QPointF(ox + x * u, oy + y * u), r * u, r * u)
    return path


shape = circ(20, 52, 19)
shape = shape.united(rr(34, 46, 64, 12, 3))                     # sap
for tx in (62, 73, 84):                                         # dişler
    shape = shape.united(rr(tx, 54, 6, 11, 1.6))
for x, y, w, h in ((40, 20, 15, 28), (58, 2, 17, 46), (79, 26, 15, 22)):   # binalar
    shape = shape.united(rr(x, y, w, h, 1.8))
shape = shape.subtracted(circ(20, 52, 6.6))                     # anahtar deliği
for x, y, w, h in ((49.5, 24, 1.6, 20), (68.5, 7, 1.8, 36), (88.5, 30, 1.6, 14)):  # bina yarıkları
    shape = shape.subtracted(rr(x, y, w, h, 0.8))

shadow = QPainterPath(shape)
for i, a in enumerate((26, 18, 10)):
    p.save()
    p.translate(0, 10 + i * 7)
    p.fillPath(shadow, QColor(2, 10, 40, a))
    p.restore()
fill = QLinearGradient(ox, oy, ox, oy + 72 * u)
fill.setColorAt(0, QColor("#FFFFFF"))
fill.setColorAt(1, QColor("#C9DBFF"))
p.fillPath(shape, QBrush(fill))
p.end()
img.save(out)
