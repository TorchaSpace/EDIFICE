"""EDIFI'CE'in kendi yapay zekası: tamamen yerel çalışır, dış servise bağlanmaz.

Bileşenler (hepsi bu dosyada, saf Python):
1. Niyet sınıflandırıcı: açılışta, aşağıdaki örnek cümlelerden karakter n-gram TF-IDF vektörleri öğrenir (Türkçe ek/yazım
   farklarına dayanıklı) ve soruyu en yakın niyete atar. Eğitim verisi INTENTS sözlüğüdür; yeni örnek ekleyerek "eğitilir".
2. Varlık çıkarımı: bütçe (2 milyon, 500 bin), öneri adı (led, chiller…), bina adı, yıl, enerji türü.
3. Cevap üretici: Toolbox ile gerçek hesap sonuçlarını okur, kaynak/kanıt düzeyiyle Türkçe cevap yazar.
Üretken bir dil modeli değildir: bilmediği soruda bunu söyler ve neleri cevaplayabildiğini listeler."""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field

from .tools import Toolbox

INTENTS: dict[str, list[str]] = {
    "greet": ["merhaba", "selam", "naber", "kimsin", "sen kimsin", "ne yapabilirsin", "yardım", "neler sorabilirim", "ne işe yararsın"],
    "overview": ["binam nasıl", "bina özeti", "genel durum", "binanın durumu nedir", "özetle", "bu bina hakkında bilgi ver",
                 "bina bilgileri", "binayı anlat", "durum raporu"],
    "problem": ["en büyük sorun ne", "sorunlar neler", "ne kötü gidiyor", "zayıf noktalar", "en zayıf bileşen", "neyi düzeltmeliyim",
                "binanın problemi ne", "neden kötü", "skor neden düşük", "ne yanlış"],
    "health": ["sağlık skoru kaç", "health score", "bina skoru", "skorum nasıl hesaplanıyor", "bina sağlığı", "puanım kaç"],
    "rating": ["enerji sınıfı nedir", "enerji sınıfım kaç", "sınıfım neden bu", "hangi sınıftayım", "enerji kimlik belgesi",
               "benzer binalara göre nasılım", "sınıf nasıl hesaplanıyor", "bep tr sınıfı"],
    "energy": ["toplam enerji tüketimi", "ne kadar enerji tüketiyoruz", "eui kaç", "kwh m2", "elektrik tüketimi ne kadar",
               "doğalgaz tüketimi ne kadar", "enerji yoğunluğu", "yıllık enerji"],
    "carbon": ["karbon salımı", "emisyon ne kadar", "co2 kaç ton", "karbon ayak izi", "kaç ton karbon", "karbon yoğunluğu", "sera gazı"],
    "water": ["su tüketimi", "su kullanımı ne kadar", "kaç metreküp su", "su yoğunluğu"],
    "cost": ["enerji maliyeti", "yıllık fatura", "ne kadar ödüyoruz", "enerji gideri kaç tl", "faturalar ne kadar", "toplam maliyet"],
    "trend": ["geçen yıla göre değişim", "artış mı azalış mı", "trend nasıl", "yıllık değişim", "geçen yıla kıyasla", "düştü mü arttı mı"],
    "peak": ["en çok tüketim hangi ay", "pik ay", "aylık tüketim", "hangi ay yüksek", "mevsimsel dağılım", "aylara göre tüketim"],
    "anomaly": ["anomali var mı", "olağandışı tüketim", "garip bir ay var mı", "sapma var mı", "ani artış", "tuhaf bir şey var mı"],
    "opportunities": ["öneriler neler", "dönüşüm önerileri", "hangi iyileştirmeler yapılabilir", "fırsatlar neler", "tasarruf önerileri",
                      "ne yapabiliriz", "hangi yatırımlar var", "öneri listesi"],
    "start": ["hangi öneriyle başlamalıyım", "önce ne yapmalıyım", "en iyi öneri hangisi", "en hızlı geri dönen", "en kârlı yatırım",
              "öncelik sırası", "nereden başlayayım", "en mantıklı yatırım"],
    "budget": ["bütçem var ne yapmalıyım", "2 milyon tl bütçeyle ne yapabilirim", "bütçeye göre paket", "param var ne önerirsin",
               "bütçe optimizasyonu", "500 bin lira ile", "bu bütçeyle hangi öneriler"],
    "scenario": ["led yaparsam ne olur", "senaryo hesapla", "şunu uygularsam ne olur", "chiller değişirse", "hepsini uygularsam",
                 "mevcut ve hedef karşılaştırma", "bunu yaparsak ne kadar tasarruf", "uygularsam sonuç ne"],
    "finance": ["geri ödeme süresi", "npv kaç", "irr nedir", "yatırım getirisi", "net bugünkü değer", "kendini kaç yılda öder",
                "capex ne kadar", "yatırım maliyeti", "kârlı mı", "finansal analiz"],
    "equipment": ["ekipmanlar neler", "ekipman envanteri", "chiller kaç yaşında", "kazan durumu", "eski ekipman var mı", "hvac durumu",
                  "cihazlar nasıl", "ekipman yaşı"],
    "portfolio": ["portföy özeti", "tüm binalar", "kaç binam var", "en kötü bina hangisi", "en iyi bina hangisi", "binaları karşılaştır",
                  "hangi bina öncelikli", "binalarım"],
    "evidence": ["bu oranlar nereden", "kaynak nedir", "neye dayanıyor", "kanıt düzeyi", "tasarruf oranları hangi kaynaklara dayanıyor",
                 "emisyon faktörü kaynağı", "güvenilir mi", "nasıl hesaplıyorsun", "varsayımlar neler", "literatür"],
}

