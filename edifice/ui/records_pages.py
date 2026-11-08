from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget

from ..db import Store
from ..service import Project
from .pages import _page
from .records import RecordsPanel
from .widgets import AMBER, G, INDIGO, RED, SUB, TEXT, Card, Panel, fmt, header, muted, qfont

PARTNER_CATS = ["Enerji hizmetleri (ESCO)", "HVAC", "Aydınlatma", "Yalıtım / cephe", "GES", "Otomasyon / BMS", "Danışmanlık / etüt", "Finansman", "Diğer"]
CERT_SCHEMES = ["Enerji Kimlik Belgesi (EKB)", "BREEAM", "LEED", "DGNB", "Yeşil Bina (Türkiye)", "ISO 50001", "ISO 14001", "Diğer"]
FINANCE_KINDS = ["Özkaynak", "Kredi", "Hibe", "ESCO / performans sözleşmesi", "Diğer"]
FINANCE_STATUS = ["Planlandı", "Başvuruldu", "Onaylandı", "Kullanıldı", "Reddedildi"]
PIE_COLORS = [G, INDIGO, AMBER, "#38BDF8", RED]


class PieChart(QWidget):
    """Basit pasta grafik: (etiket, değer) listesi; sağda açıklama."""

    def __init__(self, items: list[tuple[str, float]] | None = None):
        super().__init__()
        self.items = [(a, b) for a, b in (items or []) if b > 0]
        self.setMinimumHeight(190)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        total = sum(v for _, v in self.items)
        if not total:
            p.setPen(QColor(SUB))
            p.setFont(qfont(13))
            p.drawText(QRectF(0, 0, self.width(), self.height()), Qt.AlignCenter, "Finansman kaydı eklenince dağılım burada görünür.")
            return
        side = min(self.height() - 20, 170)
        rect = QRectF(10, 10, side, side)
        start = 90 * 16
        for i, (_, v) in enumerate(self.items):
            span = -int(v / total * 360 * 16)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(PIE_COLORS[i % len(PIE_COLORS)]))
            p.drawPie(rect, start, span)
            start += span
        p.setBrush(QColor("#0B121B"))
        p.drawEllipse(rect.adjusted(side * 0.3, side * 0.3, -side * 0.3, -side * 0.3))
        for i, (name, v) in enumerate(self.items):
            y = 18 + i * 26
            p.setBrush(QColor(PIE_COLORS[i % len(PIE_COLORS)]))
            p.drawRoundedRect(QRectF(side + 36, y, 12, 12), 3, 3)
            p.setPen(QColor(TEXT))
            p.setFont(qfont(12, 600))
            p.drawText(QRectF(side + 56, y - 4, self.width() - side - 60, 22), Qt.AlignVCenter | Qt.AlignLeft,
                       f"{name} · {fmt(v / 1e6, 2)} M ₺ · %{v / total * 100:.0f}")


class PartnersPage:
    """Ortaklar: uygulayıcı firma / danışman kaydı (bina verisinden bağımsız, elle girilir)."""

    def __init__(self, store: Store):
        self.store = store
        self.widget, self.lay = _page()
        self.lay.addWidget(header("Ortaklar", "Uygulayıcı firmalar ve danışmanlar",
                                  "Teklif aldığınız ya da çalıştığınız firmaları kaydedin. Veriler yalnız bu bilgisayarda kalır; puanı siz verirsiniz."))
        self.row = QHBoxLayout()
        self.row.setSpacing(14)
        self.c_n = Card("Kayıtlı ortak", accent=G)
        self.c_r = Card("Ortalama puan", accent=AMBER)
        self.c_c = Card("Kategori", accent=INDIGO)
        for c in (self.c_n, self.c_r, self.c_c):
            self.row.addWidget(c)
        self.lay.addLayout(self.row)
        self.panel = RecordsPanel(store, "partners",
                                  [("name", "Firma", "text"), ("category", "Kategori", "combo", PARTNER_CATS), ("country", "Ülke / şehir", "text"),
                                   ("rating", "Puan (0-5)", "num", 1), ("contact", "İletişim", "text"), ("note", "Not", "text")],
                                  "Ortak kaydı", eyebrow="Kayıt", on_change=self.kpis,
                                  line=lambda r: f"★ {r['rating']:.1f}  {r['name']} · {r['category']}" + (f" · {r['country']}" if r["country"] else "")
                                  + (f" · {r['contact']}" if r["contact"] else "") + (f" — {r['note']}" if r["note"] else ""))
        self.lay.addWidget(self.panel)
        self.lay.addStretch()
        self.kpis()

    def kpis(self):
        rows = self.store.list_records("partners")
        rated = [r["rating"] for r in rows if r["rating"]]
        self.c_n.set_number(len(rows), lambda v: f"{v:.0f}", "firma")
        self.c_r.set_number(sum(rated) / len(rated) if rated else 0, lambda v: f"{v:.1f} / 5" if rated else "-", "yalnız puan verilenler")
        self.c_c.set_number(len({r["category"] for r in rows}), lambda v: f"{v:.0f}", "farklı kategori")


