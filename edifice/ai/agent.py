"""EDIFI'CE yapay zeka asistanı: Anthropic Messages API (akışlı) + uygulamanın hesap motoruna bağlı araçlar.

Model uygulamanın verisini "içinde taşımaz" ve yeniden eğitilmez: her soruda araçlarla gerçek bina verisini,
hesap sonuçlarını ve kaynak kaydını (evidence.py) okur; sayıları buradan alır. Böylece cevaplar uygulamadaki
rakamlarla aynıdır ve kaynağı gösterilebilir."""
from __future__ import annotations

import json
from datetime import date
from typing import Callable

from ..evidence import render_markdown
from ..models import UtilityType
from ..service import Project

API_HOST = "api.anthropic.com"
API_VERSION = "2023-06-01"
MODELS = {"Sonnet 5.5 (dengeli)": "claude-sonnet-5-5", "Opus 5.5 (en güçlü)": "claude-opus-5-5", "Haiku 5.5 (hızlı)": "claude-haiku-5-5"}
DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_TOOL_ROUNDS = 8

SYSTEM = """Sen EDIFI'CE uygulamasının bina enerji ve dönüşüm asistanısın. Kullanıcı bir yapı sahibi, tesis yöneticisi ya da yatırımcıdır.
Kurallar:
- Türkçe, kısa ve net yaz. Önce cevabı ver, sonra gerekirse gerekçeyi.
- Bina verisi, KPI, skor, sınıf, tasarruf, CAPEX, NPV/IRR gibi her sayıyı ARAÇLARDAN al; ezberden ya da tahminle sayı uydurma. Araç veri vermiyorsa bilmediğini söyle.
- Bir tasarruf ya da varsayım söylerken kanıt düzeyini belirt (birincil, özet, ikincil, varsayım). Düzeyi bilmiyorsan search_evidence ile ara.
- Enerji sınıfı tahminidir, resmî Enerji Kimlik Belgesi değildir; bunu gerektiğinde hatırlat. Geri ödeme ve NPV girdi varsayımlarına bağlıdır, belirsizliği (düşük/yüksek aralık) söyle.
- Birden çok bina varsa kullanıcı belirtmedikçe seçili binayı kullan; portföy sorularında list_buildings kullan.
- Yatırım ya da finansal tavsiye verme; seçenekleri ve sayılarını sun, kararı kullanıcıya bırak.
- Uygulama kapsamı dışındaki konularda (ör. bina enerjisiyle ilgisiz) nazikçe kapsamı hatırlat.
Yöntem özeti: Health Score 4 bileşenin ağırlıklı toplamı (enerji yoğunluğu, karbon yoğunluğu, su yoğunluğu, ekipman durumu); enerji sınıfı BEP-TR Ep ölçeği (A<40, B<80, C<100, D<120, E<140, F<175, G); finans 20 yıl reel, iskonto ve enerji fiyat artışı Ayarlar'dadır; emisyon faktörü elektrik 0,469, doğalgaz 0,202 kgCO2e/kWh."""

