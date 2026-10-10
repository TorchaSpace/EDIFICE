from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..models import UtilityType  # noqa: F401  (yer tutucu sayfalar için gerekmiyor, import döngüsünü önler)
from .pages import _page
from .widgets import SUB, FadeStack, Panel, header


class TabsPage:
    """Üstte küçük sekme düğmeleri olan sayfa grubu (örn. Projeler: Öneriler | Mevcut vs Hedef)."""

    def __init__(self, tabs: list[tuple[str, object]]):
        self.tabs = dict(tabs)
        self.widget = QWidget()
        lay = QVBoxLayout(self.widget)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        bar = QWidget()
        bar.setObjectName("segbar")
        bar.setAttribute(Qt.WA_StyledBackground, True)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(32, 18, 32, 0)
        bl.setSpacing(8)
        self.stack = FadeStack()
        self.group = QButtonGroup(self.widget)
        self.group.setExclusive(True)
        for i, (name, page) in enumerate(tabs):
            b = QPushButton(name)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setChecked(i == 0)
            self.group.addButton(b, i)
            bl.addWidget(b)
            self.stack.addWidget(page.widget)
        bl.addStretch()
        self.group.idClicked.connect(self.stack.setCurrentIndex)
        lay.addWidget(bar)
        lay.addWidget(self.stack, 1)
        self.bar = bar if len(tabs) > 1 else None
        if len(tabs) == 1:
            bar.hide()


class ComingSoonPage:
    """Henüz verisi olmayan sekme: ne olacağını ve neden şimdi olmadığını dürüstçe söyler."""

    def __init__(self, eyebrow: str, title: str, text: str):
        self.widget, lay = _page()
        lay.addWidget(header(eyebrow, title, "Sonraki faz"))
        p = Panel(eyebrow="Henüz yok", title="Bu modül sonraki fazda")
        t = QLabel(text)
        t.setWordWrap(True)
        t.setStyleSheet(f"color: {SUB}; font-size: 14px; background: transparent;")
        p.lay.addWidget(t)
        lay.addWidget(p)
        lay.addStretch()


class ReportPage:
    """Raporlar: seçili bina için PDF raporu üretir."""

    def __init__(self, project, on_export):
        self.widget, lay = _page()
        lay.addWidget(header("Raporlar", "Yatırımcı raporu", f"{project.building.name} için tek sayfalık PDF"))
        p = Panel(eyebrow="PDF", title="Raporu oluştur",
                  subtitle="Rapor, Mevcut vs Hedef ekranında seçtiğin önerilere göre hazırlanır: KPI'lar, sağlık skoru, enerji sınıfı, "
                           "CAPEX, tasarruf, geri ödeme ve NPV/IRR içerir.")
        btn = QPushButton("↓ PDF raporu oluştur")
        btn.setObjectName("primary")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(38)
        btn.setFixedWidth(220)
        btn.clicked.connect(on_export)
        p.lay.addSpacing(8)
        p.lay.addWidget(btn)
        lay.addWidget(p)
        lay.addStretch()
