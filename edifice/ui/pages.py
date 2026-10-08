from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
                               QPushButton, QScrollArea, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from ..models import UTILITY_UNITS, UtilityType
from ..service import Project
from .charts import BarChart
from .widgets import (ACCENT, GRADE_COLORS, INK, MUTED, SERIES_COLORS, Card, Gauge, Panel,
                      ScoreBar, fmt, fmt_years, grade_for, header, muted, score_color, section,
                      style_chart)

UTILITY_NAMES = {UtilityType.ELECTRICITY: "Elektrik", UtilityType.GAS: "Doğalgaz",
                 UtilityType.WATER: "Su"}
MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


def _page() -> tuple[QScrollArea, QVBoxLayout]:
    """Kaydırılabilir sayfa: dışta ScrollArea, içte dikey layout."""
    inner = QWidget()
    inner.setObjectName("page")
    lay = QVBoxLayout(inner)
    lay.setContentsMargins(36, 30, 36, 30)
    lay.setSpacing(18)
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(inner)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    return area, lay


def bar_chart(categories, groups, scale=1.0, label_format="%.0f", min_h=170, colors=None, unit=""):
    decimals = 1 if label_format == "%.1f" else 0
    return BarChart(categories, groups, scale=scale, decimals=decimals, colors=colors, unit=unit,
                    min_h=min_h)


def _table(headers: list[str], left_cols: int = 1) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels([h.upper() for h in headers])
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setShowGrid(False)
    t.setFocusPolicy(Qt.NoFocus)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(40)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    t.horizontalHeader().setHighlightSections(False)
    for c in range(len(headers)):
        t.horizontalHeaderItem(c).setTextAlignment(
            (Qt.AlignLeft if c < left_cols else Qt.AlignRight) | Qt.AlignVCenter)
    return t


def _set_row(t: QTableWidget, r: int, values: list[str], left_cols: int = 1, colors: dict | None = None):
    for c, v in enumerate(values):
        it = QTableWidgetItem(v)
        it.setTextAlignment((Qt.AlignLeft if c < left_cols else Qt.AlignRight) | Qt.AlignVCenter)
        if colors and c in colors:
            it.setForeground(QColor(colors[c]))
            f = it.font()
            f.setBold(True)
            it.setFont(f)
        t.setItem(r, c, it)


def _fit_height(t: QTableWidget, rows: int):
    t.setFixedHeight(46 + 40 * rows)