OPP_WORDS = {"LED": ["led", "aydinlatma", "armatur", "floresan"], "CHILLER": ["chiller", "sogutucu", "soğutma", "klima", "sogutma"],
             "VFD": ["vfd", "fan", "pompa", "hiz kontrol", "surucu", "inverter"], "ENVELOPE": ["cati", "cephe", "yalitim", "izolasyon", "kabuk"],
             "BOILER": ["kazan", "yogusmali", "isitma"]}
STOP = set("nasil ne nedir kadar kac neden hangi var mi mu bu su bir icin ile ve da de en cok daha ben bana sen biz mi ya peki bunu sunu olur olursa yapayim yapmaliyim yapabilirim".split())
FOLD = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosuCGIOSUaiu")


def norm(text: str) -> str:
    t = text.replace("İ", "i").replace("I", "ı").lower().translate(FOLD)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ,.]", " ", t)).strip()


def _grams(t: str) -> Counter:
    t = f" {norm(t)} "
    return Counter(t[i:i + n] for n in (3, 4, 5) for i in range(len(t) - n + 1))


class IntentModel:
    """Karakter n-gram TF-IDF + kosinüs benzerliği. Örnek sayısı küçük olduğu için en yakın örneğe göre karar verir."""

    def __init__(self, intents: dict[str, list[str]] = INTENTS):
        self.raw = intents
        self.examples = [(name, _grams(ex)) for name, exs in intents.items() for ex in exs]
        df = Counter(g for _, c in self.examples for g in c)
        n = len(self.examples)
        self.idf = {g: math.log((1 + n) / (1 + d)) + 1 for g, d in df.items()}
        self.vecs = [(name, self._vec(c)) for name, c in self.examples]

    def _vec(self, c: Counter) -> dict:
        v = {g: (1 + math.log(k)) * self.idf.get(g, 1.0) for g, k in c.items()}
        norm_ = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {g: x / norm_ for g, x in v.items()}

    def content_overlap(self, text: str, intent: str) -> bool:
        """Sorunun anlamlı bir kelimesi, bu niyetin eğitim cümlelerinden birinde (ilk 4 harfle) geçiyor mu? Alan dışı soruları eler."""
        words = {w[:4] for w in norm(text).split() if w not in STOP and len(w) > 2}
        known = {w[:4] for ex in self.raw[intent] for w in norm(ex).split() if w not in STOP and len(w) > 2}
        return bool(words & known)

    def classify(self, text: str) -> list[tuple[str, float]]:
        q = self._vec(_grams(text))
        best: dict[str, float] = {}
        for name, v in self.vecs:
            s = sum(w * v.get(g, 0.0) for g, w in q.items())
            if s > best.get(name, 0):
                best[name] = s
        return sorted(best.items(), key=lambda kv: -kv[1])


