"""Yer arama (otomatik tamamlama): Photon (OpenStreetMap verisi, anahtarsız). Ağ yoksa sessizce boş döner."""
from __future__ import annotations

import json
from urllib.parse import quote

from PySide6.QtCore import QEventLoop, QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

BASE = "https://photon.komoot.io/api/?q={q}&limit={limit}&lang=default"
UA = b"EDIFICE-desktop/1.0 (building dashboard)"


def _url(q: str, layers=(), limit: int = 12, near: tuple[float, float] | None = None) -> str:
    u = BASE.format(q=quote(q.strip()), limit=limit)
    for layer in layers:
        u += f"&layer={layer}"
    if near:
        u += f"&lat={near[0]}&lon={near[1]}"
    return u


def parse(data: bytes) -> list[dict]:
    """Yer sonuçları: name, state (il), country (ülke), lat, lon, type."""
    try:
        feats = json.loads(data.decode("utf-8")).get("features", [])
    except (ValueError, AttributeError):
        return []
    out = []
    for f in feats:
        p = f.get("properties", {})
        lon, lat = f["geometry"]["coordinates"][:2]
        if p.get("name"):
            out.append({"name": p["name"], "state": p.get("state") or "", "city": p.get("city") or "",
                        "country": p.get("country") or "", "type": p.get("type") or "",
                        "street": p.get("street") or "", "district": p.get("district") or "",
                        "housenumber": p.get("housenumber") or "", "lat": float(lat), "lon": float(lon)})
    return out


class Geocoder(QObject):
    """Yazarken arar: istek 350 ms bekletilir, eski yanıtlar atılır."""
    results = Signal(list)

    def __init__(self, layers=(), parent=None):
        super().__init__(parent)
        self.layers = tuple(layers)
        self._net = QNetworkAccessManager(self)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(350)
        self._timer.timeout.connect(self._go)
        self._q, self._near, self._seq = "", None, 0

    def search(self, text: str, near: tuple[float, float] | None = None):
        self._q, self._near = text.strip(), near
        if len(self._q) < 2:
            self._timer.stop()
            return
        self._timer.start()

    def _go(self):
        self._seq += 1
        seq = self._seq
        req = QNetworkRequest(QUrl(_url(self._q, self.layers, 15, self._near)))
        req.setRawHeader(b"User-Agent", UA)
        reply = self._net.get(req)

        def done():
            if seq == self._seq and reply.error() == reply.NetworkError.NoError:
                self.results.emit(parse(reply.readAll().data()))
            reply.deleteLater()
        reply.finished.connect(done)


def lookup_first(text: str, timeout_ms: int = 4000) -> tuple[float, float] | None:
    """Kaydederken konum yoksa adresi bir kez çözer (en fazla timeout_ms bekler)."""
    net = QNetworkAccessManager()
    req = QNetworkRequest(QUrl(_url(text, (), 1)))
    req.setRawHeader(b"User-Agent", UA)
    reply = net.get(req)
    loop = QEventLoop()
    reply.finished.connect(loop.quit)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    res = parse(reply.readAll().data()) if reply.isFinished() and reply.error() == reply.NetworkError.NoError else []
    reply.abort()
    reply.deleteLater()
    return (res[0]["lat"], res[0]["lon"]) if res else None
