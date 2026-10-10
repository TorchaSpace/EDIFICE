"""Adres arama (otomatik tamamlama): Photon (OpenStreetMap verisi, anahtarsız). Ağ yoksa sessizce boş döner."""
from __future__ import annotations

import json

from PySide6.QtCore import QEventLoop, QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

URL = "https://photon.komoot.io/api/?q={q}&limit=6&lang=en"


def _label(props: dict) -> str:
    parts = []
    for key in ("name", "street", "district", "city", "state", "country"):
        v = props.get(key)
        if v and v not in parts:
            parts.append(v)
    return ", ".join(parts)


def parse(data: bytes) -> list[tuple[str, float, float]]:
    try:
        feats = json.loads(data.decode("utf-8")).get("features", [])
    except (ValueError, AttributeError):
        return []
    out, seen = [], set()
    for f in feats:
        lon, lat = f["geometry"]["coordinates"][:2]
        label = _label(f.get("properties", {}))
        if label and label not in seen:
            seen.add(label)
            out.append((label, float(lat), float(lon)))
    return out


class Geocoder(QObject):
    """Yazarken arar: her istek 350 ms bekletilir, eski yanıtlar atılır."""
    results = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._net = QNetworkAccessManager(self)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(350)
        self._timer.timeout.connect(self._go)
        self._q = ""
        self._seq = 0

    def search(self, text: str):
        self._q = text.strip()
        if len(self._q) < 3:
            self._timer.stop()
            return
        self._timer.start()

    def _go(self):
        from urllib.parse import quote
        self._seq += 1
        seq = self._seq
        req = QNetworkRequest(QUrl(URL.format(q=quote(self._q))))
        req.setRawHeader(b"User-Agent", b"EDIFICE-desktop/1.0 (building dashboard)")
        reply = self._net.get(req)

        def done():
            if seq == self._seq and reply.error() == reply.NetworkError.NoError:
                self.results.emit(parse(reply.readAll().data()))
            reply.deleteLater()
        reply.finished.connect(done)


def lookup_first(text: str, timeout_ms: int = 4000) -> tuple[float, float] | None:
    """Kaydederken konum yoksa adresi bir kez çözer (en fazla timeout_ms bekler)."""
    from urllib.parse import quote
    net = QNetworkAccessManager()
    req = QNetworkRequest(QUrl(URL.format(q=quote(text.strip()))))
    req.setRawHeader(b"User-Agent", b"EDIFICE-desktop/1.0 (building dashboard)")
    reply = net.get(req)
    loop = QEventLoop()
    reply.finished.connect(loop.quit)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    res = parse(reply.readAll().data()) if reply.isFinished() and reply.error() == reply.NetworkError.NoError else []
    reply.abort()
    reply.deleteLater()
    return (res[0][1], res[0][2]) if res else None
