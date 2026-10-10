from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..db import Store
from ..engine.rating import CLASS_COLORS
from ..models import UtilityType
from ..service import Project
from .pages import MONTHS, _page
from .widgets import AMBER, G, INDIGO, MUTED, RED, SUB, Card, Panel, badge, fmt, fmt_years, grade_for, header, muted, score_color


def summarize(project: Project) -> dict:
    """Bir binanın portföy satırı için gerçek hesap çıktıları."""
    k, h = project.kpis(), project.health()
    codes = project.applicable_codes()
    fin = project.finance(codes) if codes else None
    sc = project.scenario(codes) if codes else None
    from ..quality import assess
    q = assess(project)
    return {"quality": q, "project": project, "kpis": k, "health": h.total, "grade": h.grade, "rating": project.rating()["class"],
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
        qd = badge(f"Veri {r['quality'].level}", {"Yüksek": G, "Orta": AMBER, "Düşük": RED}[r["quality"].level])
        qd.setFixedHeight(24)
        qd.setToolTip("; ".join(i.message for i in r["quality"].issues[:3]) or "Girdi verisinde sorun bulunmadı")
        h.addWidget(qd, 0, Qt.AlignVCenter)
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
    """Sürdürülebilirlik: portföy karbonu, hedef yolu, resmî eşikler. Hedef (yıl ve yüzde) kullanıcının kararıdır, varsayılan kendi kararım değildir."""

    def __init__(self, store: Store, on_open):
        from PySide6.QtWidgets import QSpinBox
        from .pages import _fit_height, _set_row, _table, bar_chart
        from .projects_page import STATUSES
        from .widgets import Ring
        self.store = store
        self.widget, lay = _page()
        rows = [(bid, summarize(store.load_project(bid))) for bid, _ in store.list_buildings()]
        lay.addWidget(header("Sürdürülebilirlik", "Karbon ve ESG göstergeleri",
                             "Emisyon faktörleri: elektrik 0,469 kgCO₂e/kWh (ETKB 2023), doğalgaz 0,202 (IPCC). Sınıflar tahminidir, resmî EKB değildir."))
        if not rows:
            return
        base_year = max(r["project"].year for _, r in rows)
        prev_year = base_year - 1
        cur = sum(r["kpis"].carbon_kg for _, r in rows) / 1000
        have_prev = all(r["project"].previous_year() is not None for _, r in rows)
        baseline = sum(r["project"].kpis_for(prev_year).carbon_kg for _, r in rows) / 1000 if have_prev else cur
        baseline_year = prev_year if have_prev else base_year
        full = 0.0          # tüm uygun öneriler uygulanırsa
        saved_by_year: dict[int, float] = {}
        per_building: dict[int, dict[int, float]] = {}
        per_building_kwh: dict[int, dict[int, float]] = {}
        for bid, r in rows:
            p_ = r["project"]
            res = {x.opportunity.code: x for x in p_.opportunity_results()}
            codes = p_.applicable_codes()
            sc = p_.scenario(codes) if codes else None
            full += (sc.target.carbon_kg if sc else r["kpis"].carbon_kg) / 1000
            for code, (st_, yr) in store.load_projects(bid).items():
                if st_ != STATUSES[0] and code in res:
                    saved_by_year[yr] = saved_by_year.get(yr, 0.0) + res[code].saved_carbon_kg / 1000
                    per_building.setdefault(bid, {})[yr] = per_building.get(bid, {}).get(yr, 0.0) + res[code].saved_carbon_kg
                    per_building_kwh.setdefault(bid, {})[yr] = per_building_kwh.get(bid, {}).get(yr, 0.0) + res[code].saved_kwh

        t_year = int(store.get_setting("esg_target_year", "2030"))
        t_pct = float(store.get_setting("esg_target_pct", "40"))
        target = baseline * (1 - t_pct / 100)

        def progress(now: float) -> float:
            return 100 * (baseline - now) / (baseline - target) if baseline > target else 0.0

        ok_c = sum(1 for _, r in rows if r["rating"] in ("A", "B", "C"))
        avg_health = sum(r["health"] for _, r in rows) / len(rows)
        ring_row = QHBoxLayout()
        ring_row.setSpacing(16)
        rp = Panel(eyebrow="Hedefe ilerleme", title="Radyal göstergeler",
                   subtitle=f"Hedef: {baseline_year} karbonuna göre {t_year}'e kadar %{t_pct:.0f} azalım (aşağıdan değiştirebilirsiniz).")
        rr = QHBoxLayout()
        rr.setSpacing(10)
        for val, col, label, sub in (
                (progress(cur), G, "Karbon hedefi", f"{baseline:.0f} → {cur:.0f} tCO₂"),
                (progress(full), INDIGO, "Öneriler uygulanırsa", f"{full:.0f} tCO₂ (hedef {target:.0f})"),
                (100 * ok_c / len(rows), AMBER, "Sınıf C ve üstü", f"{ok_c}/{len(rows)} bina"),
                (avg_health, score_color(avg_health), "Ortalama sağlık", f"{avg_health:.0f}/100")):
            rr.addWidget(Ring(val, col, label, sub))
        rp.lay.addLayout(rr)
        lay.addWidget(rp)

        # ---- karbon yolu
        years = list(range(baseline_year, max(t_year, base_year) + 1))
        path = [baseline + (target - baseline) * (y - baseline_year) / max(t_year - baseline_year, 1) for y in years]
        actual = []
        for y in years:
            if y == baseline_year:
                actual.append(baseline)
            elif y == base_year:
                actual.append(cur)
            else:
                actual.append(0.0)
        plan, run = [], cur
        for y in years:
            if saved_by_year and y > base_year:
                run -= saved_by_year.get(y, 0.0)
                plan.append(max(run, 0.0))
            else:
                plan.append(0.0)
        cp = Panel(eyebrow="Karbon yolu", title=f"{baseline_year}–{years[-1]} karbon yolu (tCO₂)",
                   subtitle="Gerçekleşen yıllar gerçek veriden; “Plan”, Proje takibi'nde tarih verdiğiniz projelerin tasarrufuyla hesaplanır; “Hedef yolu” doğrusal azalımdır.")
        cp.lay.addWidget(bar_chart([str(y) for y in years], {"Hedef yolu": path, "Gerçekleşen": actual, "Plan": plan},
                                   scale=1.0, unit="tCO₂", colors=["slate", "green", "indigo"], min_h=240), 1)
        lay.addWidget(cp)

        # ---- hedef ayarı
        tp = Panel(eyebrow="Hedef", title="Karbon hedefini belirle", subtitle="Kendi hedefinizi yazın; yukarıdaki grafikler ve halkalar buna göre hesaplanır.")
        hr = QHBoxLayout()
        hr.setSpacing(12)
        ys, ps = QSpinBox(), QSpinBox()
        ys.setRange(base_year + 1, base_year + 40)
        ys.setValue(max(t_year, base_year + 1))
        ys.setSuffix(" yılına kadar")
        ps.setRange(1, 100)
        ps.setValue(int(t_pct))
        ps.setSuffix(" % azalım")
        for w_ in (ys, ps):
            w_.setMinimumHeight(36)
            w_.setFixedWidth(170)
        save = QPushButton("Kaydet")
        save.setObjectName("primary")
        save.setCursor(Qt.PointingHandCursor)
        save.setMinimumHeight(36)

        def _save():
            store.set_setting("esg_target_year", str(ys.value()))
            store.set_setting("esg_target_pct", str(ps.value()))
            note.setText("Kaydedildi; sayfa yeniden açıldığında hesaplar güncellenir (başka bir sekmeye geçip dönün).")
        save.clicked.connect(_save)
        note = QLabel("")
        note.setStyleSheet(f"color: {SUB}; font-size: 12px; background: transparent;")
        hr.addWidget(ys)
        hr.addWidget(ps)
        hr.addWidget(save)
        hr.addWidget(note, 1)
        tp.lay.addSpacing(6)
        tp.lay.addLayout(hr)
        lay.addWidget(tp)

        # ---- resmî eşikler (sertifika takibi yerine gerçek mevzuat eşikleri)
        th = Panel(eyebrow="Mevzuat eşikleri", title="Enerji sınıfı eşikleri",
                   subtitle="BEP Yönetmeliği: yeni bina D ve altı olamaz (C ve üstü), düşük karbonlu belge ≥ C, NSEB ≥ B. Sınıflar tahminidir.")
        order = ["A", "B", "C", "D", "E", "F", "G"]
        for bid, r in sorted(rows, key=lambda x: -order.index(x[1]["rating"])):
            line = QHBoxLayout()
            nm = QLabel(r["project"].building.name)
            nm.setStyleSheet("font-size: 13px; font-weight: 700; background: transparent;")
            line.addWidget(nm, 1)
            after = r["project"].rating_after(r["project"].applicable_codes()) if r["project"].applicable_codes() else r["rating"]
            line.addWidget(badge(f"Şimdi {r['rating']}", CLASS_COLORS[r["rating"]]))
            line.addWidget(badge(f"Planla {after}", CLASS_COLORS[after]))
            for label, need in (("C", "C"), ("B", "B")):
                okk = order.index(after) <= order.index(need)
                line.addWidget(badge(("✓ " if okk else "✗ ") + f"≥ {label}", G if okk else RED))
            th.lay.addLayout(line)
        lay.addWidget(th)

        # ---- hedef yoluna göre risk ("stranded asset" yılı): kendi hedefinize göre, resmî bir yol değil
        risk = Panel(eyebrow="Hedef yolu riski", title="Binalar hedef yolunu ne zaman aşar?",
                     subtitle=f"Her binanın karbon yoğunluğu (kgCO₂/m²), {baseline_year} değerinden {t_year}'e doğrusal %{t_pct:.0f} azalan KENDİ HEDEF YOLUNUZLA kıyaslanır; "
                              "plan = Proje takibi'ndeki tarihli projelerin tasarrufu. Şebeke emisyonunun düşeceği varsayılmaz. Resmî CRREM yolu değildir.")
        rt = _table(["Bina", "Şimdi (kg/m²)", f"Hedef {t_year} (kg/m²)", "Plan " + str(t_year), "Yol aşım yılı", "Durum"], left_cols=1)
        risk_rows = []
        for bid, r in rows:
            pb, area_ = r["project"], r["project"].building.floor_area_m2
            if area_ <= 0:
                continue
            b0 = pb.kpis_for(prev_year).carbon_kg / area_ if have_prev else r["kpis"].carbon_kg / area_
            now_i = r["kpis"].carbon_kg / area_
            tgt_i = b0 * (1 - t_pct / 100)
            def path_at(y):
                return b0 + (tgt_i - b0) * min(max(y - baseline_year, 0) / max(t_year - baseline_year, 1), 1.0)
            def plan_at(y):
                cum = sum(v for yy, v in per_building.get(bid, {}).items() if yy <= y)
                return now_i - cum / area_
            years_ = range(base_year, t_year + 1)
            breach = next((y for y in years_ if plan_at(y) > path_at(y) + 1e-9), None)
            final = plan_at(t_year)
            status = "Hedefte" if breach is None else "Şimdi aşıyor" if breach == base_year else f"{breach}'de aşar"
            color = G if breach is None else RED if breach == base_year else AMBER
            risk_rows.append((r["project"].building.name, now_i, tgt_i, final, str(breach) if breach else "-", status, color))
        rt.setRowCount(len(risk_rows))
        for i, (nm, a_, b_, c_, y_, st_, col) in enumerate(risk_rows):
            _set_row(rt, i, [nm, fmt(a_, 1), fmt(b_, 1), fmt(c_, 1), y_, st_], colors={5: col}, mono_from=1)
        _fit_height(rt, max(len(risk_rows), 1))
        risk.lay.addWidget(rt)
        lay.addWidget(risk)

        from .crrem_panel import CrremPanel
        lay.addWidget(CrremPanel(store, rows, per_building, per_building_kwh, base_year))

        p2 = Panel(eyebrow="Bina bazında", title="Karbon sıralaması", subtitle="En yüksek karbon yoğunluğundan düşüğe. Binaya tıklayın.")
        for bid, r in sorted(rows, key=lambda x: -x[1]["kpis"].carbon_kg_m2):
            p2.lay.addWidget(PortfolioPage._row(bid, r, on_open))
        lay.addWidget(p2)
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
    prev = project.previous_year()
    if prev is not None:
        from statistics import median
        for u, label in ((UtilityType.ELECTRICITY, "Elektrik"), (UtilityType.GAS, "Doğalgaz")):
            now, before = project.monthly(project.year, u), project.monthly(prev, u)
            ratios = {i: now[i] / before[i] for i in range(12) if before[i] > 0}
            if len(ratios) < 6:
                continue
            med = median(ratios.values())
            odd = [(i, v / med - 1) for i, v in ratios.items() if med > 0 and abs(v / med - 1) > 0.25]
            if odd:
                i, d = max(odd, key=lambda x: abs(x[1]))
                out.append((AMBER, f"{label} tüketiminde anomali: {MONTHS[i]} ayı",
                            f"{MONTHS[i]} ayı geçen yılın aynı ayına göre diğer aylardaki değişime kıyasla %{abs(d) * 100:.0f} "
                            f"{'fazla' if d > 0 else 'az'}. Fatura, sayaç ya da kullanım değişikliğini kontrol edin."))
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
    """Otomatik bulgular: KPI'lar, öncelik rozetli kartlar, gerçek vs optimize tüketim ve bakım tahmini (hepsi hesap motorundan)."""

    def __init__(self, project: Project):
        from datetime import date
        from ..engine.health import service_life
        from .pages import area_chart
        self.widget, lay = _page()
        lay.addWidget(header("Yapay zeka", "Otomatik bulgular",
                             f"{project.building.name} için hesap motorunun çıkardığı öne çıkan noktalar. Kural tabanlıdır; yalnız bu binanın verisini okur."))
        found = insights(project)
        codes = project.applicable_codes()
        sc = project.scenario(codes) if codes else None
        today = date.today().year
        due = []
        for e in project.equipment:
            life = service_life(e.name, project.assumptions.equipment_life_years)
            left = e.year_installed + life - today
            if left <= 3 or e.condition <= 2:
                due.append((e, left))
        crit = sum(1 for c, _, _ in found if c == RED)
        grid = QGridLayout()
        grid.setSpacing(16)
        specs = [("Aktif bulgu", len(found), lambda v: f"{int(v)}", f"{crit} kritik", G if not crit else AMBER),
                 ("Öngörülen tasarruf", (sc.annual_saving if sc else 0) / 1e6, lambda v: f"{fmt(v, 2)} M ₺", "uygun önerilerin yıllık toplamı", G),
                 ("Ekipman riski", len(due), lambda v: f"{int(v)}", f"{len(project.equipment)} ekipmandan ömrü bitmek üzere/zayıf", AMBER),
                 ("Hedef enerji", (sc.energy_reduction_pct * 100) if sc else 0, lambda v: f"−%{fmt(v, 1)}", "tüm uygun öneriler uygulanırsa", INDIGO)]
        for i, (t, v, f, sub, acc) in enumerate(specs):
            c = Card(t, sub=sub, accent=acc)
            c.set_number(v, f, sub)
            grid.addWidget(c, 0, i)
        lay.addLayout(grid)

        row = QHBoxLayout()
        row.setSpacing(18)
        p = Panel(eyebrow="EDIFI'CE analiz", title="Öne çıkanlar")
        p.setMinimumWidth(420)
        for color, title, text in found:
            p.lay.addWidget(_insight_card(color, title, text))
        row.addWidget(p, 1)
        if sc:
            ratio_e = sc.target.electricity_kwh / sc.current.electricity_kwh if sc.current.electricity_kwh else 1
            ratio_g = sc.target.gas_kwh / sc.current.gas_kwh if sc.current.gas_kwh else 1
            el, gs = project.monthly(project.year, UtilityType.ELECTRICITY), project.monthly(project.year, UtilityType.GAS)
            actual = [a + b for a, b in zip(el, gs)]
            opt = [a * ratio_e + b * ratio_g for a, b in zip(el, gs)]
            cp = Panel(eyebrow="Gerçek vs optimize", title=f"Gerçek ve öneriler uygulanmış tüketim · {project.year}", subtitle="MWh · optimize = uygun tüm öneriler (tipik tasarruf)")
            cp.setMinimumWidth(420)
            cp.lay.addWidget(area_chart(MONTHS, {"Gerçek": actual, "Optimize": opt}, scale=1000, unit="MWh", colors=["indigo", "green"], min_h=260), 1)
            row.addWidget(cp, 1)
        lay.addLayout(row)

        mp = Panel(eyebrow="Bakım tahmini", title="Ekipman değişim zamanı",
                   subtitle="Kurulum yılı + tipik hizmet ömrü (ASHRAE, ikincil kaynak); durum 1-2 olanlar ayrıca işaretlenir.")
        if not due:
            mp.lay.addWidget(muted("Önümüzdeki 3 yılda ömrünü dolduracak ya da durumu zayıf ekipman yok."))
        for e, left in sorted(due, key=lambda x: x[1]):
            color = RED if left <= 0 or e.condition <= 2 else AMBER
            when = "ömrünü doldurdu" if left <= 0 else f"{left} yıl içinde"
            line = QHBoxLayout()
            nm = QLabel(f"{e.name} <span style='color:{MUTED}; font-size:11px'>{e.category} · {e.year_installed} · durum {e.condition}/5</span>")
            nm.setStyleSheet("font-size: 13px; font-weight: 600; background: transparent;")
            line.addWidget(nm, 1)
            line.addWidget(badge(("Acil · " if color == RED else "Planla · ") + when, color))
            mp.lay.addLayout(line)
        lay.addWidget(mp)
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
    top = QHBoxLayout()
    t = QLabel(title)
    t.setStyleSheet("font-size: 14px; font-weight: 700; background: transparent;")
    top.addWidget(t, 1)
    top.addWidget(badge({RED: "Kritik", AMBER: "Uyarı"}.get(color, "Bilgi"), color))
    d = QLabel(text)
    d.setWordWrap(True)
    d.setStyleSheet(f"color: {SUB}; font-size: 13px; background: transparent;")
    v.addLayout(top)
    v.addWidget(d)
    return w


class LocationMap(QWidget):
    """Canlı harita: OpenStreetMap karoları (standart renkler); bina noktaları üstte.
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
        self.zf = float(max(3, min(12, math.log2(360 / (span * 1.7)))))
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
        lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
        return max(-84.0, min(84.0, lat)), (x / n * 360 - 180 + 180) % 360 - 180

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
        from PySide6.QtGui import QImage, QPixmap
        self._pending.discard(key)
        img = QImage()
        if reply.error() == reply.NetworkError.NoError and img.loadFromData(reply.readAll().data()):
            out = img
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
        p.fillRect(QRectF(0, h - 18, 214, 18), rgba("#FFFFFF", 0.8))
        p.setPen(QColor("#333333"))
        p.setFont(qfont(10))
        p.drawText(QPointF(6, h - 5), "© OpenStreetMap katkıda bulunanlar")
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
        """Fare çarkı ve dokunmatik yüzey aynı davranır: delta toplanır, hedef zoma yumuşak geçilir."""
        dy = e.angleDelta().y()
        if not dy:
            e.accept()
            return
        base = getattr(self, "_ztarget", self.zf)
        if self._zanim.state() != self._zanim.State.Running:
            base = self.zf
        self._ztarget = max(2.0, min(17.0, base + max(-1.0, min(1.0, dy / 240.0))))
        pos = e.position()
        cx, cy = self._world(self.clat, self.clon, self.zf)
        lat, lon = self._unworld(cx + pos.x() - self.width() / 2, cy + pos.y() - self.height() / 2, self.zf)
        self._anchor = ((lat, lon), pos)
        self._zanim.stop()
        self._zanim.setStartValue(self.zf)
        self._zanim.setEndValue(self._ztarget)
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
            import time
            self._vel = d * 0.6 + self._vel * 0.4
            self._last_t = time.monotonic()
            self._pan(d.x(), d.y())
            return
        i = self._hit(e.position())
        if i != self._hover:
            self._hover = i
            self.setCursor(Qt.PointingHandCursor if i >= 0 else Qt.ArrowCursor)
            self.update()

    def mouseReleaseEvent(self, e):
        import time
        moved = (e.position() - self._press).manhattanLength() if self._press is not None else 99
        self._last = None
        if moved < 5:
            i = self._hit(e.position())
            if i >= 0:
                self.on_open(self.points[i][0])
        elif abs(self._vel.x()) + abs(self._vel.y()) > 3 and time.monotonic() - getattr(self, "_last_t", 0) < 0.06:
            self._inertia.start()