TOOLS = [
    {"name": "list_buildings", "description": "Portföydeki tüm binaların özeti: sağlık skoru, enerji sınıfı, EUI, karbon, uygun önerilerle tasarruf potansiyeli. Seçili binayı da işaretler.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_building", "description": "Bir binanın profili, KPI'ları (enerji, karbon, su, maliyet), Health Score bileşenleri, enerji sınıfı ve yıllık değişim.",
     "input_schema": {"type": "object", "properties": {"building_id": {"type": "integer", "description": "Verilmezse seçili bina"}}}},
    {"name": "get_opportunities", "description": "Binanın dönüşüm önerileri: uygunluk (ekipmana göre), CAPEX, yıllık tasarruf ve aralığı, geri ödeme, kanıt düzeyi ve dayanağı.",
     "input_schema": {"type": "object", "properties": {"building_id": {"type": "integer"}}}},
    {"name": "simulate_scenario", "description": "Seçilen öneri kodlarını uygulayınca mevcut vs hedef, CAPEX, tasarruf, geri ödeme, NPV, IRR. mode: low/typ/high tasarruf varsayımı.",
     "input_schema": {"type": "object", "properties": {"building_id": {"type": "integer"}, "codes": {"type": "array", "items": {"type": "string"}}, "mode": {"type": "string", "enum": ["low", "typ", "high"]}}, "required": ["codes"]}},
    {"name": "best_package", "description": "Verilen bütçeyle (₺) net bugünkü değeri en yüksek öneri paketini bulur.",
     "input_schema": {"type": "object", "properties": {"building_id": {"type": "integer"}, "budget": {"type": "number"}}, "required": ["budget"]}},
    {"name": "get_monthly", "description": "Aylık tüketim değerleri. utility: electricity, gas, water. Birimler: kWh (elektrik, doğalgaz), m3 (su).",
     "input_schema": {"type": "object", "properties": {"building_id": {"type": "integer"}, "utility": {"type": "string", "enum": ["electricity", "gas", "water"]}, "year": {"type": "integer"}}, "required": ["utility"]}},
    {"name": "get_equipment", "description": "Binanın ekipman envanteri: kategori, ad, kurulum yılı, durum (1-5), not.",
     "input_schema": {"type": "object", "properties": {"building_id": {"type": "integer"}}}},
    {"name": "search_evidence", "description": "Kaynak ve yöntem kaydında arar: varsayımların kaynağı, kanıt düzeyi, resmî eşikler, emisyon faktörleri. Anahtar kelime ver.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
]


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


class ChatError(Exception):
    pass


def _sse_events(buf: bytearray):
    """Tamamlanmış SSE olaylarını (olay_adı, veri) döndürür ve tamponu keser."""
    while True:
        i = buf.find(b"\n\n")
        if i < 0:
            return
        raw, del_to = bytes(buf[:i]).decode("utf-8", "replace"), i + 2
        del buf[:del_to]
        name, data = None, None
        for line in raw.splitlines():
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data = line[5:].strip()
        if name and data:
            yield name, json.loads(data)


def _error_text(status: int, body: str) -> str:
    try:
        msg = json.loads(body)["error"]["message"]
    except Exception:
        msg = body[:200]
    hint = {401: "API anahtarı geçersiz.", 403: "Bu anahtarın erişimi yok.", 404: "Model bulunamadı.",
            429: "İstek sınırına takıldı, biraz sonra deneyin.", 529: "Servis şu an yoğun, biraz sonra deneyin."}.get(status, "")
    return f"{hint} ({status}: {msg})".strip()


def _stream(key: str, model: str, system: str, messages: list, tools: list, cancel: Callable[[], bool]):
    """Anthropic akış olaylarını yield eder. Ağ katmanı Qt'nindir (sistem sertifika deposunu kullanır), bu yüzden
    paketlenmiş uygulamada ek sertifika paketi gerekmez. Çağıran iş parçacığında çalışmalıdır (QThread)."""
    from PySide6.QtCore import QEventLoop, QTimer, QUrl
    from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
    body = json.dumps({"model": model, "max_tokens": 4096, "system": system, "messages": messages, "tools": tools, "stream": True})
    nam = QNetworkAccessManager()
    req = QNetworkRequest(QUrl(f"https://{API_HOST}/v1/messages"))
    req.setRawHeader(b"x-api-key", key.encode())
    req.setRawHeader(b"anthropic-version", API_VERSION.encode())
    req.setRawHeader(b"content-type", b"application/json")
    req.setTransferTimeout(90_000)
    reply = nam.post(req, body.encode("utf-8"))
    loop = QEventLoop()
    reply.readyRead.connect(loop.quit)
    reply.finished.connect(loop.quit)
    buf = bytearray()
    raw_all = bytearray()
    try:
        while True:
            QTimer.singleShot(150, loop.quit)      # iptal ve zaman aşımı kontrolü için aralıklı uyan
            if not reply.isFinished():
                loop.exec()
            if cancel():
                reply.abort()
                return
            chunk = bytes(reply.readAll())
            buf += chunk
            raw_all += chunk
            status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
            if status not in (None, 200):
                if reply.isFinished():
                    raise ChatError(_error_text(int(status), raw_all.decode("utf-8", "replace")))
                continue
            yield from _sse_events(buf)
            if reply.isFinished() and not reply.bytesAvailable():
                if status is None and reply.error() != reply.NetworkError.NoError:
                    raise ChatError(f"Bağlantı hatası: {reply.errorString()}")
                break
    finally:
        reply.deleteLater()


def run_chat(key: str, model: str, messages: list, toolbox: Toolbox, building_name: str, on_text: Callable[[str], None],
             on_tool: Callable[[str], None], cancel: Callable[[], bool], stream=None) -> None:
    """Bir kullanıcı sorusunu cevaplar: araç çağrılarını çalıştırıp sonuçlarla devam eder. messages yerinde güncellenir."""
    stream = stream or _stream
    system = SYSTEM + f"\nBugün: {date.today():%d.%m.%Y}. Seçili bina: {building_name} (id {toolbox.current})."
    for _ in range(MAX_TOOL_ROUNDS):
        blocks: dict[int, dict] = {}
        stop = None
        for ev, d in stream(key, model, system, messages, TOOLS, cancel):
            if ev == "content_block_start":
                cb = d["content_block"]
                blocks[d["index"]] = {"type": cb["type"], "text": "", "json": "", "id": cb.get("id"), "name": cb.get("name")}
            elif ev == "content_block_delta":
                b, dl = blocks[d["index"]], d["delta"]
                if dl["type"] == "text_delta":
                    b["text"] += dl["text"]
                    on_text(dl["text"])
                elif dl["type"] == "input_json_delta":
                    b["json"] += dl["partial_json"]
            elif ev == "message_delta":
                stop = d["delta"].get("stop_reason") or stop
            elif ev == "error":
                raise ChatError(d.get("error", {}).get("message", "Bilinmeyen hata"))
        if cancel():
            return
        content = []
        for i in sorted(blocks):
            b = blocks[i]
            if b["type"] == "text" and b["text"]:
                content.append({"type": "text", "text": b["text"]})
            elif b["type"] == "tool_use":
                content.append({"type": "tool_use", "id": b["id"], "name": b["name"], "input": json.loads(b["json"] or "{}")})
        if not content:
            return
        messages.append({"role": "assistant", "content": content})
        calls = [c for c in content if c["type"] == "tool_use"]
        if stop != "tool_use" or not calls:
            return
        results = []
        for c in calls:
            on_tool(c["name"])
            results.append({"type": "tool_result", "tool_use_id": c["id"], "content": toolbox.run(c["name"], c["input"])})
        messages.append({"role": "user", "content": results})
        on_text("\n\n")
    on_text("\n\n(Araç çağrısı sınırına ulaşıldı; soruyu daha dar sorabilirsiniz.)")
