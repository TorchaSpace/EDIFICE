from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import QObject, QUrl, Qt, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .. import weather
from ..engine.outlook import outlook
from .pages import _clear_layout, _fit_height, _page, _set_row, _table, area_chart
from .widgets import AMBER, G, INDIGO, MUTED, Card, Panel, fmt, header, muted


class ClimateLoader(QObject):
    """Anlık durum + 7 gün geçmiş + 7 gün tahmin (Open-Meteo). Başarılı çekim önbelleğe ve günlük gözlem arşivine yazılır; ağ yoksa son çekim döner."""
    done = Signal(object, object, str, object)      # building_id, çözümlenmiş veri | None, durum (ok|konum|ağ|yok), çekim zamanı (ISO) | None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._net = QNetworkAccessManager(self)
        self._busy = False

    def refresh(self, store, project):
        b, bid = project.building, project.building_id
        if b.lat is None or b.lon is None:
            self.done.emit(bid, None, "konum", None)
            return
        cached = store.load_climate(b.lat, b.lon)
        if self._busy:
            return
        self._busy = True
        req = QNetworkRequest(QUrl(weather.forecast_url(b.lat, b.lon)))
        req.setRawHeader(b"User-Agent", b"EDIFICE-desktop/1.0 (building dashboard)")
        reply = self._net.get(req)

        def finished():
            self._busy = False
            data = weather.parse_forecast(bytes(reply.readAll())) if reply.error() == reply.NetworkError.NoError else None
            reply.deleteLater()
            if data is None:
                self.done.emit(bid, cached[0] if cached else None, "ağ" if cached else "yok", cached[1] if cached else None)
                return
            store.save_climate(b.lat, b.lon, data)
            self.done.emit(bid, data, "ok", datetime.now().isoformat(timespec="seconds"))
        reply.finished.connect(finished)