@dataclass
class Memory:
    """Önceki turdan kalanlar: 'peki 3 milyon olursa?' gibi devam sorularını anlamak için."""
    intent: str = ""
    budget: float | None = None
    codes: list[str] = field(default_factory=list)


def parse_budget(text: str) -> float | None:
    t = norm(text).replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(milyon|mln|m\b|bin|k\b)?", t)
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(milyon|mln|m\b|bin|k\b)?", t):
        val, unit = float(m.group(1)), m.group(2)
        if unit in ("milyon", "mln", "m"):
            return val * 1e6
        if unit in ("bin", "k"):
            return val * 1e3
        if val >= 10_000:
            return val
    return None


def find_codes(text: str, toolbox: Toolbox) -> list[str]:
    t = norm(text)
    p = toolbox.projects[toolbox.current]
    have = {o.code for o in p.opportunities}
    out = [c for c, words in OPP_WORDS.items() if c in have and any(w in t for w in map(norm, words))]
    if "hepsi" in t or "tumunu" in t or "tum oneri" in t:
        out = [r.opportunity.code for r in p.opportunity_results() if r.fit != "none"]
    return out


def find_building(text: str, toolbox: Toolbox) -> int | None:
    t = norm(text)
    for bid, p in toolbox.projects.items():
        n = norm(p.building.name)
        if n and (n in t or any(len(w) > 3 and w in t for w in n.split())):
            return bid
    return None


def _tl(v) -> str:
    return f"{v:,.0f}".replace(",", ".") + " ₺"


def _m(v, d=2) -> str:
    return f"{v / 1e6:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".") + " M ₺"


def _n(v, d=0) -> str:
    return f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


