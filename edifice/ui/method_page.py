"""Kaynaklar ve Yöntem: uygulamadaki her varsayımın dayandığı kanıt ve doğrulama düzeyi."""
from __future__ import annotations

from collections import Counter

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ..evidence import LEVELS, OFFICIAL_THRESHOLDS, SOURCES, parameter_rows
from ..service import Project
from .pages import _page
from .widgets import AMBER, G, INDIGO, MUTED, RED, SUB, TEXT, Panel, badge, header, muted

LEVEL_COLOR = {"birincil": G, "özet": "#5BE3B4", "ikincil": AMBER, "varsayım": RED}
LEVEL_HELP = {
    "birincil": "Kaynağın kendisi (tablo, rapor ya da resmi sayfa) okundu; rakamlar oradan alındı.",
    "özet": "Makalenin özeti ya da yayıncı sayfası okundu; tam metin okunmadı.",
    "ikincil": "Rakam başka bir kaynağın aktarımından alındı; asıl kaynakla doğrulanmalı.",
    "varsayım": "Doğrulanabilir kaynak bulunamadı; gerçek değerle Ayarlar'dan değiştirilmeli.",
}


def _row(title: str, value: str, level: str, note: str, srcs: list[str]) -> QFrame:
    box = QFrame()
    box.setObjectName("inner")
    lay = QVBoxLayout(box)
    lay.setContentsMargins(16, 12, 16, 12)
    lay.setSpacing(4)
    top = QHBoxLayout()
    t = QLabel(title)
    t.setStyleSheet("font-size: 13px; font-weight: 700; background: transparent;")
    v = QLabel(value)
    v.setStyleSheet(f"color: {G}; font-size: 12px; font-family: 'DM Mono','SF Mono',Menlo,monospace; background: transparent;")
    top.addWidget(t)
    top.addStretch()
    top.addWidget(v)
    top.addWidget(badge(LEVELS[level], LEVEL_COLOR[level]))
    lay.addLayout(top)
    n = QLabel(note)
    n.setWordWrap(True)
    n.setStyleSheet(f"color: {SUB}; font-size: 12px; background: transparent;")
    lay.addWidget(n)
    if srcs:
        s = QLabel("Kaynak: " + ", ".join(srcs))
        s.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent;")
        lay.addWidget(s)
    return box


