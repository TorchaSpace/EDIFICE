from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout

from ..engine.pricing import analyze
from ..models import UtilityType
from .pages import MONTHS, _fit_height, _page, _set_row, _table, area_chart
from .widgets import AMBER, G, RED, Card, Panel, badge, fmt, header, muted


class PricePage:
    """Etkin birim fiyat (₺/kWh) analizi: medyandan sapan aylar = fatura kalemlerinin (reaktif, güç aşımı, tarife grubu) incelenmesi gereken ayları."""

    def __init__(self, project):
        self.widget, lay = _page()
        lay.addWidget(header("Birim fiyat", "Fatura birim fiyat analizi",
                             "Aylık etkin birim fiyat (fatura tutarı ÷ tüketim) izlenir. Medyandan %15'ten fazla sapan aylar incelenmeye değer: "
                             "reaktif enerji bedeli, güç aşımı ya da tarife grubu kaynaklı olabilir. Nedeni fatura kalemleri olmadan söylenemez."))
        for utility, label in ((UtilityType.ELECTRICITY, "Elektrik"), (UtilityType.GAS, "Doğalgaz")):
            rep = analyze(project, utility)
            p = Panel(eyebrow=label, title=f"{label} birim fiyatı · {rep.year}")
            if not rep.ok or rep.tariff_derived:
                p.lay.addWidget(muted(rep.note))
                lay.addWidget(p)
                continue
            top = QHBoxLayout()
            top.setSpacing(14)
            c1 = Card("Medyan fiyat", accent=G)
            c1.set_number(rep.median_price, lambda v: f"{fmt(v, 2)} ₺/kWh", "yıllık medyan")
            c2 = Card("Olası fazla ödeme", accent=RED if rep.excess_total else G)
            c2.set_number(rep.excess_total / 1000, lambda v: f"{fmt(v)} bin ₺", f"{sum(m.flagged for m in rep.months)} şüpheli ay (üst sınır tahmin)")
            top.addWidget(c1)
            top.addWidget(c2)
            p.lay.addLayout(top)
            t = _table(["Ay", "Tüketim (MWh)", "Birim fiyat (₺/kWh)", "Medyandan sapma", "Durum"])
            t.setRowCount(len(rep.months))
            for i, m in enumerate(rep.months):
                _set_row(t, i, [MONTHS[m.month - 1], fmt(m.consumption / 1000, 1), fmt(m.price, 2), f"{m.deviation * 100:+.0f}%".replace(".", ","),
                                "İncele" if m.flagged else "Normal"], colors={4: RED if m.flagged else G}, mono_from=1)
            _fit_height(t, len(rep.months))
            p.lay.addWidget(t)
            p.lay.addWidget(area_chart([MONTHS[m.month - 1] for m in rep.months], {"Birim fiyat": [m.price for m in rep.months]},
                                       scale=1.0, decimals=2, colors=["amber"], unit="₺/kWh", min_h=170))
            lay.addWidget(p)
        lay.addStretch()
