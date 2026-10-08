from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QSizePolicy, QSlider, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
                               QPushButton, QScrollArea, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from ..engine.rating import CLASS_COLORS, z_of
from ..engine.relevance import LABELS as FIT_LABELS
from ..models import UTILITY_UNITS, UtilityType
from ..service import Project
from .charts import AreaChart, BarChart, CashFlowChart, ClassScale, PercentileBar
from .forms import SmoothSelectTable
from .widgets import (AMBER, G, GRADE_COLORS, INDIGO, MUTED, RED, SUB, TEXT, Card, Gauge, Panel, ScoreBar, badge,
                      fmt, fmt_years, header, muted, qfont, section)

UTILITY_NAMES = {UtilityType.ELECTRICITY: "Elektrik", UtilityType.GAS: "Doğalgaz", UtilityType.WATER: "Su"}
MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


def _page() -> tuple[QScrollArea, QVBoxLayout]:
    inner = QWidget()
    inner.setObjectName("page")
    lay = QVBoxLayout(inner)
    lay.setContentsMargins(32, 26, 32, 36)
    lay.setSpacing(18)
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(inner)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    return area, lay


def area_chart(categories, groups, scale=1.0, decimals=0, colors=None, unit="", min_h=170):
    return AreaChart(categories, groups, scale=scale, decimals=decimals, colors=colors, unit=unit, min_h=min_h)


def bar_chart(categories, groups, scale=1.0, decimals=0, colors=None, unit="", min_h=170):
    return BarChart(categories, groups, scale=scale, decimals=decimals, colors=colors, unit=unit, min_h=min_h)


def _table(headers: list[str], left_cols: int = 1) -> QTableWidget:
    t = SmoothSelectTable(0, len(headers))
    t.setHorizontalHeaderLabels([h.upper() for h in headers])
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setShowGrid(False)
    t.setFocusPolicy(Qt.NoFocus)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(46)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    t.horizontalHeader().setHighlightSections(False)
    for c in range(len(headers)):
        t.horizontalHeaderItem(c).setTextAlignment((Qt.AlignLeft if c < left_cols else Qt.AlignRight) | Qt.AlignVCenter)
    return t


def _set_row(t, r, values, left_cols=1, colors=None, mono_from=2):
    for c, v in enumerate(values):
        it = QTableWidgetItem(v)
        it.setTextAlignment((Qt.AlignLeft if c < left_cols else Qt.AlignRight) | Qt.AlignVCenter)
        if c >= mono_from:
            it.setFont(qfont(13, mono=True))
        if c == 0:
            f = qfont(13, 700)
            it.setFont(f)
        if colors and c in colors:
            it.setForeground(QColor(colors[c]))
            f = it.font()
            f.setBold(True)
            it.setFont(f)
        t.setItem(r, c, it)


def _fit_height(t: QTableWidget, rows: int):
    t.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    t.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    t.setFixedHeight(48 + 46 * rows)


def _years(project, now: list, prev: list) -> dict:
    """Önceki yıl verisi yoksa tek seri döndürür (sıfır çizgisi göstermez)."""
    groups = {str(project.year): now}
    if project.previous_year() is not None:
        groups[str(project.year - 1)] = prev
    return groups


FIT_COLORS = {"high": G, "medium": GRADE_COLORS["B"], "low": AMBER, "none": RED, "unknown": SUB}


def _trend_text(pct: float) -> tuple[str, bool]:
    arrow = "↓" if pct < 0 else "↑"
    return f"{arrow} {fmt(abs(pct), 1)}%", pct <= 0  # azalma = iyi