class CertificatesPage:
    """Sertifika takibi (BREEAM, LEED, EKB, ISO …): bina başına, geçerlilik tarihiyle."""

    def __init__(self, project: Project, store: Store):
        self.widget, lay = _page()
        lay.addWidget(header("Sürdürülebilirlik", "Sertifikalar", f"{project.building.name} için sahip olunan ya da hedeflenen belgeler (elle girilir, doğrulanmaz)."))
        lay.addWidget(RecordsPanel(store, "certificates",
                                   [("scheme", "Belge", "combo", CERT_SCHEMES), ("level", "Seviye / sınıf", "text"), ("issued", "Veriliş (GG.AA.YYYY)", "text"),
                                    ("expires", "Geçerlilik sonu", "text"), ("note", "Not", "text")],
                                   "Sertifika kaydı", eyebrow="Kayıt", building_id=project.building_id,
                                   line=lambda r: f"{r['scheme']}" + (f" {r['level']}" if r["level"] else "") + (f" · veriliş {r['issued']}" if r["issued"] else "")
                                   + (f" · geçerlilik {r['expires']}" if r["expires"] else "") + (f" — {r['note']}" if r["note"] else "")))
        lay.addStretch()


class FinancingPage:
    """Finansman karması: özkaynak, kredi, hibe, ESCO kayıtları + pasta grafik."""

    def __init__(self, project: Project, store: Store):
        self.store, self.bid = store, project.building_id
        self.widget, lay = _page()
        lay.addWidget(header("Finans", "Finansman karması", f"{project.building.name} yatırımlarının nasıl finanse edildiğini kaydedin; oranları ve tutarları siz girersiniz."))
        self.pie_panel = Panel(eyebrow="Dağılım", title="Finansman karması")
        self.pie = PieChart()
        self.pie_panel.lay.addWidget(self.pie)
        self.total = muted("")
        self.pie_panel.lay.addWidget(self.total)
        lay.addWidget(self.pie_panel)
        self.panel = RecordsPanel(store, "finance_items",
                                  [("name", "Ad / kaynak", "text"), ("kind", "Tür", "combo", FINANCE_KINDS), ("status", "Durum", "combo", FINANCE_STATUS),
                                   ("amount", "Tutar (₺)", "num", 0), ("rate_pct", "Faiz / oran %", "num", 2), ("term_years", "Vade (yıl)", "num", 1)],
                                  "Finansman kaydı", eyebrow="Kayıt", building_id=project.building_id, on_change=self.refresh,
                                  line=lambda r: f"{r['kind']} · {r['name']} · {fmt(r['amount'] or 0)} ₺" + (f" · %{r['rate_pct']:.2f}".replace(".", ",") if r["rate_pct"] else "")
                                  + (f" · {r['term_years']:g} yıl" if r["term_years"] else "") + f" · {r['status']}")
        lay.addWidget(self.panel)
        lay.addStretch()
        self.refresh()

    def mix(self) -> dict:
        out: dict = {}
        for r in self.store.list_records("finance_items", self.bid):
            if r["status"] != "Reddedildi":
                out[r["kind"]] = out.get(r["kind"], 0.0) + (r["amount"] or 0.0)
        return out

    def refresh(self):
        mix = self.mix()
        self.pie.items = [(k, v) for k, v in mix.items() if v > 0]
        self.pie.update()
        tot = sum(mix.values())
        self.total.setText(f"Toplam {fmt(tot / 1e6, 2)} M ₺ (reddedilenler hariç). Kredi maliyeti NPV hesabına otomatik katılmaz." if tot else "")
