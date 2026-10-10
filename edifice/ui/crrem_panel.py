from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from ..crrem import CrremError, parse
from ..engine.stranding import analyze
from ..models import UtilityType
from .dropdown import PremiumCombo
from .pages import _clear_layout, area_chart
from .widgets import AMBER, G, RED, SUB, Panel, fmt, muted

METRICS = {"ghg": "Karbon (kgCO₂e/m²)", "kwh": "Enerji (kWh/m²)"}
DEFAULT_TYPE = {"Ofis": "OFF", "Otel": "HOT", "Konut": "RMF", "Hastane": "HEC", "Ticari / AVM": "RSM", "Sanayi": "DWW"}
SOURCE_URL = "https://crrem.org/library/pathways-datasets/"
TERMS_URL = "https://crrem.org/library/use-of-data/"


class CrremPanel(Panel):
    """CRREM yollarını kullanıcının kendi içe aktardığı resmî dosyadan okur; veri uygulamayla dağıtılmaz (lisans)."""

    def __init__(self, store, rows, per_building_kg: dict, per_building_kwh: dict, base_year: int):
        super().__init__(eyebrow="CRREM", title="CRREM yoluna göre yol aşımı (resmî veri, sizin içe aktardığınız)",
                         subtitle="CRREM verisi bu uygulamada YOKTUR ve dağıtılmaz: lisans koşulları gereği dosyayı crrem.org'dan kendiniz indirip içe aktarırsınız; "
                                  "veri yalnız bu bilgisayarda kalır, kendi kararlarınızda kullanılır.")
        self.store, self.rows, self.kg, self.kwh, self.base_year = store, rows, per_building_kg, per_building_kwh, base_year
        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        self.lay.addLayout(self.body)
        self.rebuild()

    # ---- seçimler
    def _sel(self, bid: int) -> dict:
        raw = self.store.get_setting(f"crrem_sel_{bid}")
        return json.loads(raw) if raw else {}

    def _save_sel(self, bid: int, **kw):
        s = self._sel(bid)
        s.update(kw)
        self.store.set_setting(f"crrem_sel_{bid}", json.dumps(s))

    def rebuild(self):
        _clear_layout(self.body)
        meta = self.store.crrem_meta()
        top = QHBoxLayout()
        imp = QPushButton("CRREM dosyasını içe aktar (.xlsx)")
        imp.setObjectName("primary" if not meta else "export")
        imp.setCursor(Qt.PointingHandCursor)
        imp.setMinimumHeight(34)
        imp.clicked.connect(self.import_file)
        top.addWidget(imp)
        if meta:
            rm = QPushButton("Kaldır")
            rm.setObjectName("export")
            rm.setMinimumHeight(34)
            rm.setCursor(Qt.PointingHandCursor)
            rm.clicked.connect(lambda: (self.store.clear_crrem(), self.rebuild()))
            top.addWidget(rm)
        top.addStretch()
        self.body.addLayout(top)
        links = QLabel(f"Kaynak: <a href='{SOURCE_URL}' style='color:{G}'>crrem.org/library/pathways-datasets</a> · "
                       f"kullanım koşulları: <a href='{TERMS_URL}' style='color:{G}'>crrem.org/library/use-of-data</a>")
        links.setOpenExternalLinks(True)
        links.setStyleSheet(f"color: {SUB}; font-size: 12px; background: transparent;")
        self.body.addWidget(links)
        if not meta:
            self.body.addWidget(muted(
                "1) Yukarıdaki sayfadan «CRREM Global Pathways» Excel dosyasını indirin (kayıt formu ve kullanım koşulları sizinle). "
                "2) «İçe aktar»a basın. Not: CRREM'in bildiğimiz sürümlerinde Türkiye (TR) yoktur; vekil ülke seçmek sizin kararınızdır ve sonuçta belirtilir."))
            self._chart_box = None
            return
        self.body.addWidget(muted(f"İçe aktarılan: {meta['file']} · {meta['version'] or 'sürüm bilgisi yok'} · {meta['imported'][:10]}. "
                                  f"Atıf: CRREM Foundation, CRREM Global Pathways, crrem.org."))
        countries, types = self.store.crrem_options()
        has_tr = any(c in ("TR", "TUR") for c in countries)
        if not has_tr:
            warn = QLabel("⚠ Bu dosyada Türkiye yok. Aşağıda seçeceğiniz ülke bir VEKİLDİR (iklim/şebeke farkı nedeniyle Türkiye için resmî bir yol değildir).")
            warn.setWordWrap(True)
            warn.setStyleSheet(f"color: {AMBER}; font-size: 12px; background: transparent;")
            self.body.addWidget(warn)
        self.grid_cb = QCheckBox("Şebeke dekarbonizasyonunu uygula (seçilen ülkenin elektrik emisyon eğrisinin göreli düşüşü; model varsayımı)")
        self.grid_cb.setStyleSheet(f"QCheckBox {{ color: {SUB}; font-size: 12px; background: transparent; spacing: 8px; }}")
        self.grid_cb.setChecked(self.store.get_setting("crrem_grid", "0") == "1")
        self.grid_cb.toggled.connect(lambda v: (self.store.set_setting("crrem_grid", "1" if v else ""), self.recompute()))
        self.body.addWidget(self.grid_cb)
        self.row_widgets = []
        for bid, r in self.rows:
            p = r["project"]
            sel = self._sel(bid)
            line = QHBoxLayout()
            line.setSpacing(8)
            nm = QLabel(p.building.name)
            nm.setStyleSheet("font-size: 13px; font-weight: 700; background: transparent;")
            nm.setMinimumWidth(150)
            line.addWidget(nm, 1)
            combos = []
            for items, key, width in ((countries, "country", 90), (types, "type", 90), (list(METRICS), "metric", 190)):
                cb = PremiumCombo()
                cb.addItem("—")
                for it in items:
                    cb.addItem(METRICS[it] if key == "metric" else it, it)
                want = sel.get(key) or (DEFAULT_TYPE.get(p.building.use_type) if key == "type" else "ghg" if key == "metric" else None)
                if want in items:
                    cb.setCurrentIndex(items.index(want) + 1)
                cb.setFixedWidth(width)
                cb.setMinimumHeight(32)
                cb.currentIndexChanged.connect(lambda _i, b=bid: self._changed(b))
                combos.append(cb)
                line.addWidget(cb)
            res = QLabel("")
            res.setMinimumWidth(240)
            res.setStyleSheet(f"color: {SUB}; font-size: 12px; background: transparent;")
            line.addWidget(res)
            w = QWidget()
            w.setLayout(line)
            self.body.addWidget(w)
            self.row_widgets.append((bid, r, combos, res))
        self._chart_box = QVBoxLayout()
        self.body.addLayout(self._chart_box)
        self.recompute()

    def _vals(self, combos):
        c, t, m = combos
        return (c.currentData() if c.currentIndex() else None, t.currentData() if t.currentIndex() else None, m.currentData() if m.currentIndex() else "ghg")

    def _changed(self, bid):
        for b, _r, combos, _res in self.row_widgets:
            if b == bid:
                c, t, m = self._vals(combos)
                self._save_sel(bid, country=c, type=t, metric=m)
        self.recompute()

    def recompute(self):
        _clear_layout(self._chart_box)
        charted = False
        for bid, r, combos, res in self.row_widgets:
            country, ptype, metric = self._vals(combos)
            if not (country and ptype):
                res.setText("ülke ve tür seçin")
                continue
            path = self.store.crrem_pathway(metric, country, ptype)
            if not path:
                res.setText("bu ülke/tür için yol yok")
                continue
            p, k = r["project"], r["kpis"]
            area = p.building.floor_area_m2
            if area <= 0:
                res.setText("alan yok")
                continue
            ef_e = p.assumptions.emission_factor_kg_per_kwh[UtilityType.ELECTRICITY]
            if metric == "ghg":
                cur, elec_part = k.carbon_kg / area, k.electricity_kwh * ef_e / area
                sav = {y: v / area for y, v in self.kg.get(bid, {}).items()}
            else:
                cur, elec_part = k.eui_kwh_m2, 0.0
                sav = {y: v / area for y, v in self.kwh.get(bid, {}).items()}
            scale = None
            if metric == "ghg" and self.grid_cb.isChecked():
                g = self.store.crrem_grid(country)
                if g.get(self.base_year):
                    scale = {y: g[y] / g[self.base_year] for y in g}
            a = analyze(path, self.base_year, cur, sav, elec_part, scale)
            if not a.years:
                res.setText(a.note)
                continue
            if a.stranded_year is None:
                res.setText(f"✓ yolun altında kalır · şimdi {fmt(cur, 1)} / yol {fmt(a.pathway[0], 1)}")
                res.setStyleSheet(f"color: {G}; font-size: 12px; background: transparent;")
            else:
                label = "Şimdi aşıyor" if a.stranded_year == self.base_year else f"{a.stranded_year}'de aşar"
                res.setText(f"{label} · şimdi {fmt(cur, 1)} / yol {fmt(a.pathway[0], 1)}")
                res.setStyleSheet(f"color: {RED if a.stranded_year == self.base_year else AMBER}; font-size: 12px; font-weight: 700; background: transparent;")
            if not charted:
                charted = True
                self._chart_box.addWidget(muted(f"{p.building.name}: öngörülen yoğunluk ve CRREM yolu ({country}.{ptype}, {METRICS[metric]})"
                                                + (" · şebeke dekarbonizasyonu varsayımı açık" if scale else "")))
                self._chart_box.addWidget(area_chart([str(y) for y in a.years], {"Öngörülen": a.projected, "CRREM yolu": a.pathway},
                                                     scale=1.0, decimals=0, colors=["amber", "green"], unit="", min_h=200))

    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "CRREM yol dosyasını seç", "", "Excel (*.xlsx *.xlsm)")
        if not path:
            return
        try:
            data = parse(path)
        except CrremError as e:
            QMessageBox.warning(self, "CRREM dosyası okunamadı", str(e))
            return
        n = self.store.import_crrem(data)
        msg = f"{len(data.countries)} ülke/şehir kodu, {len(data.types)} mülk türü, {n} değer içe aktarıldı."
        if "TR" not in data.countries and "TUR" not in data.countries:
            msg += "\n\nBu dosyada Türkiye yok; vekil ülke seçimi sizin kararınızdır."
        QMessageBox.information(self, "CRREM yolları içe aktarıldı", msg)
        self.rebuild()
