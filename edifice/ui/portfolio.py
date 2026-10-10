from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..db import Store
from ..engine.rating import CLASS_COLORS
from ..models import UtilityType
from ..service import Project
from .pages import MONTHS, _page
from .widgets import AMBER, G, INDIGO, MUTED, RED, SUB, Card, Panel, badge, fmt, fmt_years, grade_for, header, score_color


def summarize(project: Project) -> dict:
    """Bir binanın portföy satırı için gerçek hesap çıktıları."""
    k, h = project.kpis(), project.health()
    codes = project.applicable_codes()
    fin = project.finance(codes) if codes else None
    sc = project.scenario(codes) if codes else None
    return {"project": project, "kpis": k, "health": h.total, "grade": h.grade, "rating": project.rating()["class"],
            "saving": sc.annual_saving if sc else 0.0, "capex": sc.capex if sc else 0.0,
            "npv": fin.npv if fin else 0.0, "payback": sc.payback_years if sc else float("inf")}


class PortfolioPage:
    """Tüm kayıtlı binaların toplam görünümü; kart tıklanınca bina açılır."""

    def __init__(self, store: Store, on_open, query: str = ""):
        self.widget, lay = _page()
        self.rows = []
        for bid, name in store.list_buildings():
            if query and query.lower() not in name.lower():
                continue
            self.rows.append((bid, summarize(store.load_project(bid))))
        n = len(self.rows)
        lay.addWidget(header("Portföy", "Binalarım",
                             f"{n} bina" + (f" · arama: “{query}”" if query else "") +
                             " · Her kart seçili binanın gerçek verisinden hesaplanır."))
        if not self.rows:
            empty = QLabel("Eşleşen bina yok.")
            empty.setStyleSheet(f"color: {SUB}; font-size: 14px; background: transparent;")
            lay.addWidget(empty)
            lay.addStretch()
            return

        area = sum(r["project"].building.floor_area_m2 for _, r in self.rows)
        energy = sum(r["kpis"].total_energy_kwh for _, r in self.rows) / 1000
        carbon = sum(r["kpis"].carbon_kg for _, r in self.rows) / 1000
        cost = sum(r["kpis"].total_cost for _, r in self.rows) / 1e6
        saving = sum(r["saving"] for _, r in self.rows) / 1e6
        capex = sum(r["capex"] for _, r in self.rows) / 1e6
        avg_health = sum(r["health"] for _, r in self.rows) / n
        specs = [
            ("Toplam alan", area / 1000, lambda v: f"{fmt(v, 1)} bin m²", f"{n} bina", G),
            ("Toplam enerji", energy, lambda v: f"{fmt(v)} MWh", "yıllık", AMBER),
            ("Toplam karbon", carbon, lambda v: f"{fmt(v, 1)} tCO₂", "yıllık", G),
            ("Enerji maliyeti", cost, lambda v: f"{fmt(v, 2)} M ₺", "yıllık", AMBER),
            ("Ortalama sağlık", avg_health, lambda v: f"{fmt(v)}/100", f"not {grade_for(avg_health)}", INDIGO),
            ("Tasarruf potansiyeli", saving, lambda v: f"{fmt(v, 2)} M ₺/yıl", f"CAPEX {fmt(capex, 2)} M ₺ (uygun öneriler)", G),
        ]
        grid = QGridLayout()
        grid.setSpacing(16)
        for i, (t, v, f, sub, acc) in enumerate(specs):
            c = Card(t, sub=sub, accent=acc)
            c.set_number(v, f, sub)
            grid.addWidget(c, i // 3, i % 3)
        lay.addLayout(grid)

        pts = [(bid, r["project"].building.name, r["project"].building.lat, r["project"].building.lon, r["health"])
               for bid, r in self.rows if r["project"].building.lat is not None]
        if pts:
            mp = Panel(eyebrow="Konum", title="Bina konumları",
                       subtitle="Girilen adrese göre; nokta rengi sağlık skoru. Tekerlekle yakınlaştırın, sürükleyerek kaydırın.")
            mp.lay.addWidget(LocationMap(pts, on_open), 1)
            lay.addWidget(mp)
        else:
            mp = Panel(eyebrow="Konum", title="Harita",
                       subtitle="Henüz konumu girilmiş bina yok. Sol alttaki bina kartından “Bu binayı düzenle” > Genel bilgiler bölümündeki "
                                "adres alanına yazın (ör. Ankara), önerilerden birini seçin; bina haritada görünür.")
            lay.addWidget(mp)

        cards = Panel(eyebrow="Bina listesi", title="Portföydeki binalar",
                      subtitle="Sağlık skoru, enerji sınıfı (tahmini) ve uygun önerilerin tasarruf potansiyeli. Bir binaya tıklayın.")
        for bid, r in sorted(self.rows, key=lambda x: x[1]["health"]):
            cards.lay.addWidget(self._row(bid, r, on_open))
        lay.addWidget(cards)
        lay.addStretch()

    @staticmethod
    def _row(bid: int, r: dict, on_open) -> QPushButton:
        b = r["project"].building
        btn = QPushButton()
        btn.setObjectName("bldgrow")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(76)
        btn.setStyleSheet("QPushButton#bldgrow { background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06);"
                          "border-radius: 14px; text-align: left; } QPushButton#bldgrow:hover { background: rgba(13,221,150,0.06);"
                          "border: 1px solid rgba(13,221,150,0.25); }")
        h = QHBoxLayout(btn)
        h.setContentsMargins(18, 0, 18, 0)
        h.setSpacing(18)
        score = QLabel(f"{r['health']:.0f}")
        score.setFixedSize(46, 46)
        score.setAlignment(Qt.AlignCenter)
        col = score_color(r["health"])
        score.setStyleSheet(f"color: {col}; border: 2px solid {col}; border-radius: 23px; font-size: 15px; font-weight: 800; background: transparent;")
        txt = QVBoxLayout()
        txt.setSpacing(2)
        name = QLabel(b.name)
        name.setStyleSheet("font-size: 14px; font-weight: 700; background: transparent;")
        meta = QLabel(f"{b.use_type} · {fmt(b.floor_area_m2)} m² · {b.year_built} · EUI {fmt(r['kpis'].eui_kwh_m2, 0)} kWh/m²")
        meta.setStyleSheet(f"color: {SUB}; font-size: 12px; background: transparent;")
        txt.addWidget(name)
        txt.addWidget(meta)
        h.addWidget(score)
        h.addLayout(txt, 1)
        cls = r["rating"]
        bd = badge(f"Sınıf {cls}", CLASS_COLORS[cls])
        bd.setFixedHeight(24)
        h.addWidget(bd, 0, Qt.AlignVCenter)
        sv = QLabel(f"{fmt(r['saving'] / 1000)} bin ₺/yıl")
        sv.setMinimumWidth(110)
        sv.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        sv.setStyleSheet(f"color: {G}; font-family: 'DM Mono','SF Mono',Menlo; font-size: 13px; background: transparent;")
        h.addWidget(sv)
        for w in btn.findChildren(QWidget):
            w.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        btn.clicked.connect(lambda _=False, i=bid: on_open(i))
        return btn


def _mono_label(text: str, color: str = SUB) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {color}; font-family: 'DM Mono','SF Mono',Menlo; font-size: 13px; background: transparent;")
    return lbl


class FinancePage:
    """Portföy finansı: uygun önerilerin bina bazında CAPEX, tasarruf, NPV, IRR ve geri ödemesi (gerçek hesap)."""

    def __init__(self, store: Store, on_open):
        from .pages import _set_row, _table, _fit_height
        self.widget, lay = _page()
        rows = [(bid, summarize(store.load_project(bid))) for bid, _ in store.list_buildings()]
        a = rows[0][1]["project"].assumptions if rows else None
        lay.addWidget(header("Finans", "Portföy finansı",
                             "Her binada uygun (ekipmana göre elenmiş) tüm önerilerin tipik tasarruf senaryosu. "
                             + (f"{a.horizon_years} yıl · reel · iskonto %{fmt(a.discount_rate * 100, 1)}." if a else "")))
        capex = sum(r["capex"] for _, r in rows)
        saving = sum(r["saving"] for _, r in rows)
        npv = sum(r["npv"] for _, r in rows)
        grid = QGridLayout()
        grid.setSpacing(16)
        specs = [("Toplam CAPEX", capex / 1e6, lambda v: f"{fmt(v, 2)} M ₺", "uygun öneriler", AMBER),
                 ("Yıllık tasarruf", saving / 1e6, lambda v: f"{fmt(v, 2)} M ₺", "her yıl", G),
                 ("Toplam NPV", npv / 1e6, lambda v: f"{fmt(v, 2)} M ₺", "bugünkü değerle", G if npv >= 0 else RED),
                 ("Basit geri ödeme", (capex / saving) if saving else 0, lambda v: f"{fmt(v, 1)} yıl" if v else "-", "CAPEX / yıllık tasarruf (fiyat artışı hariç)", INDIGO)]
        for i, (t, v, f, sub, acc) in enumerate(specs):
            c = Card(t, sub=sub, accent=acc)
            c.set_number(v, f, sub)
            grid.addWidget(c, 0, i)
        lay.addLayout(grid)
        p = Panel(eyebrow="Bina bazında", title="Yatırım getirisi", subtitle="NPV'ye göre sıralı. Satıra çift tıklayınca bina açılır.")
        t = _table(["Bina", "CAPEX (M ₺)", "Tasarruf (M ₺/yıl)", "NPV (M ₺)", "Geri ödeme"])
        order = sorted(rows, key=lambda x: -x[1]["npv"])
        t.setRowCount(len(order))
        for i, (bid, r) in enumerate(order):
            pb = r["payback"]
            _set_row(t, i, [r["project"].building.name, fmt(r["capex"] / 1e6, 2), fmt(r["saving"] / 1e6, 2),
                            fmt(r["npv"] / 1e6, 2), fmt_years(pb)], colors={3: G if r["npv"] >= 0 else RED}, mono_from=1)
        t.cellDoubleClicked.connect(lambda row, _c, o=order: on_open(o[row][0]))
        _fit_height(t, max(len(order), 1))
        p.lay.addWidget(t)
        lay.addWidget(p)
        lay.addStretch()


class EsgPage:
    """Sürdürülebilirlik: karbon, kişi/m² yoğunluğu, hedef paketle azalım ve mevzuat eşikleri (gerçek hesap)."""

    def __init__(self, store: Store, on_open):
        self.widget, lay = _page()
        rows = [(bid, summarize(store.load_project(bid))) for bid, _ in store.list_buildings()]
        lay.addWidget(header("Sürdürülebilirlik", "Karbon ve ESG göstergeleri",
                             "Emisyon faktörleri: elektrik 0,469 kgCO₂e/kWh (ETKB 2023), doğalgaz 0,202 (IPCC). Sınıflar tahminidir, resmî EKB değildir."))
        carbon = sum(r["kpis"].carbon_kg for _, r in rows) / 1000
        after = 0.0
        for _, r in rows:
            codes = r["project"].applicable_codes()
            sc = r["project"].scenario(codes) if codes else None
            after += (sc.target.carbon_kg if sc else r["kpis"].carbon_kg) / 1000
        area = sum(r["project"].building.floor_area_m2 for _, r in rows)
        ok_c = sum(1 for _, r in rows if r["rating"] in ("A", "B", "C"))
        grid = QGridLayout()
        grid.setSpacing(16)
        specs = [("Yıllık karbon", carbon, lambda v: f"{fmt(v, 1)} tCO₂", f"{fmt(carbon * 1000 / area, 1) if area else 0} kg/m²", G),
                 ("Önerilerle hedef", after, lambda v: f"{fmt(v, 1)} tCO₂", f"%{fmt(100 * (1 - after / carbon), 1) if carbon else 0} azalım", G),
                 ("Sınıf C ve üstü", ok_c, lambda v: f"{int(v)}/{len(rows)}", "yeni bina eşiği (BEP)", INDIGO if ok_c else AMBER)]
        for i, (t, v, f, sub, acc) in enumerate(specs):
            c = Card(t, sub=sub, accent=acc)
            c.set_number(v, f, sub)
            grid.addWidget(c, 0, i)
        lay.addLayout(grid)
        p = Panel(eyebrow="Bina bazında", title="Karbon sıralaması", subtitle="En yüksek karbon yoğunluğundan düşüğe. Binaya tıklayın.")
        for bid, r in sorted(rows, key=lambda x: -x[1]["kpis"].carbon_kg_m2):
            p.lay.addWidget(PortfolioPage._row(bid, r, on_open))
        lay.addWidget(p)
        lay.addStretch()


def insights(project: Project) -> list[tuple[str, str, str]]:
    """Seçili bina için kural tabanlı bulgular: (renk, başlık, açıklama). Yalnız gerçek hesaptan türetilir."""
    out = []
    h, k = project.health(), project.kpis()
    name, (pts, w) = min(h.components.items(), key=lambda kv: kv[1][0])
    out.append((RED if pts < 40 else AMBER, f"En zayıf bileşen: {name}",
                f"Sağlık skorunun {name.lower()} bileşeni {pts:.0f}/100 (ağırlık %{w * 100:.0f}); toplam skor {h.total:.0f}/100, not {h.grade}."))
    for key, label in (("energy", "Enerji tüketimi"), ("cost", "Enerji maliyeti"), ("carbon", "Karbon salımı")):
        v = project.yoy().get(key)
        if v is not None and abs(v) >= 3:
            out.append((RED if v > 0 else G, f"{label} geçen yıla göre %{abs(v):.0f} {'arttı' if v > 0 else 'azaldı'}",
                        f"{project.year} ile {project.year - 1} karşılaştırması."))
    total = [a + b for a, b in zip(project.monthly(project.year, UtilityType.ELECTRICITY), project.monthly(project.year, UtilityType.GAS))]
    avg = sum(total) / 12 if total else 0
    if avg:
        i = max(range(12), key=lambda j: total[j])
        if total[i] > 1.4 * avg:
            out.append((AMBER, f"{MONTHS[i]} ayında tüketim ortalamanın %{(total[i] / avg - 1) * 100:.0f} üstünde",
                        "Mevsimsel pik olabilir; ısıtma/soğutma çizelgesini kontrol edin."))
    r = project.rating()
    out.append((G if r["class"] in "ABC" else AMBER, f"Tahmini enerji sınıfı {r['class']}",
                f"EUI {r['eui']:.0f} kWh/m²·yıl, kıyas {r['benchmark']:.0f}. Resmî EKB değildir."))
    best = [x for x in project.opportunity_results() if x.fit != "none"]
    if best:
        b = min(best, key=lambda x: x.payback_years)
        out.append((G, f"En hızlı geri dönen fırsat: {b.opportunity.name}",
                    f"CAPEX {fmt(b.capex / 1e6, 2)} M ₺, yıllık tasarruf {fmt(b.annual_saving / 1000)} bin ₺, geri ödeme {fmt_years(b.payback_years)}."))
    return out


class AssistantPage:
    """Seçili bina için otomatik bulgular. Bir dil modeli değil; kurallar gerçek hesap çıktısını okur."""

    def __init__(self, project: Project):
        self.widget, lay = _page()
        lay.addWidget(header("Asistan", "Otomatik bulgular",
                             f"{project.building.name} için hesap motorunun çıkardığı öne çıkan noktalar. "
                             "Kural tabanlıdır; yalnız bu binanın verisini okur."))
        p = Panel(eyebrow="EDIFI'CE analiz", title="Öne çıkanlar")
        for color, title, text in insights(project):
            p.lay.addWidget(_insight_card(color, title, text))
        lay.addWidget(p)
        lay.addStretch()


def _insight_card(color: str, title: str, text: str) -> QWidget:
    c = QColor(color)
    w = QWidget()
    w.setObjectName("ins")
    w.setStyleSheet(f"QWidget#ins {{ background: rgba({c.red()},{c.green()},{c.blue()},0.05);"
                    f"border: 1px solid rgba({c.red()},{c.green()},{c.blue()},0.16); border-radius: 12px; }}")
    v = QVBoxLayout(w)
    v.setContentsMargins(16, 12, 16, 12)
    v.setSpacing(3)
    t = QLabel(title)
    t.setStyleSheet("font-size: 14px; font-weight: 700; background: transparent;")
    d = QLabel(text)
    d.setWordWrap(True)
    d.setStyleSheet(f"color: {SUB}; font-size: 13px; background: transparent;")
    v.addWidget(t)
    v.addWidget(d)
    return w


class LocationMap(QWidget):
    """Canlı harita: OpenStreetMap karoları koyu temaya boyanır; bina noktaları üstte.
    Tekerlek: imleç noktasına yumuşak yakınlaştırma, sürükle: atalet ile kaydırma.
    Karolar diskte önbelleğe alınır; inmeyen karo yerine üst seviye karo bulanık gösterilir.
    İnternet yoksa harita boş kalır, noktalar çizilmeye devam eder."""

    TILE = 256
    URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"

    def __init__(self, points: list[tuple[int, str, float, float, float]], on_open):
        super().__init__()
        import math
        from pathlib import Path
        from PySide6.QtCore import QTimer, QVariantAnimation, QEasingCurve
        from PySide6.QtNetwork import QNetworkAccessManager, QNetworkDiskCache
        self.points, self.on_open = points, on_open
        self.setMinimumHeight(420)
        self.setMouseTracking(True)
        self._tiles: dict[tuple[int, int, int], object] = {}
        self._pending: set[tuple[int, int, int]] = set()
        self._net = QNetworkAccessManager(self)
        cache = QNetworkDiskCache(self)
        cache_dir = Path.home() / ".edifice" / "tiles"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache.setCacheDirectory(str(cache_dir))
        cache.setMaximumCacheSize(80 * 1024 * 1024)
        self._net.setCache(cache)
        self._hover = -1
        self._press = None
        self._last = None
        self._vel = QPointF(0, 0)
        lats = [p[2] for p in points]
        lons = [p[3] for p in points]
        self.clat, self.clon = (min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2
        span = max(max(lats) - min(lats), max(lons) - min(lons), 0.02)
        self.zf = float(max(3, min(15, math.log2(360 / (span * 1.7)))))
        self._zanim = QVariantAnimation(self)
        self._zanim.setDuration(320)
        self._zanim.setEasingCurve(QEasingCurve.OutCubic)
        self._zanim.valueChanged.connect(self._zoom_step)
        self._anchor = None
        self._inertia = QTimer(self)
        self._inertia.setInterval(16)
        self._inertia.timeout.connect(self._inertia_step)

    # ---- web mercator (kesirli zoom)
    def _world(self, lat: float, lon: float, z: float) -> tuple[float, float]:
        import math
        n = self.TILE * 2 ** z
        return (lon + 180) / 360 * n, (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n

    def _unworld(self, x: float, y: float, z: float) -> tuple[float, float]:
        import math
        n = self.TILE * 2 ** z
        return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n)))), x / n * 360 - 180

    def _xy(self, lat: float, lon: float) -> QPointF:
        cx, cy = self._world(self.clat, self.clon, self.zf)
        x, y = self._world(lat, lon, self.zf)
        return QPointF(self.width() / 2 + x - cx, self.height() / 2 + y - cy)

    # ---- karolar
    def _request(self, key):
        from PySide6.QtCore import QUrl
        from PySide6.QtNetwork import QNetworkRequest
        if key in self._pending or key in self._tiles or len(self._pending) > 40:
            return
        z, x, y = key
        self._pending.add(key)
        req = QNetworkRequest(QUrl(self.URL.format(z=z, x=x, y=y)))
        req.setRawHeader(b"User-Agent", b"EDIFICE-desktop/1.0 (building dashboard)")
        req.setAttribute(QNetworkRequest.CacheLoadControlAttribute, QNetworkRequest.PreferCache)
        reply = self._net.get(req)
        reply.finished.connect(lambda r=reply, k=key: self._tile_done(r, k))

    def _tile_done(self, reply, key):
        from PySide6.QtGui import QImage, QPainter, QPixmap
        self._pending.discard(key)
        img = QImage()
        if reply.error() == reply.NetworkError.NoError and img.loadFromData(reply.readAll().data()):
            g = img.convertToFormat(QImage.Format_Grayscale8)
            g.invertPixels()
            out = g.convertToFormat(QImage.Format_ARGB32)
            q = QPainter(out)
            q.setCompositionMode(QPainter.CompositionMode_Multiply)
            q.fillRect(out.rect(), QColor("#4FD8B0"))     # yeşilimsi ton: marka rengiyle uyumlu koyu harita
            q.end()
            self._tiles[key] = QPixmap.fromImage(out)
            self.update()
        reply.deleteLater()

    def _draw_tile(self, p, z: int, tx: int, ty: int, target: QRectF) -> bool:
        n = 2 ** z
        pm = self._tiles.get((z, tx % n, ty))
        if pm is not None:
            p.drawPixmap(target, pm, QRectF(pm.rect()))
            return True
        for k in range(1, 5):                      # inmemiş karo: üst seviyeden bulanık göster
            if z - k < 0:
                break
            parent = self._tiles.get((z - k, (tx % n) >> k, ty >> k))
            if parent is not None:
                size = self.TILE / 2 ** k
                sx = ((tx % n) % 2 ** k) * size
                sy = (ty % 2 ** k) * size
                p.drawPixmap(target, parent, QRectF(sx, sy, size, size))
                return True
        return False

    def paintEvent(self, e):
        import math
        from PySide6.QtGui import QPainter, QPainterPath, QPen
        from .widgets import qfont, rgba
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h, T = self.width(), self.height(), self.TILE
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), 14, 14)
        p.setClipPath(clip)
        p.fillRect(self.rect(), QColor("#0B1624"))
        z = max(0, min(18, int(round(self.zf))))
        scale = 2 ** (self.zf - z)
        ts = T * scale
        cx, cy = self._world(self.clat, self.clon, self.zf)
        x0, y0 = cx - w / 2, cy - h / 2
        n = 2 ** z
        for tx in range(int(x0 // ts) - 1, int((x0 + w) // ts) + 2):
            for ty in range(int(y0 // ts) - 1, int((y0 + h) // ts) + 2):
                if not 0 <= ty < n:
                    continue
                inside = x0 - ts <= tx * ts <= x0 + w and y0 - ts <= ty * ts <= y0 + h
                if inside:
                    if not self._draw_tile(p, z, tx, ty, QRectF(tx * ts - x0, ty * ts - y0, ts + 0.6, ts + 0.6)):
                        self._request((z, tx % n, ty))
                    elif (z, tx % n, ty) not in self._tiles:
                        self._request((z, tx % n, ty))
                else:
                    self._request((z, tx % n, ty))      # kenar payı: kaydırırken boşluk görünmesin
        vg = QRectF(0, 0, w, h)
        from PySide6.QtGui import QRadialGradient
        g = QRadialGradient(QPointF(w / 2, h / 2), max(w, h) * 0.65)
        g.setColorAt(0.6, rgba("#070C12", 0.0))
        g.setColorAt(1.0, rgba("#070C12", 0.55))
        p.fillRect(vg, g)
        for i, (_, name, lat, lon, health) in enumerate(self.points):
            pt = self._xy(lat, lon)
            col = score_color(health)
            r = 9 if i == self._hover else 7
            p.setPen(Qt.NoPen)
            p.setBrush(rgba(col, 0.28))
            p.drawEllipse(pt, r + 9, r + 9)
            p.setBrush(QColor(col))
            p.setPen(QPen(QColor("#050A0E"), 2))
            p.drawEllipse(pt, r, r)
            if i == self._hover:
                p.setFont(qfont(12, 700))
                tw = p.fontMetrics().horizontalAdvance(name)
                box = QRectF(pt.x() + r + 10, pt.y() - 13, tw + 20, 26)
                p.setPen(QPen(rgba("#FFFFFF", 0.12), 1))
                p.setBrush(rgba("#0B1624", 0.92))
                p.drawRoundedRect(box, 13, 13)
                p.setPen(QColor("#E8F2FF"))
                p.drawText(box, Qt.AlignCenter, name)
        p.setPen(rgba("#E8F2FF", 0.55))
        p.setFont(qfont(10))
        p.drawText(QPointF(12, h - 8), "© OpenStreetMap katkıda bulunanlar")
        p.end()

    # ---- etkileşim
    def _hit(self, pos) -> int:
        for i, (_, _, lat, lon, _) in enumerate(self.points):
            q = self._xy(lat, lon)
            if (q.x() - pos.x()) ** 2 + (q.y() - pos.y()) ** 2 <= 18 ** 2:
                return i
        return -1

    def _zoom_step(self, v):
        self.zf = float(v)
        if self._anchor is not None:
            (alat, alon), pos = self._anchor
            ax, ay = self._world(alat, alon, self.zf)
            self.clat, self.clon = self._unworld(ax - (pos.x() - self.width() / 2), ay - (pos.y() - self.height() / 2), self.zf)
        self.update()

    def wheelEvent(self, e):
        step = 1 if e.angleDelta().y() > 0 else -1
        target = max(2.0, min(17.0, round(self._zanim.endValue() if self._zanim.state() == self._zanim.State.Running else self.zf) + step))
        pos = e.position()
        cx, cy = self._world(self.clat, self.clon, self.zf)
        lat, lon = self._unworld(cx + pos.x() - self.width() / 2, cy + pos.y() - self.height() / 2, self.zf)
        self._anchor = ((lat, lon), pos)
        self._zanim.stop()
        self._zanim.setStartValue(self.zf)
        self._zanim.setEndValue(float(target))
        self._zanim.start()
        e.accept()

    def _pan(self, dx: float, dy: float):
        cx, cy = self._world(self.clat, self.clon, self.zf)
        self.clat, self.clon = self._unworld(cx - dx, cy - dy, self.zf)
        self.update()

    def _inertia_step(self):
        self._vel *= 0.92
        if abs(self._vel.x()) + abs(self._vel.y()) < 0.4:
            self._inertia.stop()
            return
        self._pan(self._vel.x(), self._vel.y())

    def mousePressEvent(self, e):
        self._inertia.stop()
        self._press = e.position()
        self._last = e.position()
        self._vel = QPointF(0, 0)

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton and self._last is not None:
            d = e.position() - self._last
            self._last = e.position()
            self._vel = d * 0.6 + self._vel * 0.4
            self._pan(d.x(), d.y())
            return
        i = self._hit(e.position())
        if i != self._hover:
            self._hover = i
            self.setCursor(Qt.PointingHandCursor if i >= 0 else Qt.ArrowCursor)
            self.update()

    def mouseReleaseEvent(self, e):
        moved = (e.position() - self._press).manhattanLength() if self._press is not None else 99
        self._last = None
        if moved < 5:
            i = self._hit(e.position())
            if i >= 0:
                self.on_open(self.points[i][0])
        elif abs(self._vel.x()) + abs(self._vel.y()) > 2:
            self._inertia.start()