class OverviewPage:
    def __init__(self, project: Project):
        self.widget, lay = _page()
        b, k, h = project.building, project.kpis(), project.health()
        yoy = project.yoy()
        lay.addWidget(header("Genel bakış", b.name,
                             f"{b.address} · {b.use_type} · {fmt(b.floor_area_m2)} m² · {b.floors} kat · "
                             f"{b.year_built} · {b.occupants} kişi · Baz yıl {project.year}"))

        row = QGridLayout()
        row.setSpacing(16)
        specs = [
            ("Toplam enerji", k.total_energy_kwh / 1000, lambda v: f"{fmt(v)} MWh", f"EUI {fmt(k.eui_kwh_m2, 1)}", "energy", G),
            ("Karbon", k.carbon_kg / 1000, lambda v: f"{fmt(v, 1)} tCO₂", f"{fmt(k.carbon_kg_m2, 1)} kg/m²", "carbon", G),
            ("Elektrik", k.electricity_kwh / 1000, lambda v: f"{fmt(v)} MWh", f"%{fmt(100 * k.electricity_kwh / k.total_energy_kwh)} pay", "electricity", AMBER),
            ("Doğalgaz", k.gas_kwh / 1000, lambda v: f"{fmt(v)} MWh", f"%{fmt(100 * k.gas_kwh / k.total_energy_kwh)} pay", "gas", INDIGO),
            ("Su", k.water_m3, lambda v: f"{fmt(v)} m³", f"{fmt(k.water_m3_m2, 2)} m³/m²", "water", INDIGO),
            ("Yıllık maliyet", k.total_cost / 1e6, lambda v: f"{fmt(v, 2)} M ₺", "enerji + su", "cost", AMBER),
        ]
        for idx, (title, val, f, sub, key, accent) in enumerate(specs):
            c = Card(title, sub=sub, accent=accent)
            c.set_number(val, f, sub)
            if key in yoy:
                txt, good = _trend_text(yoy[key])
                c.set_trend(txt, good)
            row.addWidget(c, idx // 3, idx % 3)
        lay.addLayout(row)

        mid = QHBoxLayout()
        mid.setSpacing(18)
        score = Panel(eyebrow="Building Health", title="Bina skoru")
        score.setFixedWidth(340)
        score.lay.addWidget(Gauge(h.total, h.grade))
        score.lay.addSpacing(6)
        for name, (pts, weight) in h.components.items():
            r = QVBoxLayout()
            r.setSpacing(2)
            top = QHBoxLayout()
            nm = QLabel(f"{name} <span style='color:{MUTED}; font-size:11px'>%{weight * 100:.0f}</span>")
            nm.setStyleSheet("font-size: 13px; font-weight: 600;")
            top.addWidget(nm)
            r.addLayout(top)
            r.addWidget(ScoreBar(pts))
            score.lay.addLayout(r)
        mid.addWidget(score)

        prev = project.previous_year()
        cost_now, cost_prev = project.monthly_cost(project.year), project.monthly_cost(project.year - 1)
        chart_panel = Panel(eyebrow="Aylık maliyet", title=f"Enerji maliyeti · {project.year}",
                            subtitle=f"{fmt(sum(cost_now) / 1e6, 2)} M ₺ yıllık · bin ₺ cinsinden aylık")
        chart_panel.lay.addWidget(area_chart(MONTHS, _years(project, cost_now, cost_prev),
                                             scale=1000, unit="bin ₺", min_h=300), 1)
        mid.addWidget(chart_panel, 1)
        lay.addLayout(mid)

        rating = project.rating()
        after_codes = project.applicable_codes()
        after = project.rating_after(after_codes) if after_codes else None
        rp = Panel(eyebrow="Enerji performansı", title="Enerji sınıfı ve benzer binalarla kıyas",
                   subtitle="Tahmini sınıf: enerji yoğunluğu (EUI) ayarlardaki kıyas değerine oranlanır. Resmi enerji kimlik belgesi değildir.")
        rrow = QHBoxLayout()
        rrow.setSpacing(28)
        left = QVBoxLayout()
        left.addWidget(ClassScale(rating["class"], after))
        if after and after != rating["class"]:
            note = QLabel(f"Tüm uygun öneriler uygulanırsa <b style='color:{CLASS_COLORS[after]}'>{rating['class']} → {after}</b>")
            note.setStyleSheet(f"color: {SUB}; font-size: 13px; background: transparent;")
            left.addWidget(note)
        left.addStretch()
        rrow.addLayout(left, 5)
        right = QVBoxLayout()
        pct = rating["percentile"]
        worse = pct >= 50
        big = QLabel(f"%{fmt(pct if worse else 100 - pct)}")
        big.setStyleSheet(f"color: {RED if pct >= 65 else AMBER if pct >= 35 else G}; font-size: 38px; font-weight: 500; "
                          "font-family: 'DM Mono','SF Mono',Menlo,monospace; background: transparent;")
        cap = QLabel(f"benzer {project.building.use_type.lower()} binasından <b>{'daha fazla' if worse else 'daha az'}</b> enerji tüketiyor "
                     f"(EUI {fmt(rating['eui'], 0)} · kıyas {fmt(rating['benchmark'], 0)} kWh/m²·yıl)")
        cap.setWordWrap(True)
        cap.setStyleSheet(f"color: {SUB}; font-size: 13px; background: transparent;")
        right.addWidget(big)
        right.addWidget(cap)
        right.addWidget(PercentileBar(z_of(rating["eui"], rating["benchmark"]), pct))
        right.addStretch()
        rrow.addLayout(right, 4)
        rp.lay.addLayout(rrow)
        rp.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        lay.addWidget(rp)

        bottom = QHBoxLayout()
        bottom.setSpacing(18)
        recs = Panel(eyebrow="EDIFI'CE öneri motoru", title="Öne çıkan fırsatlar")
        recs.setFixedWidth(340)
        for r in [r for r in project.opportunity_results() if r.fit != "none"][:3]:
            pb = r.payback_years
            col = G if pb <= 5 else AMBER if pb <= 15 else RED
            qc = QColor(col)
            card = QWidget()
            card.setObjectName("rec")
            card.setStyleSheet(f"QWidget#rec {{ background: rgba({qc.red()},{qc.green()},{qc.blue()},0.04);"
                               f"border: 1px solid rgba({qc.red()},{qc.green()},{qc.blue()},0.13); border-radius: 12px; }}")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 12, 14, 12)
            cl.setSpacing(4)
            top = QHBoxLayout()
            top.addWidget(badge("Hızlı kazanç" if pb <= 5 else "Orta vade" if pb <= 15 else "Uzun vade", col))
            top.addStretch()
            sv = QLabel(f"{fmt(r.annual_saving / 1000)} bin ₺/yıl")
            sv.setStyleSheet(f"color: {G}; font-family: 'DM Mono','SF Mono',Menlo; font-size: 13px; background: transparent;")
            top.addWidget(sv)
            cl.addLayout(top)
            t = QLabel(r.opportunity.name)
            t.setWordWrap(True)
            t.setStyleSheet("font-size: 13px; font-weight: 700; background: transparent;")
            d = QLabel(f"CAPEX {fmt(r.capex / 1e6, 2)} M ₺ · geri ödeme {fmt_years(pb)}")
            d.setWordWrap(True)
            d.setStyleSheet(f"color: {SUB}; font-size: 12px; background: transparent;")
            cl.addWidget(t)
            cl.addWidget(d)
            recs.lay.addWidget(card)
        recs.lay.addStretch()
        bottom.addWidget(recs)

        en = Panel(eyebrow="Tüketim", title="Enerji tüketimi", subtitle="MWh · elektrik + doğalgaz")
        e_now = [a + b for a, b in zip(project.monthly(project.year, UtilityType.ELECTRICITY), project.monthly(project.year, UtilityType.GAS))]
        e_prev = [a + b for a, b in zip(project.monthly(project.year - 1, UtilityType.ELECTRICITY), project.monthly(project.year - 1, UtilityType.GAS))]
        en.lay.addWidget(area_chart(MONTHS, _years(project, e_now, e_prev), scale=1000, unit="MWh", min_h=210), 1)
        bottom.addWidget(en, 1)

        co = Panel(eyebrow="Karbon", title="Karbon salımı", subtitle="tCO₂ · aylık")
        c_now, c_prev = project.monthly_carbon(project.year), project.monthly_carbon(project.year - 1)
        co.lay.addWidget(area_chart(MONTHS, _years(project, c_now, c_prev), scale=1000,
                                    decimals=0, colors=["green", "indigo"], unit="tCO₂", min_h=210), 1)
        bottom.addWidget(co, 1)
        lay.addLayout(bottom)


