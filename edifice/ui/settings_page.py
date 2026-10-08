"""Ayarlar: hesap varsayımları (emisyon, tarife, kıyas, Health Score ağırlıkları) ve öneri kataloğu."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import (QAbstractItemView, QDoubleSpinBox, QGraphicsOpacityEffect, QGridLayout,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
                               QTableWidget, QWidget)

from ..db import Store
from ..models import Assumptions, UtilityType
from ..service import Project
from .forms import field, tune_spin
from .pages import _page
from .widgets import G, RED, SUB, Panel, header


def _spin(value: float, lo: float, hi: float, decimals: int, suffix: str = "") -> QDoubleSpinBox:
    sp = tune_spin(QDoubleSpinBox())
    sp.setRange(lo, hi)
    sp.setDecimals(decimals)
    sp.setSingleStep(10 ** -decimals if decimals else 1)
    sp.setValue(value)
    if suffix:
        sp.setSuffix(suffix)
    sp.setGroupSeparatorShown(True)
    return sp


class SettingsPage:
    def __init__(self, project: Project, store: Store, on_saved):
        self.project, self.store, self.on_saved = project, store, on_saved
        a = project.assumptions
        self.widget, lay = _page()
        lay.addWidget(header("Ayarlar", "Hesap varsayımları",
                             "Health Score, karbon, maliyet ve öneri hesapları bu değerlerle yapılır. Değişiklikler tüm "
                             "binalara uygulanır. Gerçek değerlerinizi girince sonuçlar hemen güncellenir."))

        row1 = QHBoxLayout()
        row1.setSpacing(18)
        em = Panel("Emisyon faktörleri", "Enerjinin karbon karşılığı (kgCO₂ / kWh)")
        self.ef_e = _spin(a.emission_factor_kg_per_kwh[UtilityType.ELECTRICITY], 0, 5, 3, " kgCO₂/kWh")
        self.ef_g = _spin(a.emission_factor_kg_per_kwh[UtilityType.GAS], 0, 5, 3, " kgCO₂/kWh")
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        g.addWidget(field("Elektrik", self.ef_e, "Türkiye 2020 üretim bazlı: 0,437 (Şahin & Esen 2022)"), 0, 0)
        g.addWidget(field("Doğalgaz", self.ef_g, "IPCC 2006, net ısıl değer. Fatura kWh'si üst ısıl değere göreyse ≈0,182"), 0, 1)
        em.lay.addSpacing(6)
        em.lay.addLayout(g)
        row1.addWidget(em, 1)

        tf = Panel("Varsayılan tarifeler", "Bina Ekle'de fatura tutarı boş bırakılan aylarda kullanılır")
        self.t_e = _spin(a.default_tariffs[UtilityType.ELECTRICITY], 0, 1000, 2, " ₺/kWh")
        self.t_g = _spin(a.default_tariffs[UtilityType.GAS], 0, 1000, 2, " ₺/kWh")
        self.t_w = _spin(a.default_tariffs[UtilityType.WATER], 0, 10000, 2, " ₺/m³")
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        g.addWidget(field("Elektrik", self.t_e), 0, 0)
        g.addWidget(field("Doğalgaz", self.t_g), 0, 1)
        g.addWidget(field("Su", self.t_w), 0, 2)
        tf.lay.addSpacing(6)
        tf.lay.addLayout(g)
        row1.addWidget(tf, 1)
        lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(18)
        bm = Panel("Kıyas değerleri", "Binanın ne kadar iyi/kötü olduğu bu referanslarla ölçülür. Varsayılanlar ENERGY STAR (ABD ulusal medyan site EUI, "
                              "Ağustos 2024) değerleridir; Türkiye iklimi ve uygulaması farklıdır, BEP-TR referans değerlerinizi girerek değiştirin.")
        self.b_use = {}
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        g.setVerticalSpacing(14)
        for i, (use, val) in enumerate(a.benchmark_eui_by_use.items()):
            sp = _spin(val, 1, 3000, 1, " kWh/m²·yıl")
            self.b_use[use] = sp
            g.addWidget(field(use, sp), i // 2, i % 2)
        self.b_eui = _spin(a.benchmark_eui_kwh_m2, 1, 3000, 0, " kWh/m²·yıl")
        n = len(a.benchmark_eui_by_use)
        g.addWidget(field("Diğer / Sanayi (yedek)", self.b_eui, "Kaynakta sanayi için veri yok"), n // 2, n % 2)
        self.b_w = _spin(a.benchmark_water_m3_m2, 0.01, 50, 2, " m³/m²·yıl")
        self.life = _spin(a.equipment_life_years, 1, 60, 0, " yıl")
        g.addWidget(field("Su yoğunluğu", self.b_w, "Kaynak bulunamadı (varsayım)"), (n + 1) // 2, (n + 1) % 2)
        g.addWidget(field("Ekipman ömrü (yedek)", self.life, "Soğutucu/kazan/santral/pompa için tür bazlı ömür kullanılır"), (n + 2) // 2, (n + 2) % 2)
        bm.lay.addSpacing(6)
        bm.lay.addLayout(g)
        note = QLabel("Karbon yoğunluğu kıyası: kıyas EUI × ağırlıklı emisyon faktörü olarak türetilir (kaynak yok).")
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {SUB}; font-size: 12px; background: transparent;")
        bm.lay.addWidget(note)
        row2.addWidget(bm, 3)

        hw = Panel("Health Score ağırlıkları", "Dört bileşenin skora katkısı; toplam %100 olmalı")
        self.w_spins = {}
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        g.setVerticalSpacing(14)
        for i, (name, wt) in enumerate(a.health_weights.items()):
            sp = _spin(round(wt * 100), 0, 100, 0, " %")
            sp.valueChanged.connect(self._weights_changed)
            self.w_spins[name] = sp
            g.addWidget(field(name, sp), i // 2, i % 2)
        self.w_total = QLabel("")
        hw.lay.addSpacing(6)
        hw.lay.addLayout(g)
        hw.lay.addWidget(self.w_total)
        row2.addWidget(hw, 2)
        lay.addLayout(row2)

        fp = Panel("Finansal varsayımlar", "NPV, IRR ve nakit akışı reel (enflasyondan arındırılmış) değerlerle hesaplanır")
        self.f_disc = _spin(a.discount_rate * 100, 0, 60, 1, " %")
        self.f_esc = _spin(a.energy_escalation * 100, -10, 30, 1, " %")
        self.f_years = _spin(a.horizon_years, 3, 40, 0, " yıl")
        self.f_deg = _spin(a.savings_degradation * 100, 0, 10, 1, " %")
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        g.addWidget(field("Reel iskonto oranı", self.f_disc, "Yatırımın fırsat maliyeti"), 0, 0)
        g.addWidget(field("Enerji fiyat artışı (reel)", self.f_esc, "Enflasyonun üstündeki yıllık artış"), 0, 1)
        g.addWidget(field("Analiz süresi", self.f_years, "NPV ve nakit akışı ufku"), 0, 2)
        g.addWidget(field("Yıllık tasarruf kaybı", self.f_deg, "Ekipman yıpranması"), 0, 3)
        fp.lay.addSpacing(6)
        fp.lay.addLayout(g)
        lay.addWidget(fp)

        cat = Panel("Dönüşüm önerileri kataloğu", "Her öneri için beklenen tasarruf oranı ve birim yatırım maliyeti")
        self.table = QTableWidget(len(project.opportunities), 6)
        self.table.setHorizontalHeaderLabels(["Öneri", "Kategori", "Etkilediği kalem", "Tasarruf oranı", "Literatür aralığı", "Yatırım (₺/m²)"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Stretch)
        for col, width in ((3, 150), (4, 200), (5, 170)):
            hh.setSectionResizeMode(col, QHeaderView.Fixed)
            self.table.setColumnWidth(col, width)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(56)
        self.table.setShowGrid(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setFixedHeight(46 + 56 * len(project.opportunities))
        self.opp_widgets = []
        names = {"electricity": "Elektrik", "gas": "Doğalgaz"}
        for r, o in enumerate(project.opportunities):
            name = QLineEdit(o.name)
            name.setObjectName("cellInput")
            pct = _spin(o.saving_pct * 100, 0, 90, 1, " %")
            capex = _spin(o.capex_per_m2, 0, 100000, 0, " ₺/m²")
            for col, w in ((0, name), (3, pct), (5, capex)):
                w.setMinimumHeight(38)
                self.table.setCellWidget(r, col, self._cell(w))
            lo, hi = o.saving_for("low") * 100, o.saving_for("high") * 100
            rng = f"%{lo:.0f}-{hi:.1f}".replace(".", ",") + f" · {o.evidence_level}"
            for col, text in ((1, o.category), (2, names.get(o.affects.value, o.affects.value)), (4, rng)):
                lbl = QLabel(text)
                lbl.setStyleSheet(f"color: {SUB}; font-size: 13px; padding-left: 14px; background: transparent;")
                self.table.setCellWidget(r, col, lbl)
            self.opp_widgets.append((o, name, pct, capex))
        cat.lay.addWidget(self.table)
        lay.addWidget(cat)

        bar = QHBoxLayout()
        bar.setSpacing(10)
        self.status = QLabel("")
        self.status.setStyleSheet("font-size: 13px; font-weight: 600; background: transparent;")
        self._fx = QGraphicsOpacityEffect(self.status)
        self.status.setGraphicsEffect(self._fx)
        self._fx.setOpacity(0.0)
        self._fade = QPropertyAnimation(self._fx, b"opacity", self.status)
        self._fade.setEasingCurve(QEasingCurve.OutQuart)
        reset = QPushButton("Varsayılana dön")
        reset.setObjectName("secondary")
        reset.setCursor(Qt.PointingHandCursor)
        reset.clicked.connect(self.reset)
        save = QPushButton("Değişiklikleri kaydet")
        save.setObjectName("primary")
        save.setCursor(Qt.PointingHandCursor)
        save.clicked.connect(self.save)
        bar.addWidget(self.status, 1)
        bar.addWidget(reset)
        bar.addWidget(save)
        lay.addLayout(bar)
        lay.addStretch()
        self._weights_changed()

    @staticmethod
    def _cell(w: QWidget) -> QWidget:
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(w)
        box.inner = w
        return box

    def _weights_changed(self, *_):
        total = sum(sp.value() for sp in self.w_spins.values())
        ok = abs(total - 100) < 0.01
        self.w_total.setText(f"Toplam: %{total:.0f}" + ("  ✓" if ok else "  · %100 olmalı"))
        self.w_total.setStyleSheet(f"color: {G if ok else RED}; font-size: 13px; font-weight: 700; background: transparent;")

    def _toast(self, text: str, color: str):
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 600; background: transparent;")
        self._fade.stop()
        self._fade.setDuration(300)
        self._fade.setStartValue(self._fx.opacity())
        self._fade.setEndValue(1.0)
        self._fade.start()
        QTimer.singleShot(3200, self._hide_toast)

    def _hide_toast(self):
        self._fade.stop()
        self._fade.setDuration(700)
        self._fade.setStartValue(self._fx.opacity())
        self._fade.setEndValue(0.0)
        self._fade.start()

    def collect(self) -> Assumptions:
        a = Assumptions()
        a.emission_factor_kg_per_kwh = {UtilityType.ELECTRICITY: self.ef_e.value(), UtilityType.GAS: self.ef_g.value()}
        a.default_tariffs = {UtilityType.ELECTRICITY: self.t_e.value(), UtilityType.GAS: self.t_g.value(),
                             UtilityType.WATER: self.t_w.value()}
        a.benchmark_eui_kwh_m2, a.benchmark_carbon_kg_m2 = self.b_eui.value(), None
        a.benchmark_eui_by_use = {use: sp.value() for use, sp in self.b_use.items()}
        a.benchmark_water_m3_m2, a.equipment_life_years = self.b_w.value(), int(self.life.value())
        a.health_weights = {n: sp.value() / 100 for n, sp in self.w_spins.items()}
        a.discount_rate, a.energy_escalation = self.f_disc.value() / 100, self.f_esc.value() / 100
        a.horizon_years, a.savings_degradation = int(self.f_years.value()), self.f_deg.value() / 100
        return a

    def save(self):
        if abs(sum(sp.value() for sp in self.w_spins.values()) - 100) >= 0.01:
            self._toast("Health Score ağırlıklarının toplamı %100 olmalı.", RED)
            return
        self.store.save_assumptions(self.collect())
        opps = []
        for o, name, pct, capex in self.opp_widgets:
            o.name = name.text().strip() or o.name
            o.saving_pct = pct.value() / 100
            o.capex_per_m2 = capex.value()
            opps.append(o)
        self.store.save_opportunities(opps)
        self.on_saved()

    def reset(self):
        if QMessageBox.question(self.widget, "Varsayılana dön", "Tüm ayarlar ve öneri kataloğu varsayılan değerlere dönsün mü?") != QMessageBox.Yes:
            return
        self.store.reset_settings()
        self.on_saved()

    def saved_message(self):
        self._toast("Kaydedildi. Tüm hesaplar güncellendi.", G)
