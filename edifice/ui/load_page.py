from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDoubleSpinBox, QFileDialog, QHBoxLayout, QMessageBox, QPushButton

from ..db import Store
from ..engine.loadprofile import BANDS, DEFAULT_RATIOS, analyze, compare_tariffs, parse_interval_file
from ..models import UtilityType
from ..service import Project
from .pages import _clear_layout, _fit_height, _page, _set_row, _table, area_chart
from .widgets import AMBER, G, Card, Panel, fmt, header, muted

BAND_LABEL = {"T1": "T1 gündüz 06-17", "T2": "T2 puant 17-22", "T3": "T3 gece 22-06"}


class LoadPage:
    """Saatlik/aralıklı yük analizi: akıllı sayaç CSV'si -> yük profili, boşta yük, pik, çok zamanlı tarife karşılaştırması."""

    def __init__(self, project: Project, store: Store):
        self.project, self.store = project, store
        self.widget, self.lay = _page()
        self.lay.addWidget(header("Finans", "Yük profili ve tarife",
                                  "Akıllı sayaç/dağıtım şirketi saatlik ya da 15 dakikalık tüketim dosyasını (CSV) yükleyin. Boşta tüketim, pik ve "
                                  "çok zamanlı tarife karşılaştırması bu veriden hesaplanır. Aylık faturadan çıkarılamayan bilgiler bunlardır."))
        bar = QHBoxLayout()
        b = QPushButton("⇪ Yük dosyası yükle (CSV)")
        b.setObjectName("primary")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(self.import_file)
        clr = QPushButton("Verileri sil")
        clr.setObjectName("export")
        clr.clicked.connect(self.clear)
        bar.addWidget(b)
        bar.addWidget(clr)
        bar.addStretch()
        self.lay.addLayout(bar)
        self.body = Panel()
        self.lay.addWidget(self.body)
        self.lay.addStretch()
        self.ratios = dict(DEFAULT_RATIOS)
        self.render()

    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(self.widget, "Yük dosyası seç", "", "CSV (*.csv *.txt)")
        if not path or self.project.building_id is None:
            return
        s = parse_interval_file(path)
        if not s.points:
            QMessageBox.warning(self.widget, "Yük dosyası", "Okunamadı:\n• " + "\n• ".join(s.warnings or ["boş dosya"]))
            return
        self.store.save_interval(self.project.building_id, s)
        self.render()

    def clear(self):
        if self.project.building_id is not None:
            self.store.clear_interval(self.project.building_id)
            self.render()

    def render(self):
        _clear_layout(self.body.lay)
        s = self.store.load_interval(self.project.building_id) if self.project.building_id is not None else None
        if not s or not s.points:
            self.body.lay.addWidget(muted("Henüz yük verisi yok. Beklenen: «Tarih» ve «kWh» (ya da «kW») sütunlu CSV; 15 dk / 30 dk / saatlik aralık otomatik anlaşılır."))
            return
        r = analyze(s)
        if not r.ok:
            self.body.lay.addWidget(muted(r.note))
            return
        row = QHBoxLayout()
        row.setSpacing(14)
        cards = [("Pik güç", f"{fmt(r.peak_kw)} kW", f"{r.peak_at:%d.%m.%Y %H:%M}", AMBER), ("Temel (boşta) yük", f"{fmt(r.base_kw)} kW", f"pikin %{r.base_to_peak * 100:.0f}'i", G),
                 ("Yük faktörü", fmt(r.load_factor, 2), "ortalama ÷ pik", G), ("Gece + hafta sonu", f"%{r.off_hours_share * 100:.0f}", f"{r.days} gün veri", G)]
        for t, v, sub, col in cards:
            c = Card(t, accent=col)
            c.set_number(1.0, lambda _x, v=v: v, sub)
            row.addWidget(c)
        self.body.lay.addLayout(row)
        hours = [f"{h:02d}" for h in range(24)]
        self.body.lay.addWidget(area_chart(hours, {"Hafta içi": r.weekday_profile, "Hafta sonu": r.weekend_profile}, unit="kW", min_h=190))
        for w in r.warnings:
            self.body.lay.addWidget(muted("⚠ " + w))
        for f in r.findings:
            self.body.lay.addWidget(muted("• " + f))
        # tarife karşılaştırması
        price = self.project.assumptions.default_tariffs[UtilityType.ELECTRICITY]
        ctl = QHBoxLayout()
        ctl.addWidget(muted("Tek zamanlı birim fiyat (₺/kWh):"))
        self.price = QDoubleSpinBox()
        self.price.setRange(0.1, 100)
        self.price.setDecimals(2)
        self.price.setValue(price)
        ctl.addWidget(self.price)
        self.rsp = {}
        for k in BANDS:
            ctl.addWidget(muted(f"{k} oranı:"))
            sp = QDoubleSpinBox()
            sp.setRange(0.1, 5)
            sp.setDecimals(2)
            sp.setSingleStep(0.05)
            sp.setValue(self.ratios[k])
            sp.valueChanged.connect(self._tariff)
            self.rsp[k] = sp
            ctl.addWidget(sp)
        self.price.valueChanged.connect(self._tariff)
        ctl.addStretch()
        self.body.lay.addWidget(muted("ÇOK ZAMANLI TARİFE (oranlar varsayımdır: güncel EPDK tarifesine göre değiştirin)"))
        self.body.lay.addLayout(ctl)
        self.tbl_host = QHBoxLayout()
        self.body.lay.addLayout(self.tbl_host)
        self.sum_lbl = muted("")
        self.body.lay.addWidget(self.sum_lbl)
        self._report = r
        self._tariff()

    def _tariff(self, *_):
        r = self._report
        self.ratios = {k: sp.value() for k, sp in self.rsp.items()}
        c = compare_tariffs(r, self.price.value(), self.ratios)
        _clear_layout(self.tbl_host)
        t = _table(["Dilim", "Tüketim (MWh)", "Pay", "Maliyet (bin ₺)"])
        t.setRowCount(3)
        for i, k in enumerate(BANDS):
            _set_row(t, i, [BAND_LABEL[k], fmt(r.band_kwh[k] / 1000, 1), f"%{r.band_kwh[k] / r.kwh * 100:.0f}", fmt(c.band_cost[k] / 1000, 1)], mono_from=1)
        _fit_height(t, 3)
        self.tbl_host.addWidget(t)
        sign = "ucuz" if c.saving > 0 else "pahalı"
        self.sum_lbl.setText(f"Bu yük profilinde çok zamanlı tarife tek zamanlıya göre {fmt(abs(c.saving) / 1000, 1)} bin ₺ {sign} "
                             f"(ölçüm dönemi toplamı). Puant tüketiminin %20'sini geceye kaydırmak ek {fmt(c.shift_gain / 1000, 1)} bin ₺ kazandırır. "
                             "Talep (kW) bedeli, reaktif ve abonelik grubu bu hesaba dahil değildir.")
