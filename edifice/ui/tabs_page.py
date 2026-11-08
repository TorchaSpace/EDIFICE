from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..models import UtilityType  # noqa: F401  (yer tutucu sayfalar için gerekmiyor, import döngüsünü önler)
from .pages import _page
from .widgets import SUB, FadeStack, Panel, header, muted


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
        self.names = [n for n, _ in tabs]
        self.on_change = None                       # MainWindow: üst çubuktaki konum ve oturum hafızası için
        self.group.idClicked.connect(self._clicked)
        lay.addWidget(bar)
        lay.addWidget(self.stack, 1)
        self.bar = bar if len(tabs) > 1 else None
        if len(tabs) == 1:
            bar.hide()

    def _clicked(self, i: int):
        self.stack.setCurrentIndex(i)
        if self.on_change:
            self.on_change(self.names[i])

    def current(self) -> str:
        return self.names[max(0, self.group.checkedId())]

    def select(self, name: str) -> bool:
        """Sekmeyi adıyla seçer (animasyonsuz geçiş için set_current'tan önce çağrılabilir)."""
        if name not in self.names:
            return False
        i = self.names.index(name)
        self.group.button(i).setChecked(True)
        self._clicked(i)
        return True

    def step(self, delta: int):
        """Ctrl+Tab / Ctrl+Shift+Tab: sonraki/önceki sekme (döngüsel)."""
        if len(self.names) > 1:
            self.select(self.names[(self.group.checkedId() + delta) % len(self.names)])


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

    def __init__(self, project, on_export, on_pack=None, store=None):
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
        packs = Panel(eyebrow="Excel paketleri", title="Raporlama veri paketleri",
                      subtitle="Resmî beyan ya da belge değildir: raporlayıcıya/uzmana hazır veri ve açık yöntem sağlar.")
        pr = QHBoxLayout()
        pr.setSpacing(10)
        for key, label, tip in (("esg", "ESG veri paketi", "Kapsam 1-2 emisyon, enerji, su, aylık döküm, yöntem ve kaynaklar, veri kalitesi"),
                                ("ekb", "EKB hazırlık sayfası", "Enerji Kimlik Belgesi düzenleyecek uzman için bina, tüketim ve ekipman verisi"),
                                ("portfoy", "Portföy özeti", "Tüm binalar: EUI, sınıf, skor, karbon, CAPEX, tasarruf, NPV, veri güvenilirliği")):
            b = QPushButton(label)
            b.setObjectName("export")
            b.setMinimumHeight(38)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(tip)
            if on_pack:
                b.clicked.connect(lambda _=False, k=key: on_pack(k))
            pr.addWidget(b)
        pr.addStretch()
        packs.lay.addSpacing(6)
        packs.lay.addLayout(pr)
        lay.addWidget(packs)
        self.store, self.project = store, project
        if store is not None:
            self.hist = Panel(eyebrow="Geçmiş", title="Üretilen raporlar", subtitle="Bu bilgisayarda oluşturduğunuz raporların kaydı; dosyaya tıklayarak açabilirsiniz.")
            lay.addWidget(self.hist)
            self.refresh_history()
        lay.addStretch()


    def refresh_history(self):
        """Rapor geçmişi: bu bina ve portföy raporları, yeniden eskiye. Dosya taşınmışsa «bulunamadı» yazar."""
        import os
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWidgets import QPushButton
        lay = self.hist.lay
        while lay.count() > 3:
            it = lay.takeAt(3)
            if it.widget():
                it.widget().deleteLater()
        rows = [r for r in self.store.list_records("report_log") if r["building_id"] in (None, self.project.building_id)][:12]
        if not rows:
            lay.addWidget(muted("Henüz rapor üretilmedi."))
        for r in rows:
            exists = os.path.exists(r["path"] or "")
            b = QPushButton(f"{r['created_at'][:16]}   {r['kind']}   {os.path.basename(r['path'] or '')}" + ("" if exists else "   (dosya bulunamadı)"))
            b.setObjectName("export")
            b.setEnabled(exists)
            b.setStyleSheet("text-align: left; padding: 8px 12px;")
            b.clicked.connect(lambda _=False, p=r["path"]: QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
            lay.addWidget(b)
