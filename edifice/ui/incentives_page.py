from __future__ import annotations

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QGridLayout, QHBoxLayout, QLabel, QPushButton

from ..db import Store
from ..engine.incentives import Terms
from ..service import Project
from .pages import _page
from .widgets import AMBER, G, RED, Card, Panel, fmt, header, muted


class IncentivesPage:
    """Teşvik/hibe bulucu: seçili senaryoya uygun programlar; oranı kullanıcı girer, hesap yalnız girilen orana göre yapılır."""

    def __init__(self, project: Project, store: Store, on_changed=None):
        self.project, self.store, self.on_changed = project, store, on_changed
        self.widget, self.lay = _page()
        self.lay.addWidget(header("Finans", "Teşvik ve hibe bulucu",
                                  "Seçili senaryodaki önerilere uygun program türleri. Koşullar ve oranlar sık değişir ve burada doğrulanmış değildir: "
                                  "programın güncel metnini kontrol edip oranı kendiniz girin. Girmediğiniz hiçbir oran CAPEX'ten düşülmez."))
        self.rows: dict[str, tuple[QDoubleSpinBox, QDoubleSpinBox, QCheckBox]] = {}
        self.body = Panel()
        self.lay.addWidget(self.body)
        self.result = Panel(eyebrow="Etki", title="Hibe sonrası finans")
        self.lay.addWidget(self.result)
        self.lay.addStretch()
        self.reload()

    def _codes(self) -> list[str]:
        codes = self.store.load_scenario(self.project.building_id) if self.project.building_id is not None else []
        return codes or self.project.applicable_codes()

    def reload(self):
        from .pages import _clear_layout
        _clear_layout(self.body.lay)
        terms = self.store.load_incentive_terms()
        codes = self._codes()
        _, _, matches = self.project.finance_with_grants(codes, terms, include_solar=True) if codes else (None, None, [])
        self.rows.clear()
        if not matches:
            self.body.lay.addWidget(muted("Seçili önerilere uygun program bulunamadı. Projeler > Mevcut vs Hedef'ten öneri seçin."))
            self.result.hide()
            return
        self.result.show()
        self.body.lay.addWidget(muted(f"Senaryo: {', '.join(codes)} · bina tipi: {self.project.building.use_type}"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)
        for c, h in enumerate(("Program", "Tür / durum", "Hibe oranı %", "Tavan ₺", "Kontrol ettim", "")):
            grid.addWidget(muted(h.upper()), 0, c)
        for i, m in enumerate(matches, start=1):
            p = m.program
            t = terms.get(p.code, Terms())
            info = QLabel(f"<b>{p.name}</b><br><span style='color:#7B8EA3'>{p.provider} · {p.audience}</span>"
                          + (f"<br><span style='color:{AMBER}'>{m.why}</span>" if m.why else "")
                          + (f"<br><span style='color:#7B8EA3'>{p.note}</span>" if p.note else ""))
            info.setWordWrap(True)
            info.setTextFormat(Qt.RichText)
            grid.addWidget(info, i, 0)
            grid.addWidget(muted(f"{p.kind} · {p.status} · kanıt: {p.level}"), i, 1)
            pct, cap, ok = QDoubleSpinBox(), QDoubleSpinBox(), QCheckBox()
            pct.setRange(0, 100)
            pct.setDecimals(1)
            pct.setValue(t.grant_pct * 100)
            cap.setRange(0, 1e10)
            cap.setDecimals(0)
            cap.setSingleStep(100000)
            cap.setSpecialValueText("sınırsız")
            cap.setValue(t.cap or 0)
            ok.setChecked(t.verified)
            can = p.kind == "hibe" and m.in_scope
            pct.setEnabled(can)
            cap.setEnabled(can)
            pct.setToolTip("" if can else "Yalnız kapsam içi hibe programları CAPEX'i düşürür.")
            for w, c in ((pct, 2), (cap, 3), (ok, 4)):
                grid.addWidget(w, i, c)
            link = QPushButton("Kaynak ↗")
            link.setObjectName("export")
            link.setCursor(Qt.PointingHandCursor)
            link.clicked.connect(lambda _=False, u=p.url: QDesktopServices.openUrl(QUrl(u)))
            grid.addWidget(link, i, 5)
            self.rows[p.code] = (pct, cap, ok)
            pct.valueChanged.connect(self._save)
            cap.valueChanged.connect(self._save)
            ok.stateChanged.connect(self._save)
        grid.setColumnStretch(0, 4)
        self.body.lay.addLayout(grid)
        self._show_result()

    def _save(self, *_):
        for code, (pct, cap, ok) in self.rows.items():
            self.store.save_incentive_terms(code, pct.value() / 100, cap.value() or None, ok.isChecked())
        self._show_result()
        if self.on_changed:
            self.on_changed()

    def _show_result(self):
        from .pages import _clear_layout
        while self.result.lay.count() > 2:
            it = self.result.lay.takeAt(2)
            w = it.widget()
            if w:
                w.deleteLater()
            elif it.layout():
                _clear_layout(it.layout())
        codes = self._codes()
        terms = self.store.load_incentive_terms()
        base = self.project.finance_with_grants(codes, {})[0]
        fin, g, _ = self.project.finance_with_grants(codes, terms, include_solar=False)
        row = QHBoxLayout()
        row.setSpacing(14)
        c1 = Card("CAPEX", accent=G)
        c1.set_number(g.capex_after / 1e6, lambda v: f"{fmt(v, 2)} milyon ₺", f"hibe öncesi {fmt(g.capex_before / 1e6, 2)} milyon ₺")
        c2 = Card("Hibe toplamı", accent=G if g.grant_total else RED)
        c2.set_number(g.grant_total / 1e6, lambda v: f"{fmt(v, 2)} milyon ₺", "girilen orana göre")
        c3 = Card("NPV", accent=G)
        c3.set_number(fin.npv / 1e6, lambda v: f"{fmt(v, 2)} milyon ₺", f"hibesiz {fmt(base.npv / 1e6, 2)} milyon ₺")
        for c in (c1, c2, c3):
            row.addWidget(c)
        self.result.lay.addLayout(row)
        self.result.lay.addWidget(muted((g.note or "Henüz oran girilmedi: sonuçlar hibesiz değerlerle aynıdır.")
                                        + " GES yatırımı bu hesaba dahil değildir (ayrı sayfada)."))
