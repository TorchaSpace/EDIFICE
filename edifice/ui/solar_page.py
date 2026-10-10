from __future__ import annotations

from PySide6.QtCore import QObject, QUrl, Qt, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import QDoubleSpinBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .. import solar
from ..engine import solar_sizing as ss
from ..models import UtilityType
from .pages import MONTHS, _clear_layout, _page, area_chart, bar_chart
from .widgets import AMBER, G, INDIGO, Card, Panel, fmt, fmt_years, header, muted


class SolarLoader(QObject):
    """PVGIS aylık verimini önbellekten verir; yoksa bir kez indirir."""
    done = Signal(object, str)      # 12 aylık kWh/kWp ya da None, durum: ok | konum | ağ

    def __init__(self, parent=None):
        super().__init__(parent)
        self._net = QNetworkAccessManager(self)

    def load(self, store, project):
        b = project.building
        if b.lat is None or b.lon is None:
            self.done.emit(None, "konum")
            return
        cached = store.load_solar(b.lat, b.lon, solar.DEFAULT_ANGLE, solar.DEFAULT_ASPECT)
        if cached:
            self.done.emit(cached, "ok")
            return
        req = QNetworkRequest(QUrl(solar.request_url(b.lat, b.lon)))
        req.setRawHeader(b"User-Agent", b"EDIFICE-desktop/1.0 (building dashboard)")
        reply = self._net.get(req)

        def finished():
            data = bytes(reply.readAll()) if reply.error() == reply.NetworkError.NoError else b""
            reply.deleteLater()
            monthly = solar.parse_pvgis(data)
            if monthly is None:
                self.done.emit(None, "ağ")
                return
            store.save_solar(b.lat, b.lon, solar.DEFAULT_ANGLE, solar.DEFAULT_ASPECT, monthly)
            self.done.emit(monthly, "ok")
        reply.finished.connect(finished)


