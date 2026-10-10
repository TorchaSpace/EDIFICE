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

    def __init__(self, projects: dict[int, Project], current: int | None):
        self.projects, self.current = projects, current

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
