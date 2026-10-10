"""Asistanın veri araçları: bellekteki Project nesnelerini okur (veritabanına dokunmaz, iş parçacığından güvenli)."""
from __future__ import annotations

import json

from ..evidence import render_markdown
from ..models import UtilityType
from ..service import Project


def _r(v, d=1):
    return None if v is None or v == float("inf") else round(float(v), d)


class Toolbox:
    """Araçların uygulaması: yalnız bellekteki Project nesnelerini okur (veritabanına dokunmaz, iş parçacığından güvenli)."""

    def __init__(self, projects: dict[int, Project], current: int | None, weather: dict | None = None):
        self.projects, self.current = projects, current
        self.weather = weather or {}
        self.solar: dict[int, list[float]] = {}       # bina -> 12 aylık kWh/kWp (PVGIS önbelleği)
        self.completed: dict[int, dict] = {}     # bina -> {öneri kodu: (yıl, ay)} (tamamlanan projeler)        # bina kimliği -> aylık derece-gün sözlüğü (önbellekten)

    def _p(self, args: dict) -> tuple[int, Project]:
        bid = args.get("building_id", self.current)
        if bid not in self.projects:
            raise ValueError(f"Bina bulunamadı: {bid}. list_buildings ile geçerli kimlikleri görün.")
        return bid, self.projects[bid]

    def run(self, name: str, args: dict) -> str:
        try:
            out = getattr(self, "t_" + name)(args or {})
        except Exception as e:      # model hatayı görüp düzeltebilsin
            out = {"hata": str(e)}
        return json.dumps(out, ensure_ascii=False)

    # ---- araçlar
    def t_list_buildings(self, a):
        rows = []
        for bid, p in self.projects.items():
            k, h = p.kpis(), p.health()
            codes = p.applicable_codes()
            sc = p.scenario(codes) if codes else None
            rows.append({"id": bid, "ad": p.building.name, "secili": bid == self.current, "kullanim": p.building.use_type,
                         "alan_m2": _r(p.building.floor_area_m2, 0), "saglik": _r(h.total, 0), "not": h.grade,
                         "enerji_sinifi": p.rating()["class"], "eui_kwh_m2": _r(k.eui_kwh_m2), "karbon_t": _r(k.carbon_kg / 1000),
                         "yillik_maliyet_TL": _r(k.total_cost, 0), "uygun_oneri_tasarruf_TL_yil": _r(sc.annual_saving, 0) if sc else 0,
                         "uygun_oneri_capex_TL": _r(sc.capex, 0) if sc else 0})
        return rows

    def t_get_building(self, a):
        bid, p = self._p(a)
        b, k, h, r = p.building, p.kpis(), p.health(), p.rating()
        lo, hi, eq = p.health_range()
        return {"id": bid, "ad": b.name, "adres": b.address, "kullanim": b.use_type, "alan_m2": b.floor_area_m2, "yapim_yili": b.year_built,
                "kat": b.floors, "kisi": b.occupants, "baz_yil": p.year,
                "kpi": {"elektrik_kwh": _r(k.electricity_kwh, 0), "dogalgaz_kwh": _r(k.gas_kwh, 0), "su_m3": _r(k.water_m3, 0),
                        "toplam_enerji_kwh": _r(k.total_energy_kwh, 0), "eui_kwh_m2": _r(k.eui_kwh_m2), "karbon_kg": _r(k.carbon_kg, 0),
                        "karbon_kg_m2": _r(k.carbon_kg_m2), "enerji_maliyet_TL": _r(k.energy_cost, 0), "su_maliyet_TL": _r(k.water_cost, 0),
                        "toplam_maliyet_TL": _r(k.total_cost, 0)},
                "saglik_skoru": {"toplam": _r(h.total, 0), "not": h.grade, "agirlik_duyarliligi": [_r(lo, 0), _r(hi, 0)],
                                 "bilesenler": {n: {"puan": _r(v[0], 0), "agirlik": v[1]} for n, v in h.components.items()}},
                "enerji_sinifi": {"sinif": r["class"], "ep": _r(r.get("ep")), "benchmark_eui": _r(r["benchmark"]), "yuzdelik": _r(r["percentile"], 0),
                                  "not": "tahmini; resmî EKB değil"},
                "yillik_degisim_yuzde": {k_: _r(v) for k_, v in p.yoy().items()}}

    def t_get_opportunities(self, a):
        bid, p = self._p(a)
        rng = p.opportunity_ranges()
        out = []
        for r in p.opportunity_results():
            o = r.opportunity
            out.append({"kod": o.code, "ad": o.name, "etkiledigi": o.affects.value, "uygunluk": r.fit, "uygunluk_gerekce": r.reason,
                        "capex_TL": _r(r.capex, 0), "yillik_tasarruf_TL": _r(r.annual_saving, 0), "geri_odeme_yil": _r(r.payback_years),
                        "tasarruf_orani": o.saving_pct, "oran_araligi": [o.saving_low, o.saving_high], "kanit_duzeyi": o.evidence_level,
                        "dayanak": o.basis, "tasarruf_TL_araligi": rng.get(o.code)})
        return out

    def t_simulate_scenario(self, a):
        bid, p = self._p(a)
        codes = [c for c in a.get("codes", []) if c in {o.code for o in p.opportunities}]
        mode = a.get("mode", "typ")
        s, f = p.scenario(codes, mode), p.finance(codes, mode)
        return {"secilen": codes, "mod": mode, "capex_TL": _r(s.capex, 0), "yillik_tasarruf_TL": _r(s.annual_saving, 0),
                "basit_geri_odeme_yil": _r(s.payback_years), "enerji_azalimi_yuzde": _r(s.energy_reduction_pct * 100),
                "karbon_azalimi_yuzde": _r(s.carbon_reduction_pct * 100),
                "mevcut": {"enerji_kwh": _r(s.current.total_energy_kwh, 0), "karbon_kg": _r(s.current.carbon_kg, 0), "maliyet_TL": _r(s.current.total_cost, 0)},
                "hedef": {"enerji_kwh": _r(s.target.total_energy_kwh, 0), "karbon_kg": _r(s.target.carbon_kg, 0), "maliyet_TL": _r(s.target.total_cost, 0)},
                "finans": {"npv_TL": _r(f.npv, 0), "irr": _r(f.irr, 4), "indirgenmis_geri_odeme_yil": _r(f.discounted_payback),
                           "toplam_net_kazanc_TL": _r(f.total_net, 0), "ufuk_yil": p.assumptions.horizon_years,
                           "iskonto": p.assumptions.discount_rate, "enerji_fiyat_artisi": p.assumptions.energy_escalation}}

    def t_best_package(self, a):
        bid, p = self._p(a)
        codes, fin = p.best_package(float(a["budget"]))
        return {"butce_TL": a["budget"], "paket": codes, "capex_TL": _r(fin.capex, 0) if codes else 0, "npv_TL": _r(fin.npv, 0) if codes else 0,
                "not": "" if codes else "Bu bütçeyle NPV'si pozitif paket yok."}

    def t_get_monthly(self, a):
        bid, p = self._p(a)
        u = UtilityType(a["utility"])
        year = a.get("year", p.year)
        return {"yil": year, "birim": "m3" if u == UtilityType.WATER else "kWh", "aylar": [_r(v, 0) for v in p.monthly(year, u)]}

    def t_get_weather_adjusted(self, a):
        from ..engine.weather_norm import normalize
        bid, p = self._p(a)
        dd = self.weather.get(bid)
        if not dd:
            return {"hata": "Bu bina için hava verisi yok (konum girilmemiş ya da henüz indirilmemiş)."}
        wn = normalize(p, dd)
        if wn is None:
            return {"hata": "Hava düzeltmesi için yeterli veri yok."}
        return {"yil": wn.year, "onceki_yil": wn.prev, "guven": wn.confidence, "normal_yil_sayisi": wn.normal_years,
                "ham_toplam_kwh": _r(wn.raw_total, 0), "duzeltilmis_toplam_kwh": _r(wn.norm_total, 0),
                "ham_degisim_yuzde": _r(wn.raw_change_pct), "duzeltilmis_degisim_yuzde": _r(wn.norm_change_pct),
                "turler": {n: {"kullanilabilir": u.ok, "r2": _r(u.r2, 2), "gozlem": u.n, "not": u.note,
                               "ham_kwh": {str(y): _r(v, 0) for y, v in u.raw.items()},
                               "duzeltilmis_kwh": {str(y): _r(v, 0) for y, v in u.normalized.items()}} for n, u in wn.by_utility.items()}}

    def t_get_mv(self, a):
        from ..engine.mv import measure
        bid, p = self._p(a)
        done = {c: (y, m) for c, (y, m) in (self.completed.get(bid) or {}).items()}
        if not done:
            return {"hata": "Bu binada tamamlandı olarak işaretlenmiş proje yok."}
        out = []
        for r in measure(p, self.weather.get(bid) or {}, done):
            out.append({"proje": r.name, "bitis": f"{r.completed[1]}/{r.completed[0]}", "olculebildi": r.ok, "not": r.note,
                        "oncesi_ay": r.n_pre, "sonrasi_ay": r.n_post, "tasarruf_kwh": _r(r.saved_kwh, 0), "tasarruf_yuzde": _r(r.saved_pct * 100),
                        "belirsizlik_kwh": _r(r.uncertainty_kwh, 0), "anlamli": r.significant, "katalog_beklentisi_kwh": _r(r.expected_kwh, 0),
                        "gerceklesme_yuzde": _r(r.realization_pct, 0), "model_guvenilir": r.model_ok, "cv_rmse": _r(r.cv_rmse, 3)})
        return out

    def t_get_solar(self, a):
        from ..engine import solar_sizing as ss
        from ..models import UtilityType as U
        bid, p = self._p(a)
        y = self.solar.get(bid)
        if not y:
            return {"hata": "Bu bina için güneş verisi yok (konum girilmemiş ya da henüz indirilmemiş; GES sayfasını bir kez açın)."}
        cons, price = p.monthly(p.year, U.ELECTRICITY), p.prices()[U.ELECTRICITY]
        if sum(cons) <= 0 or price <= 0:
            return {"hata": "Elektrik tüketimi ya da birim fiyatı yok."}
        cap = ss.max_kwp(p.building.floor_area_m2, p.building.floors)
        best, _ = ss.size_for_best_npv(y, cons, price, p.assumptions, cap)
        if best is None:
            return {"hata": "Varsayılan birim maliyetle NPV'si pozitif bir GES boyutu yok.", "cati_siniri_kwp": _r(cap, 0)}
        f = best.finance
        return {"kwp": best.kwp, "cati_siniri_kwp": _r(cap, 0), "yillik_uretim_kwh": _r(best.production_kwh, 0), "oz_tuketim_kwh": _r(best.self_kwh, 0),
                "elektrik_karsilama_yuzde": _r(best.coverage_pct), "yillik_tasarruf_TL": _r(best.saving, 0), "capex_TL": _r(best.capex, 0),
                "geri_odeme_yil": _r(f.simple_payback), "npv_TL": _r(f.npv, 0), "irr": _r(f.irr, 4), "karbon_onlenen_kg": _r(best.carbon_avoided_kg, 0),
                "varsayimlar": f"birim maliyet {ss.DEFAULT_CAPEX_PER_KWP:.0f} TL/kWp, eşzamanlılık %{ss.SELF_MATCH * 100:.0f}, fazla üretim değersiz; hepsi varsayım"}

    def t_get_price_analysis(self, a):
        from ..engine.pricing import analyze
        from ..models import UtilityType as U
        bid, p = self._p(a)
        out = {}
        for u, label in ((U.ELECTRICITY, "elektrik"), (U.GAS, "dogalgaz")):
            r = analyze(p, u)
            out[label] = {"analiz_edilebildi": r.ok and not r.tariff_derived, "not": r.note, "medyan_fiyat": _r(r.median_price, 2),
                          "supheli_aylar": [m.month for m in r.months if m.flagged], "olasi_fazla_odeme_TL": _r(r.excess_total, 0)}
        return out

    def t_get_data_quality(self, a):
        from ..quality import assess
        bid, p = self._p(a)
        q = assess(p)
        return {"skor": q.score, "seviye": q.level, "doluluk": round(q.completeness, 2),
                "sorunlar": [{"onem": i.severity, "alan": i.area, "mesaj": i.message} for i in q.issues]}

    def t_get_equipment(self, a):
        bid, p = self._p(a)
        return [{"kategori": e.category, "ad": e.name, "kurulum_yili": e.year_installed, "durum_1_5": e.condition, "not": e.notes}
                for e in p.equipment]

    def t_search_evidence(self, a):
        bid, p = self._p({})
        terms = [t for t in a.get("query", "").casefold().split() if len(t) > 1]
        lines = [ln for ln in render_markdown(p.assumptions).splitlines() if ln.strip()]
        scored = sorted(((sum(t in ln.casefold() for t in terms), i) for i, ln in enumerate(lines)), reverse=True)
        return [lines[i] for sc, i in scored[:10] if sc > 0] or ["Eşleşen kayıt yok."]
