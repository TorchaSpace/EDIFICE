from __future__ import annotations

from PySide6.QtCharts import (QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView,
                              QValueAxis)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QGridLayout, QHBoxLayout,
                               QHeaderView, QLabel, QProgressBar, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..engine.kpi import monthly_series
from ..models import UTILITY_UNITS, UtilityType
from ..service import Project
from .widgets import ACCENT, GRADE_COLORS, Card, fmt, fmt_years, h1, muted

UTILITY_NAMES = {UtilityType.ELECTRICITY: "Elektrik", UtilityType.GAS: "Doğalgaz",
                 UtilityType.WATER: "Su"}


def _page() -> tuple[QWidget, QVBoxLayout]:
    w = QWidget()
    w.setObjectName("page")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(28, 24, 28, 24)
    lay.setSpacing(14)
    return w, lay


def _table(headers: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.verticalHeader().setVisible(False)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    return t


def _set_row(t: QTableWidget, r: int, values: list[str], right_from: int = 2):
    for c, v in enumerate(values):
        it = QTableWidgetItem(v)
        if c >= right_from:
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        t.setItem(r, c, it)


class OverviewPage:
    def __init__(self, project: Project):
        self.widget, lay = _page()
        b, k, h = project.building, project.kpis(), project.health()
        lay.addWidget(h1(b.name))
        lay.addWidget(muted(f"{b.address} · {b.use_type} · {fmt(b.floor_area_m2)} m² · "
                            f"{b.floors} kat · {b.year_built} · {b.occupants} kişi · "
                            f"Baz yıl: {project.year}"))

        grid = QGridLayout()
        grid.setSpacing(12)
        score = Card("Building Health Score", f"{h.total:.0f} / 100", f"Not: {h.grade}")
        score.set(f"{h.total:.0f} / 100", f"Not: {h.grade}", GRADE_COLORS[h.grade])
        cards = [
            score,
            Card("Toplam enerji", f"{fmt(k.total_energy_kwh / 1000)} MWh",
                 f"EUI {fmt(k.eui_kwh_m2, 1)} kWh/m²·yıl"),
            Card("Karbon", f"{fmt(k.carbon_kg / 1000, 1)} tCO₂",
                 f"{fmt(k.carbon_kg_m2, 1)} kgCO₂/m²·yıl"),
            Card("Su", f"{fmt(k.water_m3)} m³", f"{fmt(k.water_m3_m2, 2)} m³/m²·yıl"),
            Card("Elektrik", f"{fmt(k.electricity_kwh / 1000)} MWh", ""),
            Card("Doğalgaz", f"{fmt(k.gas_kwh / 1000)} MWh", ""),
            Card("Yıllık enerji maliyeti", f"{fmt(k.energy_cost / 1e6, 2)} M ₺", ""),
            Card("Yıllık toplam maliyet", f"{fmt(k.total_cost / 1e6, 2)} M ₺", "enerji + su"),
        ]
        for i, c in enumerate(cards):
            grid.addWidget(c, i // 4, i % 4)
        lay.addLayout(grid)

        lay.addWidget(QLabel("<b>Health Score bileşenleri</b>"))
        for name, (pts, weight) in h.components.items():
            row = QHBoxLayout()
            lbl = QLabel(f"{name} (ağırlık %{weight * 100:.0f})")
            lbl.setMinimumWidth(240)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(int(pts))
            bar.setFormat(f"{pts:.0f}")
            bar.setStyleSheet(f"QProgressBar {{ border: 1px solid #dde3e0; border-radius: 4px; background: white; text-align: center; }} QProgressBar::chunk {{ background: {ACCENT}; }}")
            row.addWidget(lbl)
            row.addWidget(bar)
            lay.addLayout(row)
        lay.addStretch()


class ConsumptionPage:
    def __init__(self, project: Project):
        self.widget, lay = _page()
        lay.addWidget(h1("Tüketim takibi"))
        lay.addWidget(muted("Aylık elektrik, doğalgaz ve su tüketimi (fatura verisi)."))
        for u in UtilityType:
            lay.addWidget(self._chart(project, u), 1)

    def _chart(self, project: Project, utility: UtilityType) -> QChartView:
        data = monthly_series(project.readings, utility)
        bars = QBarSet(f"{UTILITY_NAMES[utility]} ({UTILITY_UNITS[utility]})")
        bars.setColor(QColor(ACCENT))
        for _, v in data:
            bars.append(v)
        series = QBarSeries()
        series.append(bars)
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(UTILITY_NAMES[utility])
        chart.legend().hide()
        ax = QBarCategoryAxis()
        ax.append([m for m, _ in data])
        ax.setLabelsAngle(-60)
        ay = QValueAxis()
        ay.setLabelFormat("%.0f")
        chart.addAxis(ax, Qt.AlignBottom)
        chart.addAxis(ay, Qt.AlignLeft)
        series.attachAxis(ax)
        series.attachAxis(ay)
        view = QChartView(chart)
        view.setRenderHint(QPainter.Antialiasing)
        view.setMinimumHeight(150)
        return view


class OpportunitiesPage:
    def __init__(self, project: Project):
        self.widget, lay = _page()
        lay.addWidget(h1("Dönüşüm önerileri"))
        lay.addWidget(muted("Geri ödeme süresine göre sıralı. Tasarruf oranları ve birim "
                            "maliyetler varsayımdır, pilot bina etüdüyle güncellenecek."))
        res = project.opportunity_results()
        t = _table(["Öneri", "Kategori", "Tasarruf (kWh/yıl)", "Karbon (kgCO₂/yıl)",
                    "Yıllık tasarruf (₺)", "CAPEX (₺)", "Geri ödeme"])
        t.setRowCount(len(res))
        for i, r in enumerate(res):
            _set_row(t, i, [r.opportunity.name, r.opportunity.category, fmt(r.saved_kwh),
                            fmt(r.saved_carbon_kg), fmt(r.annual_saving), fmt(r.capex),
                            fmt_years(r.payback_years)])
        lay.addWidget(t)


class ScenarioPage:
    def __init__(self, project: Project):
        self.project = project
        self.widget, lay = _page()
        lay.addWidget(h1("Mevcut vs Hedef"))
        lay.addWidget(muted("Uygulanacak önerileri seçin; hedef durum anında hesaplanır."))
        top = QHBoxLayout()
        left = QVBoxLayout()
        self.checks: dict[str, QCheckBox] = {}
        for o in project.opportunities:
            cb = QCheckBox(f"{o.name}  (%{o.saving_pct * 100:.0f} {UTILITY_NAMES[o.affects].lower()})")
            cb.toggled.connect(self.refresh)
            self.checks[o.code] = cb
            left.addWidget(cb)
        left.addStretch()
        top.addLayout(left, 1)
        self.table = _table(["Gösterge", "Mevcut", "Hedef", "Değişim"])
        top.addWidget(self.table, 2)
        lay.addLayout(top)
        grid = QGridLayout()
        self.c_capex = Card("Toplam CAPEX", "-")
        self.c_save = Card("Yıllık tasarruf", "-")
        self.c_pay = Card("Geri ödeme süresi", "-")
        self.c_co2 = Card("Karbon azalımı", "-")
        for i, c in enumerate((self.c_capex, self.c_save, self.c_pay, self.c_co2)):
            grid.addWidget(c, 0, i)
        lay.addLayout(grid)
        self.refresh()

    def selected_codes(self) -> list[str]:
        return [c for c, cb in self.checks.items() if cb.isChecked()]

    def refresh(self):
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
                     right_from=1)
        self.c_capex.set(f"{fmt(s.capex / 1e6, 2)} M ₺")
        self.c_save.set(f"{fmt(s.annual_saving / 1e6, 2)} M ₺", "her yıl")
        self.c_pay.set(fmt_years(s.payback_years))
        self.c_co2.set(f"%{fmt(s.carbon_reduction_pct * 100, 1)}", f"enerji %{fmt(s.energy_reduction_pct * 100, 1)}")