class LocalAssistant:
    THRESHOLD = 0.32

    def __init__(self):
        self.model = IntentModel()

    def answer(self, question: str, toolbox: Toolbox, mem: Memory) -> str:
        bid = find_building(question, toolbox)
        if bid is not None and bid != toolbox.current:
            toolbox = Toolbox(toolbox.projects, bid)
        if bid is not None:        # bina adının kelimeleri niyeti bozmasın: çıkar; geriye anlamlı kelime kalmadıysa genel özet iste
            drop = set(norm(toolbox.projects[bid].building.name).split())
            question = " ".join(w for w in norm(question).split() if w not in drop)
            if not [w for w in question.split() if w not in STOP and len(w) > 2]:
                mem.intent = "overview"
                return self.a_overview(question, toolbox, None, [])
        ranked = self.model.classify(question)
        intent, score = ranked[0]
        budget = parse_budget(question)
        codes = find_codes(question, toolbox)
        if score < self.THRESHOLD or not self.model.content_overlap(question, intent) or (len(ranked) > 1 and score - ranked[1][1] < 0.02 and score < 0.5):
            if budget and mem.intent in ("budget", "scenario", "start"):
                intent = "budget"           # "peki 3 milyon olursa?"
            elif codes and mem.intent in ("scenario", "finance", "evidence", "opportunities", "start"):
                intent = mem.intent         # "ya chiller?"
            elif codes:
                intent = "scenario"
            else:
                return self._unknown()
        if budget and intent not in ("budget", "scenario"):
            intent = "budget" if "butce" in norm(question) or "param" in norm(question) else intent
        mem.intent, mem.budget = intent, budget or mem.budget
        mem.codes = codes or mem.codes
        fn = getattr(self, "a_" + intent)
        return fn(question, toolbox, budget, codes or ([] if intent != "scenario" else mem.codes))

    # ---- cevaplar
    def _unknown(self) -> str:
        return ("Bunu tam anlayamadım. Şunları cevaplayabilirim:\n\n"
                "- Bina özeti, sağlık skoru, enerji sınıfı\n- Enerji, karbon, su, maliyet ve yıllık değişim\n"
                "- Pik ay ve tüketim anomalileri\n- Dönüşüm önerileri, nereden başlanacağı, bütçeye göre paket\n"
                "- Senaryo (ör. “LED ve VFD yaparsam”), geri ödeme, NPV, IRR\n- Ekipman envanteri, portföy karşılaştırması\n"
                "- Rakamların kaynağı ve kanıt düzeyi\n\nÖrnek: “2 milyon ₺ bütçeyle ne yapmalıyım?”")

    def a_greet(self, q, t, b, c):
        return ("Merhaba! Ben EDIFI'CE'in kendi yapay zekasıyım; internet ya da dış servis kullanmadan, bu uygulamadaki hesaplara bakarak "
                "cevap veririm. Binanın durumunu, önerileri, finansı ve rakamların kaynağını sorabilirsin.\n\n" + self._unknown().split("\n\n", 1)[1])

    def a_overview(self, q, t, b, c):
        d = json.loads(t.run("get_building", {}))
        k, h, r = d["kpi"], d["saglik_skoru"], d["enerji_sinifi"]
        return (f"**{d['ad']}** · {d['kullanim']} · {_n(d['alan_m2'])} m² · {d['yapim_yili']}\n\n"
                f"- Sağlık skoru **{h['toplam']:.0f}/100** (not {h['not']})\n- Tahmini enerji sınıfı **{r['sinif']}** (EUI {_n(k['eui_kwh_m2'])} kWh/m², "
                f"benzer binalardan %{r['yuzdelik']:.0f}'inden daha çok tüketiyor)\n- Yıllık enerji {_n(k['toplam_enerji_kwh'] / 1000)} MWh, "
                f"karbon {_n(k['karbon_kg'] / 1000, 1)} tCO₂, maliyet {_m(k['toplam_maliyet_TL'])}\n\n"
                "İstersen en zayıf noktayı ya da önerileri anlatayım.")

    def a_problem(self, q, t, b, c):
        d = json.loads(t.run("get_building", {}))
        comps = sorted(d["saglik_skoru"]["bilesenler"].items(), key=lambda kv: kv[1]["puan"])
        worst, w = comps[0]
        lines = "\n".join(f"- {n}: {v['puan']:.0f}/100 (ağırlık %{v['agirlik'] * 100:.0f})" for n, v in comps)
        return (f"En zayıf bileşen **{worst}** ({w['puan']:.0f}/100, skordaki ağırlığı %{w['agirlik'] * 100:.0f}).\n\n{lines}\n\n"
                "Bu bileşeni en çok etkileyen önerileri görmek için “hangi öneriyle başlamalıyım?” diye sorabilirsin.")

    def a_health(self, q, t, b, c):
        d = json.loads(t.run("get_building", {}))["saglik_skoru"]
        lo, hi = d["agirlik_duyarliligi"]
        lines = "\n".join(f"- {n}: {v['puan']:.0f}/100 · ağırlık %{v['agirlik'] * 100:.0f}" for n, v in d["bilesenler"].items())
        return (f"Sağlık skoru **{d['toplam']:.0f}/100**, not **{d['not']}**. Ağırlıklar ±%50 değişirse skor {lo:.0f}–{hi:.0f} arasında kalır.\n\n{lines}\n\n"
                "Skor, dört bileşenin ağırlıklı toplamıdır; ağırlıklar Ayarlar'dan değiştirilebilir.")

    def a_rating(self, q, t, b, c):
        d = json.loads(t.run("get_building", {}))["enerji_sinifi"]
        p = t.projects[t.current]
        codes = p.applicable_codes()
        after = p.rating_after(codes) if codes else d["sinif"]
        extra = f" Uygun tüm öneriler uygulanırsa **{d['sinif']} → {after}**." if after != d["sinif"] else ""
        return (f"Tahmini enerji sınıfı **{d['sinif']}**. EUI'n kullanım tipinin kıyas değerine ({_n(d['benchmark_eui'])} kWh/m²·yıl) oranlanır "
                f"(Ep = 100 × EUI / kıyas); sınıf aralıkları resmî BEP-TR ölçeğidir.{extra}\n\n"
                "Not: Bu resmî Enerji Kimlik Belgesi değildir; kıyas değeri ENERGY STAR medyanıdır (kanıt düzeyi: ikincil).")

    def _kpi(self, t):
        return json.loads(t.run("get_building", {}))["kpi"]

    def a_energy(self, q, t, b, c):
        k = self._kpi(t)
        return (f"Yıllık toplam enerji **{_n(k['toplam_enerji_kwh'] / 1000)} MWh** (EUI {_n(k['eui_kwh_m2'], 1)} kWh/m²·yıl).\n\n"
                f"- Elektrik {_n(k['elektrik_kwh'] / 1000)} MWh\n- Doğalgaz {_n(k['dogalgaz_kwh'] / 1000)} MWh")

    def a_carbon(self, q, t, b, c):
        k = self._kpi(t)
        return (f"Yıllık karbon salımı **{_n(k['karbon_kg'] / 1000, 1)} tCO₂** ({_n(k['karbon_kg_m2'], 1)} kg/m²).\n\n"
                "Emisyon faktörleri: elektrik 0,469 kgCO₂e/kWh (ETKB 2023, birincil kaynak), doğalgaz 0,202 (IPCC).")

    def a_water(self, q, t, b, c):
        k = self._kpi(t)
        return f"Yıllık su tüketimi **{_n(k['su_m3'])} m³**."

    def a_cost(self, q, t, b, c):
        k = self._kpi(t)
        return (f"Yıllık toplam maliyet **{_m(k['toplam_maliyet_TL'])}**.\n\n- Enerji {_m(k['enerji_maliyet_TL'])}\n- Su {_m(k['su_maliyet_TL'])}")

    def a_trend(self, q, t, b, c):
        d = json.loads(t.run("get_building", {}))["yillik_degisim_yuzde"]
        if not d:
            return "Karşılaştırma için önceki yıla ait veri yok."
        names = {"energy": "Enerji", "carbon": "Karbon", "water": "Su", "electricity": "Elektrik", "gas": "Doğalgaz", "cost": "Maliyet"}
        lines = "\n".join(f"- {names.get(k, k)}: %{abs(v):.1f} {'arttı' if v > 0 else 'azaldı'}" for k, v in d.items())
        return "Geçen yıla göre değişim:\n\n" + lines

    def a_peak(self, q, t, b, c):
        p = t.projects[t.current]
        months = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        from ..models import UtilityType
        tot = [a + b_ for a, b_ in zip(p.monthly(p.year, UtilityType.ELECTRICITY), p.monthly(p.year, UtilityType.GAS))]
        order = sorted(range(12), key=lambda i: -tot[i])
        return (f"Tüketimin en yüksek olduğu ay **{months[order[0]]}** ({_n(tot[order[0]] / 1000)} MWh); en düşük **{months[order[-1]]}** "
                f"({_n(tot[order[-1]] / 1000)} MWh). İlk üç ay: {', '.join(months[i] for i in order[:3])}.")

    def a_anomaly(self, q, t, b, c):
        from ..ui.portfolio import insights
        found = [(ti, tx) for _, ti, tx in insights(t.projects[t.current]) if "anomali" in ti.lower() or "ortalamanın" in ti]
        if not found:
            return "Geçen yılın aynı aylarına göre belirgin bir sapma (%25'ten fazla) görmedim."
        return "\n\n".join(f"**{ti}**\n{tx}" for ti, tx in found)

    def a_opportunities(self, q, t, b, c):
        rows = [r for r in json.loads(t.run("get_opportunities", {})) if r["uygunluk"] != "none"]
        lines = "\n".join(f"- **{r['ad']}**: CAPEX {_m(r['capex_TL'])}, tasarruf {_tl(r['yillik_tasarruf_TL'])}/yıl, geri ödeme "
                          f"{'-' if r['geri_odeme_yil'] is None else _n(r['geri_odeme_yil'], 1) + ' yıl'} · uygunluk: {r['uygunluk']}" for r in rows)
        return f"Ekipmanına göre uygun {len(rows)} öneri var:\n\n{lines}\n\nKanıt düzeyini ya da senaryosunu sorabilirsin."

    def a_start(self, q, t, b, c):
        rows = [r for r in json.loads(t.run("get_opportunities", {})) if r["uygunluk"] != "none" and r["geri_odeme_yil"] is not None]
        if not rows:
            return "Uygun öneri bulamadım."
        rows.sort(key=lambda r: r["geri_odeme_yil"])
        b0 = rows[0]
        rng = b0["tasarruf_TL_araligi"]
        return (f"**{b0['ad']}** ile başla: geri ödeme **{_n(b0['geri_odeme_yil'], 1)} yıl**, CAPEX {_m(b0['capex_TL'])}, tipik tasarruf "
                f"{_tl(b0['yillik_tasarruf_TL'])}/yıl" + (f" (aralık {_tl(rng[0])}–{_tl(rng[1])})" if rng else "") +
                f".\n\nGerekçe: {b0['uygunluk_gerekce'] or 'ekipman durumu uygun'}. Kanıt düzeyi: **{b0['kanit_duzeyi']}**.\n\n"
                "Sıralama (geri ödemeye göre):\n" + "\n".join(f"{i}. {r['ad']} · {_n(r['geri_odeme_yil'], 1)} yıl" for i, r in enumerate(rows[:4], 1)))

    def a_budget(self, q, t, b, c):
        if not b:
            return "Bütçeyi yazar mısın? Örneğin “2 milyon ₺ bütçeyle ne yapmalıyım?”"
        d = json.loads(t.run("best_package", {"budget": b}))
        if not d["paket"]:
            return f"{_m(b)} bütçeyle net bugünkü değeri pozitif bir paket yok; bütçeyi artırmayı dene."
        names = {r["kod"]: r["ad"] for r in json.loads(t.run("get_opportunities", {}))}
        return (f"{_m(b)} bütçeyle NPV'yi en yükseğe çıkaran paket:\n\n" + "\n".join(f"- {names.get(k, k)}" for k in d["paket"]) +
                f"\n\nCAPEX {_m(d['capex_TL'])} · NPV **{_m(d['npv_TL'])}**.")

    def a_scenario(self, q, t, b, c):
        if not c:
            return "Hangi öneriyi uygulamak istiyorsun? Örneğin “LED ve VFD yaparsam ne olur?” ya da “hepsini uygularsam”."
        d = json.loads(t.run("simulate_scenario", {"codes": c}))
        f = d["finans"]
        return (f"**{', '.join(d['secilen'])}** uygulanırsa:\n\n- CAPEX {_m(d['capex_TL'])}, yıllık tasarruf {_tl(d['yillik_tasarruf_TL'])}\n"
                f"- Enerji %{d['enerji_azalimi_yuzde']:.1f}, karbon %{d['karbon_azalimi_yuzde']:.1f} azalır\n"
                f"- Basit geri ödeme {'-' if d['basit_geri_odeme_yil'] is None else _n(d['basit_geri_odeme_yil'], 1) + ' yıl'}\n"
                f"- {f['ufuk_yil']} yıllık NPV **{_m(f['npv_TL'])}**" + (f", IRR %{f['irr'] * 100:.1f}" if f["irr"] is not None else "") +
                "\n\nTasarruf oranları literatür aralıklarına dayanır (kanıt düzeyi: ikincil); düşük/yüksek senaryo için Mevcut vs Hedef ekranına bak.")

    def a_finance(self, q, t, b, c):
        p = t.projects[t.current]
        codes = c or p.applicable_codes()
        if not codes:
            return "Hesaplanacak uygun öneri yok."
        return self.a_scenario(q, t, b, codes)

    def a_equipment(self, q, t, b, c):
        rows = json.loads(t.run("get_equipment", {}))
        if not rows:
            return "Bu bina için ekipman girilmemiş."
        from datetime import date
        lines = "\n".join(f"- {r['kategori']} · {r['ad']}: {date.today().year - r['kurulum_yili']} yaşında, durum {r['durum_1_5']}/5"
                          + (f" ({r['not']})" if r["not"] else "") for r in rows)
        return "Ekipman envanteri:\n\n" + lines

    def a_portfolio(self, q, t, b, c):
        rows = json.loads(t.run("list_buildings", {}))
        rows.sort(key=lambda r: r["saglik"])
        lines = "\n".join(f"- **{r['ad']}**: skor {r['saglik']:.0f}, sınıf {r['enerji_sinifi']}, EUI {_n(r['eui_kwh_m2'])}, "
                          f"tasarruf potansiyeli {_tl(r['uygun_oneri_tasarruf_TL_yil'])}/yıl" for r in rows)
        return (f"Portföyde {len(rows)} bina var. En düşük skordan başlayarak:\n\n{lines}\n\n"
                f"Öncelik önerisi: **{rows[0]['ad']}** (en düşük sağlık skoru).")

    def a_evidence(self, q, t, b, c):
        p = t.projects[t.current]
        if c:
            rows = {r["kod"]: r for r in json.loads(t.run("get_opportunities", {}))}
            out = []
            for code in c:
                r = rows.get(code)
                if r:
                    out.append(f"**{r['ad']}**: tipik tasarruf %{r['tasarruf_orani'] * 100:.1f} (aralık %{r['oran_araligi'][0] * 100:.1f}–%{r['oran_araligi'][1] * 100:.1f}), "
                               f"kanıt düzeyi **{r['kanit_duzeyi']}**. Dayanak: {r['dayanak']}")
            if out:
                return "\n\n".join(out) + "\n\nCAPEX birim fiyatları doğrulanmamış varsayımdır."
        terms = [w for w in norm(q).split() if len(w) > 3 and w not in ("nereden", "kaynak", "nedir", "neye", "dayaniyor")]
        hits = json.loads(t.run("search_evidence", {"query": " ".join(terms) or q}))
        if hits == ["Eşleşen kayıt yok."]:
            return ("Kaynak düzeyleri: **birincil** (resmî belge), **özet** (derleme/meta-analiz), **ikincil** (tek çalışma/vaka), **varsayım** "
                    "(doğrulanamadı). Ayrıntı için Raporlar > Kaynaklar ve Yöntem ekranına bak; belirli bir konuyu (ör. “emisyon faktörü”) sorabilirsin.")
        return "Kaynak kaydından ilgili satırlar:\n\n" + "\n".join(f"- {h}" for h in hits[:6])


def stream_chunks(text: str, size: int = 5):
    """Cevabı yazılıyormuş gibi küçük parçalara böler (arayüzde canlı yazım etkisi)."""
    for i in range(0, len(text), size):
        yield text[i:i + size]