class ClimatePage:
    """Canlı iklim paneli: şu anki durum, 14 günlük sıcaklık, 7 günlük enerji öngörüsü."""

    def __init__(self, project, store, on_refresh):
        self.project, self.store, self.on_refresh = project, store, on_refresh
        self.data = None
        self.status, self.fetched = "yok", None
        self.dd: dict = {}
        self.widget, lay = _page()
        top = QHBoxLayout()
        top.addWidget(header("İklim", "Canlı iklim ve enerji öngörüsü",
                             "Binanın konumundan anlık hava ve 7 günlük tahmin; uygulama açıkken 30 dakikada bir yenilenir. Veri Open-Meteo'dandır (modellenmiş, istasyon ölçümü değil)."), 1)
        self.btn = QPushButton("↻ Şimdi yenile")
        self.btn.setObjectName("export")
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.setMinimumHeight(34)
        self.btn.clicked.connect(self.on_refresh)
        top.addWidget(self.btn, 0, Qt.AlignTop)
        lay.addLayout(top)
        self.stamp = QLabel("")
        self.stamp.setStyleSheet(f"color: {MUTED}; font-size: 12px; background: transparent;")
        lay.addWidget(self.stamp)
        self.body = QVBoxLayout()
        self.body.setSpacing(16)
        lay.addLayout(self.body)
        lay.addStretch()
        self.body.addWidget(muted("İklim verisi yükleniyor…"))

    def set_dd(self, dd: dict):
        self.dd = dd or {}
        self.render()

    def set_data(self, data, status: str, fetched):
        self.data, self.status, self.fetched = data, status, fetched
        self.render()

    def _age(self) -> str:
        if not self.fetched:
            return ""
        mins = max(0, int((datetime.now() - datetime.fromisoformat(self.fetched)).total_seconds() // 60))
        return "az önce" if mins < 2 else f"{mins} dk önce" if mins < 90 else f"{mins // 60} saat önce"

    def render(self):
        _clear_layout(self.body)
        if self.data is None:
            self.stamp.setText("")
            self.body.addWidget(muted(
                "Bina konumu girilmemiş: bina düzenleme ekranında ülke, il ve ilçeyi girin." if self.status == "konum" else
                "İklim verisi alınamadı ve önbellekte veri yok (internet gerekir). Bağlanınca «Şimdi yenile»ye basın."))
            return
        live = self.status == "ok"
        self.stamp.setText(("● Canlı · " if live else "○ Çevrimdışı, son veri · ") + f"güncelleme {self._age()}"
                           + f" · {self.project.building.name}")
        self.stamp.setStyleSheet(f"color: {G if live else AMBER}; font-size: 12px; background: transparent;")
        cur = self.data["current"]
        name, icon = weather.describe(cur["code"])
        row = QHBoxLayout()
        row.setSpacing(14)
        for title, val, f, sub, acc in (
                ("Sıcaklık", cur["temp"], lambda v: f"{v:.1f} °C", f"{icon} {name}", G),
                ("Hissedilen", cur["feels"] if cur["feels"] is not None else cur["temp"], lambda v: f"{v:.1f} °C", "görünür sıcaklık", INDIGO),
                ("Nem", cur["humidity"] or 0, lambda v: f"%{v:.0f}", "bağıl nem", INDIGO),
                ("Rüzgâr", cur["wind"] or 0, lambda v: f"{v:.0f} km/s", "10 m yükseklikte", AMBER),
                ("Güneş ışınımı", cur["radiation"] or 0, lambda v: f"{v:.0f} W/m²", "kısa dalga", AMBER),
                ("Yağış", cur["precip"], lambda v: f"{v:.1f} mm", "şu anki", INDIGO)):
            c = Card(title, sub=sub, accent=acc)
            c.set_number(val, f, sub)
            row.addWidget(c)
        self.body.addLayout(row)

        daily = self.data["daily"]
        today = date.today().isoformat()
        chart = Panel(eyebrow="14 gün", title="Günlük ortalama sıcaklık", subtitle="°C · son 7 gün gözlem/analiz, sonraki 7 gün tahmin")
        chart.lay.addWidget(area_chart([f"{d['date'][8:]}.{d['date'][5:7]}" for d in daily],
                                       {"Ortalama": [d["tmean"] for d in daily], "Maks": [d["tmax"] for d in daily], "Min": [d["tmin"] for d in daily]},
                                       scale=1.0, decimals=0, colors=["green", "amber", "indigo"], unit="°C", min_h=230))
        self.body.addWidget(chart)

        ol = outlook(self.project, self.dd, daily)
        op = Panel(eyebrow="Enerji öngörüsü", title="Önümüzdeki 7 gün", subtitle=ol.note or "")
        if not ol.ok:
            op.lay.addWidget(muted(ol.note or "Öngörü hesaplanamadı."))
        else:
            summary = QHBoxLayout()
            summary.setSpacing(14)
            gd, ed = ol.delta_pct("gas"), ol.delta_pct("elec")
            for title, total, normal, dpct, acc in (("Doğalgaz", ol.gas_total, ol.gas_normal, gd, AMBER), ("Elektrik", ol.elec_total, ol.elec_normal, ed, INDIGO)):
                if total <= 0 and normal <= 0:
                    continue
                c = Card(f"{title} · 7 gün", accent=acc)
                sub = (f"normal haftaya göre %{abs(dpct):.0f} {'fazla' if dpct > 0 else 'az'}" if dpct is not None else "normal hafta bilinmiyor")
                c.set_number(total / 1000, lambda v: f"{fmt(v, 1)} MWh", sub)
                summary.addWidget(c)
            op.lay.addLayout(summary)
            t = _table(["Gün", "Durum", "Min / Maks (°C)", "HDD", "CDD", "Doğalgaz (MWh)", "Elektrik (MWh)"], left_cols=2)
            by_date = {d["date"]: d for d in daily}
            t.setRowCount(len(ol.days))
            for i, d in enumerate(ol.days):
                src = by_date[d.day]
                nm, ic = weather.describe(src["code"])
                _set_row(t, i, [f"{d.day[8:]}.{d.day[5:7]}" + (" (bugün)" if d.day == today else ""), f"{ic} {nm}",
                                f"{src['tmin']:.0f} / {src['tmax']:.0f}", f"{d.hdd:.1f}", f"{d.cdd:.1f}", fmt(d.gas_kwh / 1000, 2), fmt(d.elec_kwh / 1000, 2)],
                         left_cols=2, mono_from=2)
            _fit_height(t, len(ol.days))
            op.lay.addWidget(t)
            r2 = ", ".join(f"{('doğalgaz' if k == 'gas' else 'elektrik')} R² {v:.2f}" for k, v in ol.r2.items())
            op.lay.addWidget(muted(f"Model güveni: {r2}. HDD/CDD taban 15/22 °C (varsayım). Tahmin günlük hava + aylık regresyondur; gerçek tüketim hafta sonu ve tatilden etkilenir."))
        self.body.addWidget(op)
        self.body.addWidget(muted("Hava verisi: Open-Meteo.com (CC BY 4.0)."))