class MethodPage:
    def __init__(self, project: Project):
        self.widget, lay = _page()
        a = project.assumptions
        lay.addWidget(header("Metodoloji", "Kaynaklar ve yöntem",
                             "Her varsayımın hangi çalışmaya dayandığını ve kaynağın ne kadar doğrulandığını şeffaf biçimde gösterir. "
                             "Doğrulanamayan her şey açıkça \"Varsayım\" diye işaretlenir."))

        rows = parameter_rows(a)
        opps = project.opportunities
        counts = Counter([r[4] for r in rows] + [o.evidence_level for o in opps])
        sc = Panel("Güven ölçeği", f"{sum(counts.values())} varsayımın dağılımı")
        for lvl in ("birincil", "özet", "ikincil", "varsayım"):
            line = QHBoxLayout()
            line.addWidget(badge(LEVELS[lvl], LEVEL_COLOR[lvl]))
            cnt = QLabel(f"{counts.get(lvl, 0)} varsayım")
            cnt.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 600; background: transparent;")
            line.addWidget(cnt)
            line.addWidget(muted(LEVEL_HELP[lvl]), 1)
            sc.lay.addLayout(line)
        lay.addWidget(sc)

        pp = Panel("Hesap parametreleri", "Değerler Ayarlar ekranından değiştirilebilir; kaynak ve düzey burada görünür")
        group = None
        for g, name, value, srcs, level, note in rows:
            if g != group:
                gl = QLabel(g.upper())
                gl.setObjectName("eyebrow")
                pp.lay.addSpacing(6)
                pp.lay.addWidget(gl)
                group = g
            pp.lay.addWidget(_row(name, value, level, note, srcs))
        lay.addWidget(pp)

        ot = Panel("Resmî eşikler (Türkiye)", "Binalarda Enerji Performansı Yönetmeliği ve ÇŞİDB belgesinden, doğrudan okunarak alındı")
        for title, text, src in OFFICIAL_THRESHOLDS:
            ot.lay.addWidget(_row(title, "", "birincil", text, [src]))
        lay.addWidget(ot)

        op = Panel("Dönüşüm önerileri: tasarruf aralıkları", "Etkilenen kalemde bina düzeyinde tasarruf: düşük · tipik · yüksek")
        for o in opps:
            val = f"%{o.saving_for('low') * 100:.1f} · %{o.saving_pct * 100:.1f} · %{o.saving_for('high') * 100:.1f}".replace(".", ",")
            op.lay.addWidget(_row(o.name, val, o.evidence_level, o.basis or "Kullanıcı tanımlı.", list(o.evidence)))
        lay.addWidget(op)

        sp = Panel("Kaynakça", "Metinde kısaltmayla anılan çalışmalar")
        for key, s in SOURCES.items():
            box = QFrame()
            box.setObjectName("inner")
            bl = QVBoxLayout(box)
            bl.setContentsMargins(16, 12, 16, 12)
            bl.setSpacing(4)
            top = QHBoxLayout()
            k = QLabel(key)
            k.setStyleSheet(f"color: {G}; font-size: 11px; font-family: 'DM Mono','SF Mono',Menlo,monospace; background: transparent;")
            top.addWidget(k)
            top.addStretch()
            top.addWidget(badge(LEVELS[s["level"]], LEVEL_COLOR[s["level"]]))
            bl.addLayout(top)
            c = QLabel(s["cite"])
            c.setWordWrap(True)
            c.setStyleSheet("font-size: 13px; font-weight: 600; background: transparent;")
            bl.addWidget(c)
            n = QLabel(s["note"])
            n.setWordWrap(True)
            n.setStyleSheet(f"color: {SUB}; font-size: 12px; background: transparent;")
            bl.addWidget(n)
            link = QLabel(f'<a style="color:{INDIGO}" href="{s["url"]}">{s["url"]}</a>')
            link.setOpenExternalLinks(True)
            link.setTextInteractionFlags(Qt.TextBrowserInteraction)
            link.setStyleSheet("font-size: 11px; background: transparent;")
            bl.addWidget(link)
            sp.lay.addWidget(box)
        lay.addWidget(sp)

        lp = Panel("Sınırlamalar", "Sonuçlar nasıl okunmalı")
        for text in (
            "Kıyas değerleri ABD ulusal medyanıdır (ENERGY STAR/CBECS). Türkiye iklimi ve işletme alışkanlıkları farklıdır; BEP-TR referans değerleri girildikçe sonuçlar iyileşir.",
            "Enerji sınıfı (A-G) ve benzer binalara göre yüzdelik göstergedir; resmi Enerji Kimlik Belgesi değildir. Sınır değerleri resmi tablodan doğrulanamadı.",
            "Tasarruf aralıkları yayımlanmış çalışmalardan türetilmiştir ve bina özelinde etüt/ölçümün yerini tutmaz. Tahmin ile ölçüm arasında ortalama +%34 (SS %55) fark "
            "gözlenmiştir (van Dronkelaar ve ark. 2016); bu yüzden finans ekranında düşük-yüksek aralığı ve duyarlılık tablosu gösterilir.",
            "Yatırım maliyetleri (₺/m²) doğrulanmış bir kaynağa dayanmaz; teklif ya da keşif bedeliyle değiştirilmelidir.",
            "Hava durumu normalizasyonu (derece-gün) ve ölçüm-doğrulama (IPMVP / ASHRAE Guideline 14) bu sürümde yoktur; yıllık karşılaştırmalar hava farkından etkilenebilir.",
        ):
            l = QLabel("•  " + text)
            l.setWordWrap(True)
            l.setStyleSheet(f"color: {SUB}; font-size: 13px; background: transparent;")
            lp.lay.addWidget(l)
        lay.addWidget(lp)
        lay.addStretch()