class ConsumptionPage:
    def __init__(self, project: Project):
        self.widget, lay = _page()
        lay.addWidget(header("Tüketim takibi", "Elektrik, doğalgaz ve su",
                             "Fatura verisinden aylık tüketim; bir önceki yıl ile karşılaştırılır."))
        scale = {UtilityType.ELECTRICITY: (1000, "MWh"), UtilityType.GAS: (1000, "MWh"), UtilityType.WATER: (1, "m³")}
        for u in UtilityType:
            sc, unit = scale[u]
            now, prev = project.monthly(project.year, u), project.monthly(project.year - 1, u)
            panel = Panel(eyebrow=UTILITY_NAMES[u], title=f"{fmt(sum(now) / sc, 0)} {unit}",
                          subtitle=f"{project.year} yıllık toplam · aylık dağılım")
            panel.lay.addWidget(area_chart(MONTHS, _years(project, now, prev),
                                           scale=sc, unit=unit, min_h=170,
                                           colors=["green", "indigo"] if u != UtilityType.WATER else ["indigo", "amber"]), 1)
            lay.addWidget(panel, 1)


class OpportunitiesPage:
    def __init__(self, project: Project):
        self.widget, lay = _page()
        lay.addWidget(header("Dönüşüm önerileri", "Fırsatlar",
                             "Geri ödeme süresine göre sıralı. Tasarruf oranları ve birim maliyetler varsayımdır, "
                             "pilot bina etüdüyle güncellenecek."))
        res = project.opportunity_results()
        quick = [r for r in res if r.payback_years <= 5]
        grid = QHBoxLayout()
        grid.setSpacing(16)
        c1 = Card("Öneri sayısı", accent=G)
        c1.set_number(len(res), lambda v: f"{v:.0f}", f"{len(quick)} tanesi 5 yıl altında geri ödüyor")
        c2 = Card("Hızlı kazanç · yıllık tasarruf", accent=G)
        c2.set_number(sum(r.annual_saving for r in quick) / 1e6, lambda v: f"{fmt(v, 2)} M ₺", "geri ödemesi ≤ 5 yıl")
        c3 = Card("Hızlı kazanç · CAPEX", accent=AMBER)
        c3.set_number(sum(r.capex for r in quick) / 1e6, lambda v: f"{fmt(v, 2)} M ₺", "gerekli yatırım")
        for c in (c1, c2, c3):
            grid.addWidget(c)
        lay.addLayout(grid)

        t = _table(["Öneri", "Kategori", "Uygunluk", "Enerji kWh/yıl", "Karbon kg/yıl", "Tasarruf ₺/yıl", "CAPEX ₺", "Geri ödeme"], left_cols=3)
        t.setRowCount(len(res))
        for i, r in enumerate(res):
            pb = r.payback_years
            col = G if pb <= 5 else AMBER if pb <= 15 else RED
            _set_row(t, i, [r.opportunity.name, r.opportunity.category, FIT_LABELS[r.fit], fmt(r.saved_kwh),
                            fmt(r.saved_carbon_kg), fmt(r.annual_saving), fmt(r.capex), fmt_years(pb)],
                     left_cols=3, colors={2: FIT_COLORS[r.fit], 7: col}, mono_from=3)
            t.item(i, 1).setForeground(QColor(SUB))
            t.item(i, 1).setFont(qfont(13))
            t.item(i, 2).setFont(qfont(13, 700))
            for c in range(8):
                t.item(i, c).setToolTip(r.reason or "")
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        _fit_height(t, len(res))
        panel = Panel()
        panel.lay.addWidget(t)
        lay.addWidget(panel)

        cp = Panel(eyebrow="Karşılaştırma", title="Tasarruf ve yatırım", subtitle="milyon ₺")
        cp.lay.addWidget(bar_chart([r.opportunity.name for r in res],
                                   {"Yıllık tasarruf": [r.annual_saving for r in res], "CAPEX": [r.capex for r in res]},
                                   scale=1e6, decimals=1, colors=["green", "amber"], unit="M ₺", min_h=240), 1)
        lay.addWidget(cp, 1)