class SolarPage:
    """Çatı GES: önerilen boyut (NPV'yi en yükseğe çıkaran), üretim–tüketim dengesi ve finansal sonuç."""

    def __init__(self, project, store):
        self.project, self.store = project, store
        self.yield_m: list[float] | None = None
        self.widget, lay = _page()
        lay.addWidget(header("Güneş enerjisi", "Çatı GES analizi",
                             "Konumdan PVGIS ile aylık üretim modellenir; aylık elektrik tüketimiyle dengelenerek NPV'yi en yükseğe çıkaran boyut bulunur."))
        self.note = Panel(eyebrow="Varsayımlar", title="Girdiler",
                          subtitle="Birim maliyet ve eşzamanlılık varsayımdır (Kaynaklar ve Yöntem'de işaretli). Gerçek teklif ve çatı keşfiyle değiştirin.")
        row = QHBoxLayout()
        row.setSpacing(12)
        self.capex = QDoubleSpinBox()
        self.capex.setRange(1000, 200000)
        self.capex.setDecimals(0)
        self.capex.setSingleStep(1000)
        self.capex.setSuffix(" ₺/kWp")
        self.capex.setValue(float(store.get_setting("solar_capex", str(ss.DEFAULT_CAPEX_PER_KWP))))
        self.kwp = QDoubleSpinBox()
        self.kwp.setRange(0, 5000)
        self.kwp.setDecimals(0)
        self.kwp.setSingleStep(5)
        self.kwp.setSuffix(" kWp (0 = otomatik en iyi)")
        for w in (self.capex, self.kwp):
            w.setMinimumHeight(36)
            w.setMinimumWidth(210)
        btn = QPushButton("Hesapla")
        btn.setObjectName("primary")
        btn.setMinimumHeight(36)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self.render)
        row.addWidget(QLabel("Birim maliyet"))
        row.addWidget(self.capex)
        row.addWidget(QLabel("Boyut"))
        row.addWidget(self.kwp)
        row.addWidget(btn)
        row.addStretch()
        self.note.lay.addLayout(row)
        lay.addWidget(self.note)
        self.body = QVBoxLayout()
        self.body.setSpacing(16)
        lay.addLayout(self.body)
        lay.addStretch()
        self.body.addWidget(muted("Güneş verisi yükleniyor…"))

    def set_yield(self, monthly, status: str):
        self.yield_m = monthly
        if monthly is None:
            _clear_layout(self.body)
            self.body.addWidget(muted(
                "Bina konumu girilmemiş: bina düzenleme ekranında ülke, il ve ilçeyi girin." if status == "konum" else
                "Güneş verisi indirilemedi (internet gerekir); bağlanınca tekrar açın."))
            return
        self.render()

    def render(self):
        if not self.yield_m:
            return
        p = self.project
        _clear_layout(self.body)
        self.store.set_setting("solar_capex", str(int(self.capex.value())))
        cons = p.monthly(p.year, UtilityType.ELECTRICITY)
        price = p.prices()[UtilityType.ELECTRICITY]
        if sum(cons) <= 0 or price <= 0:
            self.body.addWidget(muted("Elektrik tüketimi ya da birim fiyatı yok; GES hesaplanamaz."))
            return
        cap = ss.max_kwp(p.building.floor_area_m2, p.building.floors)
        best, sweep = ss.size_for_best_npv(self.yield_m, cons, price, p.assumptions, cap, self.capex.value())
        chosen = (ss.evaluate(self.kwp.value(), self.yield_m, cons, price, p.assumptions, self.capex.value()) if self.kwp.value() > 0 else best)
        if chosen is None:
            self.body.addWidget(muted(f"Bu varsayımlarla (birim maliyet {fmt(self.capex.value())} ₺/kWp, elektrik {price:.2f} ₺/kWh) NPV'si pozitif bir GES boyutu yok. "
                                      "Daha düşük maliyet teklifi ya da daha yüksek tarife bunu değiştirebilir."))
            return
        f = chosen.finance
        grid = QHBoxLayout()
        grid.setSpacing(14)
        specs = [("Boyut", chosen.kwp, lambda v: f"{fmt(v)} kWp", f"çatı sınırı ≈ {fmt(cap)} kWp" + (" · en iyi NPV" if chosen is best else ""), G),
                 ("Yıllık üretim", chosen.production_kwh / 1000, lambda v: f"{fmt(v)} MWh", f"%{chosen.coverage_pct:.0f} elektrik karşılanır", G),
                 ("Yıllık tasarruf", chosen.saving / 1e6, lambda v: f"{fmt(v, 2)} M ₺", f"öz tüketim %{100 * chosen.self_kwh / chosen.production_kwh:.0f}", G),
                 ("CAPEX", chosen.capex / 1e6, lambda v: f"{fmt(v, 2)} M ₺", f"{fmt(self.capex.value())} ₺/kWp (varsayım)", AMBER),
                 ("Geri ödeme", f.simple_payback if f.simple_payback != float("inf") else 0, lambda v: fmt_years(v) if v else "-", "basit (fiyat artışı dahil)", INDIGO),
                 ("NPV", f.npv / 1e6, lambda v: f"{fmt(v, 2)} M ₺", f"IRR %{f.irr * 100:.1f}" if f.irr is not None else "IRR tanımsız", G if f.npv >= 0 else AMBER)]
        for t, v, fm, sub, acc in specs:
            c = Card(t, sub=sub, accent=acc)
            c.set_number(v, fm, sub)
            grid.addWidget(c)
        self.body.addLayout(grid)
        row = QHBoxLayout()
        row.setSpacing(18)
        pm = Panel(eyebrow="Üretim ve tüketim", title="Aylık GES üretimi ve elektrik tüketimi", subtitle="MWh · öz tüketim = aylık örtüşmenin %85'i (varsayım)")
        pm.lay.addWidget(bar_chart(MONTHS, {"Elektrik tüketimi": cons, "GES üretimi": chosen.monthly_production, "Öz tüketilen": chosen.monthly_self},
                                   scale=1000, unit="MWh", colors=["slate", "amber", "green"], min_h=260), 1)
        row.addWidget(pm, 1)
        ps = Panel(eyebrow="Boyutlandırma", title="Boyut – NPV", subtitle="M ₺ · eğrinin en yüksek noktası NPV açısından en iyi boyuttur")
        ps.lay.addWidget(area_chart([f"{int(s.kwp)}" for s in sweep], {"NPV": [s.finance.npv for s in sweep]}, scale=1e6, decimals=1,
                                    colors=["green"], unit="M ₺", min_h=260), 1)
        row.addWidget(ps, 1)
        self.body.addLayout(row)
        self.body.addWidget(muted(f"Önlenen karbon: {fmt(chosen.carbon_avoided_kg / 1000, 1)} tCO₂/yıl · Üretim verisi: PVGIS (AB JRC), 30° eğim, güney, %14 kayıp. "
                                  "Modellenmiş üretimdir; gölgelenme, kirlenme ve gerçek çatı geometrisi dahil değildir. Fazla üretim gelire sayılmaz (muhafazakâr)."))