class OverviewPage:
    def __init__(self, project: Project):
        self.widget, lay = _page()
        b, k, h = project.building, project.kpis(), project.health()
        lay.addWidget(header("Genel bakış", b.name,
                             f"{b.address} · {b.use_type} · {fmt(b.floor_area_m2)} m² · {b.floors} kat · "
                             f"{b.year_built} · {b.occupants} kişi · Baz yıl {project.year}"))

        top = QHBoxLayout()
        top.setSpacing(18)
        score = Panel("Building Health Score", "Bileşenlerin ağırlıklı ortalaması")
        score.setMinimumWidth(430)
        score.lay.addWidget(Gauge(h.total, h.grade))
        for name, (pts, weight) in h.components.items():
            row = QHBoxLayout()
            lbl = QLabel(f"{name}  <span style='color:{MUTED}'>%{weight * 100:.0f}</span>")
            lbl.setMinimumWidth(190)
            row.addWidget(lbl)
            row.addWidget(ScoreBar(pts), 1)
            score.lay.addLayout(row)
        top.addWidget(score, 4)

        grid = QGridLayout()
        grid.setSpacing(16)
        specs = [
            ("Toplam enerji", k.total_energy_kwh / 1000, lambda v: f"{fmt(v)} MWh",
             f"EUI {fmt(k.eui_kwh_m2, 1)} kWh/m²·yıl"),
            ("Karbon", k.carbon_kg / 1000, lambda v: f"{fmt(v, 1)} tCO₂",
             f"{fmt(k.carbon_kg_m2, 1)} kgCO₂/m²·yıl"),
            ("Su", k.water_m3, lambda v: f"{fmt(v)} m³", f"{fmt(k.water_m3_m2, 2)} m³/m²·yıl"),
            ("Elektrik", k.electricity_kwh / 1000, lambda v: f"{fmt(v)} MWh",
             f"%{fmt(100 * k.electricity_kwh / k.total_energy_kwh)} enerji payı"),
            ("Doğalgaz", k.gas_kwh / 1000, lambda v: f"{fmt(v)} MWh",
             f"%{fmt(100 * k.gas_kwh / k.total_energy_kwh)} enerji payı"),
            ("Yıllık toplam maliyet", k.total_cost / 1e6, lambda v: f"{fmt(v, 2)} M ₺",
             f"enerji {fmt(k.energy_cost / 1e6, 2)} M ₺ + su"),
        ]
        for i, (title, val, f, sub) in enumerate(specs):
            c = Card(title, sub=sub, hero=(i == 0))
            c.set_number(val, f, sub)
            grid.addWidget(c, i // 2, i % 2)
        top.addLayout(grid, 5)
        lay.addLayout(top)

        cost: dict[str, list[float]] = {}
        for r in sorted(project.readings, key=lambda r: (r.year, r.month)):
            if r.utility != UtilityType.WATER:
                cost.setdefault(str(r.year), [0.0] * 12)[r.month - 1] += r.cost
        panel = Panel("Aylık enerji maliyeti", "Bin ₺, yıllar yan yana")
        panel.lay.addWidget(bar_chart(MONTHS, cost, scale=1000, min_h=210, unit="bin ₺"), 1)
        lay.addWidget(panel, 1)


class ConsumptionPage:
    def __init__(self, project: Project):
        self.widget, lay = _page()
        lay.addWidget(header("Tüketim takibi", "Elektrik, doğalgaz ve su",
                             "Fatura verisinden aylık tüketim; yıllar yan yana karşılaştırılır."))
        scale = {UtilityType.ELECTRICITY: (1000, "MWh"), UtilityType.GAS: (1000, "MWh"),
                 UtilityType.WATER: (1, "m³")}
        for u in UtilityType:
            groups: dict[str, list[float]] = {}
            for r in sorted(project.readings, key=lambda r: (r.year, r.month)):
                if r.utility == u:
                    groups.setdefault(str(r.year), []).append(r.consumption)
            sc, unit = scale[u]
            panel = Panel(UTILITY_NAMES[u], f"Aylık tüketim · {unit}")
            panel.lay.addWidget(bar_chart(MONTHS, groups, scale=sc, min_h=170, unit=unit), 1)
            lay.addWidget(panel, 1)


class OpportunitiesPage:
    def __init__(self, project: Project):
        self.widget, lay = _page()
        lay.addWidget(header("Dönüşüm önerileri", "Fırsatlar",
                             "Geri ödeme süresine göre sıralı. Tasarruf oranları ve birim maliyetler "
                             "varsayımdır, pilot bina etüdüyle güncellenecek."))
        res = project.opportunity_results()
        quick = [r for r in res if r.payback_years <= 5]
        grid = QGridLayout()
        grid.setSpacing(16)
        c1 = Card("Öneri sayısı")
        c1.set_number(len(res), lambda v: f"{v:.0f}", f"{len(quick)} tanesi 5 yıl altında geri ödüyor")
        c2 = Card("Hızlı kazanç · yıllık tasarruf", hero=True)
        c2.set_number(sum(r.annual_saving for r in quick) / 1e6, lambda v: f"{fmt(v, 2)} M ₺",
                      "geri ödemesi ≤ 5 yıl olanlar")
        c3 = Card("Hızlı kazanç · CAPEX")
        c3.set_number(sum(r.capex for r in quick) / 1e6, lambda v: f"{fmt(v, 2)} M ₺", "gerekli yatırım")
        for i, c in enumerate((c1, c2, c3)):
            grid.addWidget(c, 0, i)
        lay.addLayout(grid)

        t = _table(["Öneri", "Kategori", "Enerji kWh/yıl", "Karbon kg/yıl",
                    "Tasarruf ₺/yıl", "CAPEX ₺", "Geri ödeme"], left_cols=2)
        t.setRowCount(len(res))
        for i, r in enumerate(res):
            pb = r.payback_years
            col = GRADE_COLORS["A"] if pb <= 5 else GRADE_COLORS["C"] if pb <= 15 else GRADE_COLORS["E"]
            _set_row(t, i, [r.opportunity.name, r.opportunity.category, fmt(r.saved_kwh),
                            fmt(r.saved_carbon_kg), fmt(r.annual_saving), fmt(r.capex),
                            fmt_years(pb)], left_cols=2, colors={6: col})
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        _fit_height(t, len(res))
        panel = Panel()
        panel.lay.addWidget(t)
        lay.addWidget(panel)

        chart_panel = Panel("Tasarruf ve yatırım", "Milyon ₺")
        chart_panel.lay.addWidget(bar_chart(
            [r.opportunity.name for r in res],
            {"Yıllık tasarruf": [r.annual_saving for r in res], "CAPEX": [r.capex for r in res]},
            scale=1e6, label_format="%.1f", min_h=230, colors=["emerald", "gold"], unit="M ₺"), 1)
        lay.addWidget(chart_panel, 1)


class ScenarioPage:
    def __init__(self, project: Project):
        self.project = project
        self.widget, lay = _page()
        lay.addWidget(header("Senaryo", "Mevcut vs Hedef",
                             "Uygulanacak önerileri seçin; hedef durum anında hesaplanır."))
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
            btn.toggled.connect(self.refresh)
            self.checks[o.code] = btn
            left.addWidget(btn)
        left.addStretch()
        lw = QWidget()
        lw.setLayout(left)
        lw.setFixedWidth(360)
        body.addWidget(lw)

        right = QVBoxLayout()
        right.setSpacing(16)
        grid = QGridLayout()
        grid.setSpacing(16)
        self.c_capex = Card("Toplam CAPEX")
        self.c_save = Card("Yıllık tasarruf", hero=True)
        self.c_pay = Card("Geri ödeme süresi")
        self.c_co2 = Card("Karbon azalımı")
        for i, c in enumerate((self.c_capex, self.c_save, self.c_pay, self.c_co2)):
            grid.addWidget(c, i // 2, i % 2)
        right.addLayout(grid)
        self.table = _table(["Gösterge", "Mevcut", "Hedef", "Değişim"])
        _fit_height(self.table, 5)
        tp = Panel()
        tp.lay.addWidget(self.table)
        right.addWidget(tp)
        body.addLayout(right, 1)
        lay.addLayout(body)

        self.chart_panel = Panel("Mevcut vs Hedef", "Mevcut durum = 100")
        self.chart_box = QVBoxLayout()
        self.chart_panel.lay.addLayout(self.chart_box, 1)
        lay.addWidget(self.chart_panel, 1)
        self.refresh()

    def selected_codes(self) -> list[str]:
        return [c for c, cb in self.checks.items() if cb.isChecked()]

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
                     colors={3: GRADE_COLORS["A"] if pct < -0.05 else MUTED})

        while self.chart_box.count():
            old = self.chart_box.takeAt(0).widget()
            old.setParent(None)
            old.deleteLater()
        self.chart_box.addWidget(bar_chart(
            ["Elektrik", "Doğalgaz", "Enerji", "Karbon", "Maliyet"],
            {"Mevcut": [100] * 5,
             "Hedef": [100 * t.electricity_kwh / c.electricity_kwh, 100 * t.gas_kwh / c.gas_kwh,
                       100 * t.total_energy_kwh / c.total_energy_kwh,
                       100 * t.carbon_kg / c.carbon_kg, 100 * t.total_cost / c.total_cost]},
            min_h=210, colors=["slate", "emerald"], unit="(%)"))

        self.c_capex.set_number(s.capex / 1e6, lambda v: f"{fmt(v, 2)} M ₺", "toplam yatırım", live=True)
        self.c_save.set_number(s.annual_saving / 1e6, lambda v: f"{fmt(v, 2)} M ₺", "her yıl", live=True)
        pb = s.payback_years if s.payback_years != float("inf") else 0.0
        self.c_pay.set_number(pb, lambda v: f"{fmt(v, 1)} yıl" if v > 0.05 else "-", "basit geri ödeme", live=True)
        self.c_co2.set_number(s.carbon_reduction_pct * 100, lambda v: f"%{fmt(v, 1)}",
                              f"enerji %{fmt(s.energy_reduction_pct * 100, 1)} azalır", live=True)