class ScenarioPage:
    def __init__(self, project: Project, store=None):
        self.project, self.store = project, store
        self.widget, lay = _page()
        lay.addWidget(header("Senaryo", "Mevcut vs Hedef", "Uygulanacak önerileri seçin; hedef durum anında hesaplanır."))
        total_capex = sum(o.capex_per_m2 for o in project.opportunities) * project.building.floor_area_m2
        self.slider_max = int(-(-total_capex // 50_000) * 50_000) or 50_000
        sim = Panel("Bütçe simülatörü", "Bütçeyi kaydırın: o bütçeyle en yüksek net bugünkü değeri (NPV) veren öneri paketi otomatik seçilir.")
        srow = QHBoxLayout()
        srow.setSpacing(18)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, self.slider_max // 50_000)
        self.slider.setCursor(Qt.PointingHandCursor)
        self.slider.setMinimumHeight(34)
        self.budget_lbl = QLabel("0 ₺")
        self.budget_lbl.setMinimumWidth(150)
        self.budget_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.budget_lbl.setStyleSheet("font-size: 26px; font-weight: 500; font-family: 'DM Mono','SF Mono',Menlo,monospace; background: transparent;")
        srow.addWidget(self.slider, 1)
        srow.addWidget(self.budget_lbl)
        sim.lay.addSpacing(6)
        sim.lay.addLayout(srow)
        self.sim_note = QLabel("")
        self.sim_note.setWordWrap(True)
        self.sim_note.setStyleSheet(f"color: {SUB}; font-size: 13px; background: transparent;")
        sim.lay.addWidget(self.sim_note)
        lay.addWidget(sim)
        self.slider.valueChanged.connect(self._slider_moved)

        body = QHBoxLayout()
        body.setSpacing(18)

        left = QVBoxLayout()
        left.setSpacing(10)
        left.addWidget(section("Önerileri seç"))
        self.checks: dict[str, QPushButton] = {}
        res = {r.opportunity.code: r for r in project.opportunity_results()}
        for o in project.opportunities:
            r = res[o.code]
            btn = QPushButton(f"{o.name}\n%{o.saving_pct * 100:.0f} {UTILITY_NAMES[o.affects].lower()} · "
                              f"{fmt(r.capex / 1e6, 2)} M ₺ · {fmt_years(r.payback_years)}")
            btn.setObjectName("toggle")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(64)
            btn.setToolTip(r.reason or "")
            if r.fit == "none":
                btn.setText(btn.text() + "  ·  uygun değil")
            btn.toggled.connect(self._toggled)
            self.checks[o.code] = btn
            left.addWidget(btn)
        left.addStretch()
        lw = QWidget()
        lw.setLayout(left)
        lw.setFixedWidth(340)
        body.addWidget(lw)

        right = QVBoxLayout()
        right.setSpacing(14)
        grid = QGridLayout()
        grid.setSpacing(14)
        self.c_capex = Card("Toplam CAPEX", accent=AMBER)
        self.c_save = Card("Yıllık tasarruf", accent=G)
        self.c_pay = Card("Geri ödeme süresi", accent=INDIGO)
        self.c_co2 = Card("Karbon azalımı", accent=G)
        for i, c in enumerate((self.c_capex, self.c_save, self.c_pay, self.c_co2)):
            grid.addWidget(c, 0, i)
        right.addLayout(grid)
        self.table = _table(["Gösterge", "Mevcut", "Hedef", "Değişim"])
        _fit_height(self.table, 5)
        tp = Panel()
        tp.lay.addWidget(self.table)
        right.addWidget(tp)
        body.addLayout(right, 1)
        lay.addLayout(body)

        a = project.assumptions
        self.fin_panel = Panel(eyebrow="Finansal analiz", title=f"{a.horizon_years} yıllık nakit akışı",
                               subtitle=f"Reel (enflasyondan arındırılmış) değerler · iskonto %{fmt(a.discount_rate * 100, 1)} · enerji fiyat artışı %{fmt(a.energy_escalation * 100, 1)} · "
                                        f"tasarruf kaybı %{fmt(a.savings_degradation * 100, 1)}/yıl")
        frow = QHBoxLayout()
        frow.setSpacing(14)
        self.f_npv = Card("Net bugünkü değer (NPV)", accent=G)
        self.f_irr = Card("İç verim oranı (IRR)", accent=INDIGO)
        self.f_dpb = Card("İndirgenmiş geri ödeme", accent=AMBER)
        self.f_net = Card("Toplam net kazanç", accent=G)
        for c in (self.f_npv, self.f_irr, self.f_dpb, self.f_net):
            frow.addWidget(c)
        self.fin_panel.lay.addSpacing(6)
        self.fin_panel.lay.addLayout(frow)
        self.cash_chart = CashFlowChart(list(range(a.horizon_years + 1)), [0.0] * (a.horizon_years + 1), None, min_h=250)
        self.fin_panel.lay.addWidget(self.cash_chart, 1)
        lay.addWidget(self.fin_panel)

        self.chart_panel = Panel(eyebrow="Karşılaştırma", title="Mevcut vs Hedef", subtitle="mevcut durum = 100")
        self.chart = BarChart(["Elektrik", "Doğalgaz", "Enerji", "Karbon", "Maliyet"],
                              {"Mevcut": [100] * 5, "Hedef": [100] * 5}, min_h=230,
                              colors=["slate", "green"], unit="%", fixed_max=100)
        self.chart_panel.lay.addWidget(self.chart, 1)
        lay.addWidget(self.chart_panel)
        if store is not None and project.building_id is not None:
            for code in store.load_scenario(project.building_id):
                if code in self.checks:
                    self.checks[code].blockSignals(True)
                    self.checks[code].setChecked(True)
                    self.checks[code].blockSignals(False)
        self.refresh()

    def selected_codes(self) -> list[str]:
        return [c for c, cb in self.checks.items() if cb.isChecked()]

    def _slider_moved(self, v: int):
        budget = v * 50_000
        self.budget_lbl.setText(f"{fmt(budget / 1e6, 2)} M ₺")
        codes, fin = self.project.best_package(budget)
        for code, btn in self.checks.items():
            btn.blockSignals(True)
            btn.setChecked(code in codes)
            btn.blockSignals(False)
        if codes:
            names = ", ".join(o.name for o in self.project.opportunities if o.code in codes)
            self.sim_note.setText(f"En iyi paket: {names}  ·  CAPEX {fmt(fin.capex / 1e6, 2)} M ₺  ·  NPV {fmt(fin.npv / 1e6, 2)} M ₺")
        else:
            self.sim_note.setText("Bu bütçeyle net bugünkü değeri pozitif bir paket yok; bütçeyi artırın." if budget else "Bütçeyi kaydırın.")
        self._toggled()

    def _toggled(self, *_):
        if self.store is not None and self.project.building_id is not None:
            self.store.save_scenario(self.project.building_id, self.selected_codes())
        self.refresh()

    def refresh(self, *_):
        s = self.project.scenario(self.selected_codes())
        c, t = s.current, s.target
        rows = [
            ("Elektrik (MWh)", c.electricity_kwh / 1000, t.electricity_kwh / 1000, 0),
            ("Doğalgaz (MWh)", c.gas_kwh / 1000, t.gas_kwh / 1000, 0),
            ("EUI (kWh/m²·yıl)", c.eui_kwh_m2, t.eui_kwh_m2, 1),
            ("Karbon (tCO₂)", c.carbon_kg / 1000, t.carbon_kg / 1000, 1),
            ("Yıllık maliyet (M ₺)", c.total_cost / 1e6, t.total_cost / 1e6, 2),
        ]
        self.table.setRowCount(len(rows))
        for i, (name, cur, tgt, d) in enumerate(rows):
            pct = (tgt / cur - 1) * 100 if cur else 0
            _set_row(self.table, i, [name, fmt(cur, d), fmt(tgt, d), f"{pct:+.1f}%".replace(".", ",")],
                     colors={3: G if pct < -0.05 else MUTED}, mono_from=1)

        self.chart.update_data(
            {"Mevcut": [100] * 5,
             "Hedef": [100 * t.electricity_kwh / c.electricity_kwh, 100 * t.gas_kwh / c.gas_kwh,
                       100 * t.total_energy_kwh / c.total_energy_kwh, 100 * t.carbon_kg / c.carbon_kg,
                       100 * t.total_cost / c.total_cost]})

        fin = self.project.finance(self.selected_codes())
        pb = fin.simple_payback if fin.simple_payback != float("inf") else None
        self.cash_chart.update_data(fin.cumulative, pb)
        self.f_npv.set_number(fin.npv / 1e6, lambda v: f"{fmt(v, 2)} M ₺", "bugünkü değerle", live=True,
                              color=None if fin.npv >= 0 else RED)
        if fin.irr is None:
            self.f_irr.set("-", "tanımsız")
        else:
            self.f_irr.set_number(fin.irr * 100, lambda v: f"%{fmt(v, 1)}", f"iskonto %{fmt(self.project.assumptions.discount_rate * 100, 0)} üstünde" if fin.irr > self.project.assumptions.discount_rate else "iskontonun altında", live=True)
        if fin.discounted_payback is None:
            self.f_dpb.set("-", "analiz süresinde dönmüyor")
        else:
            self.f_dpb.set_number(fin.discounted_payback, lambda v: f"{fmt(v, 1)} yıl", "iskontolu", live=True)
        self.f_net.set_number(fin.total_net / 1e6, lambda v: f"{fmt(v, 2)} M ₺", f"{self.project.assumptions.horizon_years} yıl sonunda", live=True,
                              color=None if fin.total_net >= 0 else RED)
        self.c_capex.set_number(s.capex / 1e6, lambda v: f"{fmt(v, 2)} M ₺", "toplam yatırım", live=True)
        self.c_save.set_number(s.annual_saving / 1e6, lambda v: f"{fmt(v, 2)} M ₺", "her yıl", live=True)
        pb = s.payback_years if s.payback_years != float("inf") else 0.0
        self.c_pay.set_number(pb, lambda v: f"{fmt(v, 1)} yıl" if v > 0.05 else "-", "basit geri ödeme", live=True)
        self.c_co2.set_number(s.carbon_reduction_pct * 100, lambda v: f"%{fmt(v, 1)}",
                              f"enerji %{fmt(s.energy_reduction_pct * 100, 1)} azalır", live=True)
