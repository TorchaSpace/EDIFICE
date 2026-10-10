from __future__ import annotations


from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

from .. import weather


class WeatherLoader(QObject):
    """Bina konumunun aylık derece-gününü önbellekten verir; eksikse bir kez indirip önbelleğe yazar. Ağ hatasında eldekini döndürür."""
    done = Signal(object, object, str)      # building_id, derece-gün sözlüğü (ya da None), durum: ok | konum | ağ

    def __init__(self, parent=None):
        super().__init__(parent)
        self._net = QNetworkAccessManager(self)

    def load(self, store, project):
        b, bid = project.building, project.building_id
        if b.lat is None or b.lon is None:
            self.done.emit(bid, None, "konum")
            return
        have = store.load_weather(b.lat, b.lon)
        years = sorted({r.year for r in project.readings})
        if not weather.missing_for(have, years):
            self.done.emit(bid, have, "ok")
            return
        start, end = weather.needed_range(min(years), max(years))
        req = QNetworkRequest(QUrl(weather.request_url(b.lat, b.lon, start, end)))
        req.setRawHeader(b"User-Agent", b"EDIFICE-desktop/1.0 (building dashboard)")
        reply = self._net.get(req)

        def finished():
            daily = weather.parse_daily(bytes(reply.readAll())) if reply.error() == reply.NetworkError.NoError else []
            reply.deleteLater()
            if not daily:
                self.done.emit(bid, have or None, "ağ")
                return
            fresh = weather.monthly_degree_days(daily)
            store.save_weather(b.lat, b.lon, fresh)
            self.done.emit(bid, {**have, **fresh}, "ok")
        reply.finished.connect(finished)
