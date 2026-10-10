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
    "why": ["neden böyle", "niye düştü", "skorum neden düştü", "bu öneri neden önde", "bu sonucu neden verdi", "sebebi ne", "niçin",
            "neden bu kadar kötü", "puanım neden düşük", "neden ilk sırada", "neden bu sınıf", "hangi etken etkiliyor"],
    "compare": ["karşılaştır", "ile karşılaştır", "hangisi daha iyi", "aradaki fark nedir", "elektrik mi doğalgaz mı daha çok",
                "geçen yılın ocağı ile bu ocak", "iki binayı karşılaştır", "hangisi daha fazla", "fark ne kadar"],
    "act_status": ["vfd yi planlandı yap", "ledi uygulanıyor olarak işaretle", "chiller projesi tamamlandı", "kazanı planla",
                   "projeyi başlat", "projeyi iptal et", "led projesini bitirdim", "durumunu değiştir"],
    "act_report": ["raporu oluştur", "pdf rapor al", "rapor indir", "yatırımcı raporu hazırla", "raporu hazırla"],
    "act_open": ["portföyü aç", "finans sayfasına git", "projeleri göster", "ayarları aç", "sürdürülebilirlik sayfasını göster",
                 "kaynaklara git", "genel bakışa dön", "tüketim sayfasını aç"],
    "act_scenario": ["senaryoyu uygula", "bu paketi senaryoya koy", "led ve vfd yi seç", "mevcut vs hedefte göster",
                     "senaryo sayfasında aç", "bu önerileri senaryoda seç", "seçili yap"],
    "quality": ["veri kalitesi", "verilerim güvenilir mi", "eksik veri var mı", "veri güvenilirliği", "girdiler doğru mu",
                "hatalı veri var mı", "veriye güvenebilir miyim", "sonuçlar ne kadar güvenilir"],
    "evidence": ["bu oranlar nereden", "kaynak nedir", "neye dayanıyor", "kanıt düzeyi", "tasarruf oranları hangi kaynaklara dayanıyor",
                 "emisyon faktörü kaynağı", "güvenilir mi", "nasıl hesaplıyorsun", "varsayımlar neler", "literatür"],
}

OPP_WORDS = {"LED": ["led", "aydinlatma", "armatur", "floresan"], "CHILLER": ["chiller", "sogutucu", "soğutma", "klima", "sogutma"],
             "VFD": ["vfd", "fan", "pompa", "hiz kontrol", "surucu", "inverter"], "ENVELOPE": ["cati", "cephe", "yalitim", "izolasyon", "kabuk"],
             "BOILER": ["kazan", "yogusmali", "isitma"]}
STOP = set("nasil ne nedir kadar kac neden hangi var mi mu bu su bir icin ile ve da de en cok daha ben bana sen biz mi ya peki bunu sunu olur olursa yapayim yapmaliyim yapabilirim".split())
MONTH_NAMES_SHORT = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
ACTION_VERBS = {"sec", "secili", "secin", "koy", "koyun", "ac", "acin", "goster", "ekle", "isaretle", "ayarla", "uygula"}
OPEN_VERBS = {"ac", "acin", "git", "gidelim", "goster", "gosterin", "don", "gec", "ziyaret"}
FOLD = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosuCGIOSUaiu")


def norm(text: str) -> str:
    t = text.replace("İ", "i").replace("I", "ı").lower().translate(FOLD)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ,.]", " ", t)).strip()


def _grams(t: str) -> Counter:
    t = f" {norm(t)} "
    return Counter(t[i:i + n] for n in (3, 4, 5) for i in range(len(t) - n + 1))


def accepts(extra: list[tuple[str, str]], intent: str, text: str) -> bool:
    """Bozulma koruması: yeni örnek eklenince yerleşik ve öğretilmiş TÜM örnekler hâlâ kendi niyetine düşmeli,
    yeni örneğin kendisi de hedef niyete düşmeli. Aksi halde örnek reddedilir."""
    if intent not in INTENTS or not norm(text):
        return False
    merged = {k: list(v) for k, v in INTENTS.items()}
    for i, t in list(extra) + [(intent, text)]:
        if i in merged:
            merged[i].append(t)
    m = IntentModel(merged)
    return all(m.classify(ex)[0][0] == name for name, exs in merged.items() for ex in exs)


def shares_content(a: str, b: str) -> bool:
    """İki cümle anlamlı bir kelimeyi (ilk 4 harf) paylaşıyor mu? (yeniden sorma tespiti)"""
    wa = {w[:4] for w in norm(a).split() if w not in STOP and len(w) > 2}
    wb = {w[:4] for w in norm(b).split() if w not in STOP and len(w) > 2}
    return bool(wa & wb)


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


INTENT_LABELS = {
    "overview": "Bina özeti", "problem": "Sorunlar / zayıf noktalar", "health": "Sağlık skoru", "rating": "Enerji sınıfı", "energy": "Enerji tüketimi",
    "carbon": "Karbon", "water": "Su", "cost": "Maliyet", "trend": "Yıllık değişim", "peak": "Pik ay", "anomaly": "Anomali",
    "opportunities": "Öneri listesi", "start": "Nereden başlamalı", "budget": "Bütçeye göre paket", "scenario": "Senaryo (ne olur?)",
    "finance": "Finans (NPV, geri ödeme)", "equipment": "Ekipman", "portfolio": "Portföy", "why": "Neden?", "compare": "Karşılaştırma",
    "quality": "Veri kalitesi", "evidence": "Kaynak / kanıt", "act_status": "İşlem: proje durumu", "act_report": "İşlem: rapor", "act_open": "İşlem: sayfa aç",
    "act_scenario": "İşlem: senaryo seç", "greet": "Selamlama / yardım"}


@dataclass
class Memory:
    """Önceki turdan kalanlar: 'peki 3 milyon olursa?' gibi devam sorularını anlamak için."""
    intent: str = ""
    budget: float | None = None
    codes: list[str] = field(default_factory=list)
    actions: list[tuple] = field(default_factory=list)   # arayüzün çalıştıracağı eylemler (durum değiştir, sayfa aç…)
    chart: dict | None = None                             # cevaba eşlik eden mini grafik tanımı
    unknown: str | None = None                            # anlaşılmayan soru (eğitim listesine düşer)
    answered: str | None = None                           # bu cevabı üreten niyet (👍/👎 ve öğrenme için)
    suggest: list[str] = field(default_factory=list)      # "şunu mu demek istedin?" niyet adayları
    learn: list[tuple[str, str]] = field(default_factory=list)   # yeniden sorma sinyalinden çıkan (niyet, soru) örnekleri
    pending_unknown: str | None = None                    # bir önceki turda anlaşılmayan soru


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


MONTH_ROOTS = {0: ("ocak", "ocag"), 1: ("suba",), 2: ("mart",), 3: ("nisa",), 4: ("mayi",), 5: ("hazi",), 6: ("temm",), 7: ("agus",),
               8: ("eylu",), 9: ("ekim",), 10: ("kasi",), 11: ("aral",)}
MONTH_NAMES = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
STATUS_WORDS = [("Planlanmadı", ("planlanmadi", "iptal", "kaldir")), ("Tamamlandı", ("tamamla", "bitti", "bitir")),
                ("Uygulanıyor", ("uygulaniyor", "basla", "baslat")), ("Planlandı", ("planla",))]
NAV_TARGETS = [(("portfoy",), ("Portföy", None)), (("finans",), ("Finans", None)), (("surdurulebilir", "esg"), ("Sürdürülebilirlik", None)),
               (("senaryo", "mevcut"), ("Projeler", "Mevcut vs Hedef")), (("proje", "takip"), ("Projeler", "Proje takibi")),
               (("oneri",), ("Projeler", "Öneriler")), (("tuketim",), ("Genel Bakış", "Tüketim")),
               (("genel bakis", "dashboard", "ozet"), ("Genel Bakış", "Genel Bakış")), (("ayar",), ("Ayarlar", None)),
               (("kaynak", "yontem"), ("Raporlar", "Kaynaklar ve Yöntem")), (("rapor",), ("Raporlar", "Rapor")),
               (("asistan", "sohbet"), ("Asistan", "Sohbet"))]


def find_months(text: str) -> list[int]:
    words = norm(text).split()
    return [i for i, roots in MONTH_ROOTS.items() if any(w.startswith(r) for w in words for r in roots)]


def find_status(text: str) -> str | None:
    t = norm(text)
    for status, words in STATUS_WORDS:
        if any(w in t for w in words):
            return status
    return None


def find_buildings(text: str, toolbox: Toolbox) -> list[int]:
    t = norm(text)
    out = []
    for bid, p in toolbox.projects.items():
        n = norm(p.building.name)
        if n and (n in t or any(len(w) > 3 and w in t.split() for w in n.split())):
            out.append(bid)
    return out


class LocalAssistant:
    THRESHOLD = 0.32
    _chart: dict | None = None
    _actions: list = []

    def __init__(self, extra: list[tuple[str, str]] | None = None):
        """extra: kullanıcının öğrettiği (niyet, cümle) çiftleri; yerleşik örneklere eklenerek model yeniden eğitilir."""
        merged = {k: list(v) for k, v in INTENTS.items()}
        for intent, text in extra or []:
            if intent in merged:
                merged[intent].append(text)
        self.model = IntentModel(merged)

    def answer(self, question: str, toolbox: Toolbox, mem: Memory) -> str:
        mem.actions, mem.chart, mem.unknown, mem.suggest, mem.learn, mem.answered = [], None, None, [], [], None
        pending, mem.pending_unknown = mem.pending_unknown, None
        found = find_buildings(question, toolbox)
        if len(found) >= 2:           # "A ile B'yi karşılaştır"
            mem.intent = mem.answered = "compare"
            return self._compare_buildings(toolbox, found)
        bid = find_building(question, toolbox)
        if bid is not None and bid != toolbox.current:
            toolbox = Toolbox(toolbox.projects, bid)
        if bid is not None:        # bina adının kelimeleri niyeti bozmasın: çıkar; geriye anlamlı kelime kalmadıysa genel özet iste
            drop = set(norm(toolbox.projects[bid].building.name).split())
            question = " ".join(w for w in norm(question).split() if w not in drop)
            if not [w for w in question.split() if w not in STOP and len(w) > 2]:
                mem.intent = mem.answered = "overview"
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
            else:
                return self._unknown(question, mem, ranked)
        if intent == "act_open" and not OPEN_VERBS & set(norm(question).split()):
            nq = norm(question)       # "sürdürülebilirlik durumu" gibi fiilsiz soru: sayfa açma değil, konunun kendisi
            intent = next((i for words, i in (("portfoy", "portfolio"), ("finans", "finance"), ("surdurulebilir", "carbon"), ("oneri", "opportunities"),
                                              ("tuketim", "energy"), ("kaynak", "evidence")) if words in nq), "overview")
        if intent == "act_scenario" and not ACTION_VERBS & set(norm(question).split()):
            intent = "scenario"        # fiil yoksa "led yaparsam ne olur" gibi bir ne-olur sorusudur
        if budget and intent not in ("budget", "scenario"):
            intent = "budget" if "butce" in norm(question) or "param" in norm(question) else intent
        mem.intent, mem.answered, mem.budget = intent, intent, budget or mem.budget
        if pending and shares_content(pending, question) and intent in INTENTS:
            mem.learn.append((intent, pending))          # yeniden sorma: ilk soru da bu niyete ait
        mem.codes = codes or mem.codes
        fn = getattr(self, "a_" + intent)
        self._chart, self._actions = None, []
        out = fn(question, toolbox, budget, codes or ([] if intent not in ("scenario", "act_scenario") else mem.codes))
        mem.chart, mem.actions = self._chart, self._actions
        return out

    def answer_as(self, intent: str, question: str, toolbox: Toolbox, mem: Memory) -> str:
        """Kullanıcı bir niyeti seçince (öneri düğmesi/Eğitim) soruyu o niyetle cevaplar."""
        mem.actions, mem.chart, mem.unknown, mem.suggest, mem.learn = [], None, None, [], []
        mem.pending_unknown = None
        budget, codes = parse_budget(question), find_codes(question, toolbox)
        mem.intent = mem.answered = intent
        self._chart, self._actions = None, []
        out = getattr(self, "a_" + intent)(question, toolbox, budget, codes or ([] if intent not in ("scenario", "act_scenario") else mem.codes))
        mem.chart, mem.actions = self._chart, self._actions
        return out

    # ---- cevaplar
    def _unknown(self, question: str = "", mem: Memory | None = None, ranked=None) -> str:
        if mem is not None:
            mem.unknown, mem.pending_unknown = question, question
            mem.suggest = [i for i, sc in (ranked or [])[:3] if sc >= 0.15 and i != "greet" and self.model.content_overlap(question, i)][:3]
            if mem.suggest:
                return "Tam emin olamadım. Aşağıdakilerden birini mi kastettin? Seçersen bunu öğrenirim."
        return ("Bunu tam anlayamadım. Şunları cevaplayabilirim:\n\n"
                "- Bina özeti, sağlık skoru, enerji sınıfı\n- Enerji, karbon, su, maliyet ve yıllık değişim\n"
                "- Pik ay ve tüketim anomalileri\n- Dönüşüm önerileri, nereden başlanacağı, bütçeye göre paket\n"
                "- Senaryo (ör. “LED ve VFD yaparsam”), geri ödeme, NPV, IRR\n- Ekipman envanteri, portföy karşılaştırması\n"
                "- Rakamların kaynağı ve kanıt düzeyi, “neden?” soruları\n- Karşılaştırma (iki bina, elektrik–doğalgaz, ay–yıl)\n"
                "- İşlem: proje durumunu değiştirme, sayfa açma, senaryo seçme, rapor üretme\n\n"
                "Örnek: “2 milyon ₺ bütçeyle ne yapmalıyım?” Anlamadığım soruları Asistan > Eğitim sekmesinde bana öğretebilirsin.")

    def a_quality(self, q, t, b, c):
        d = json.loads(t.run("get_data_quality", {}))
        if not d["sorunlar"]:
            return f"Girdi verisi **{d['seviye']}** güvenilirlikte ({d['skor']:.0f}/100); eksik ya da tutarsız bir şey bulmadım."
        lines = "\n".join(f"- **{i['onem']}** · {i['alan']}: {i['mesaj']}" for i in d["sorunlar"][:8])
        return (f"Girdi verisi güvenilirliği **{d['seviye']}** ({d['skor']:.0f}/100, son iki yılın %{d['doluluk'] * 100:.0f}'i dolu).\n\n{lines}\n\n"
                "Bu skor hesapların değil, girilen verinin güvenilirliğini gösterir; düzeltmek için bina düzenleme ekranını kullan.")

    def a_greet(self, q, t, b, c):
        return ("Merhaba! Ben EDIFI'CE'in kendi yapay zekasıyım; internet ya da dış servis kullanmadan, bu uygulamadaki hesaplara bakarak "
                "cevap veririm. Binanın durumunu, önerileri, finansı ve rakamların kaynağını sorabilirsin.\n\n" + self._unknown().split("\n\n", 1)[1])

    def a_overview(self, q, t, b, c):
        d = json.loads(t.run("get_building", {}))
        k, h, r = d["kpi"], d["saglik_skoru"], d["enerji_sinifi"]
        dq = json.loads(t.run("get_data_quality", {}))
        caveat = (f"\n\n⚠ Veri güvenilirliği **{dq['seviye']}** ({dq['skor']:.0f}/100): rakamlara temkinli yaklaş; ayrıntı için “veri kalitesi” diye sor."
                  if dq["seviye"] != "Yüksek" else "")
        return (f"**{d['ad']}** · {d['kullanim']} · {_n(d['alan_m2'])} m² · {d['yapim_yili']}\n\n"
                f"- Sağlık skoru **{h['toplam']:.0f}/100** (not {h['not']})\n- Tahmini enerji sınıfı **{r['sinif']}** (EUI {_n(k['eui_kwh_m2'])} kWh/m², "
                f"benzer binalardan %{r['yuzdelik']:.0f}'inden daha çok tüketiyor)\n- Yıllık enerji {_n(k['toplam_enerji_kwh'] / 1000)} MWh, "
                f"karbon {_n(k['karbon_kg'] / 1000, 1)} tCO₂, maliyet {_m(k['toplam_maliyet_TL'])}\n\n"
                "İstersen en zayıf noktayı ya da önerileri anlatayım." + caveat)

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
        self._chart = self._monthly_chart(t.projects[t.current])
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
        mem_chart = self._monthly_chart(p)
        self._chart = mem_chart
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
        self._chart = self._cash_chart(t.projects[t.current], d["paket"])
        return (f"{_m(b)} bütçeyle NPV'yi en yükseğe çıkaran paket:\n\n" + "\n".join(f"- {names.get(k, k)}" for k in d["paket"]) +
                f"\n\nCAPEX {_m(d['capex_TL'])} · NPV **{_m(d['npv_TL'])}**.")

    def a_scenario(self, q, t, b, c):
        if not c:
            return "Hangi öneriyi uygulamak istiyorsun? Örneğin “LED ve VFD yaparsam ne olur?” ya da “hepsini uygularsam”."
        d = json.loads(t.run("simulate_scenario", {"codes": c}))
        f = d["finans"]
        self._chart = self._cash_chart(t.projects[t.current], d["secilen"])
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

    # ---- grafik tanımları (arayüz çizer)
    def _monthly_chart(self, p) -> dict:
        from ..models import UtilityType
        now = [a + b for a, b in zip(p.monthly(p.year, UtilityType.ELECTRICITY), p.monthly(p.year, UtilityType.GAS))]
        groups = {str(p.year): now}
        if p.previous_year() is not None:
            groups[str(p.year - 1)] = [a + b for a, b in zip(p.monthly(p.year - 1, UtilityType.ELECTRICITY), p.monthly(p.year - 1, UtilityType.GAS))]
        return {"kind": "area", "title": "Aylık enerji tüketimi (MWh)", "cats": MONTH_NAMES_SHORT, "groups": groups, "scale": 1000, "unit": "MWh"}

    def _cash_chart(self, p, codes) -> dict | None:
        if not codes:
            return None
        f = p.finance(codes)
        return {"kind": "cash", "title": f"Kümülatif nakit akışı ({p.assumptions.horizon_years} yıl, M ₺)", "years": f.years, "cum": f.cumulative,
                "payback": None if f.simple_payback == float("inf") else f.simple_payback}

    # ---- neden?
    def a_why(self, q, t, b, c):
        n = norm(q)
        if "sinif" in n:
            return self.a_rating(q, t, b, c)
        if any(w in n for w in ("oner", "sira", "once", "ilk", "onde")):
            return self._why_top(t)
        return self._why_health(t)

    def _why_health(self, t) -> str:
        p = t.projects[t.current]
        k, h, a = p.kpis(), p.health(), p.assumptions
        use = p.building.use_type
        lines = []
        pts = {n: v[0] for n, v in h.components.items()}
        if pts["Enerji yoğunluğu"] < 60:
            lines.append(f"- **Enerji yoğunluğu** ({pts['Enerji yoğunluğu']:.0f}/100): EUI {_n(k.eui_kwh_m2)} kWh/m², kıyas {_n(a.benchmark_for(use))} "
                         f"(kıyasın %{100 * k.eui_kwh_m2 / a.benchmark_for(use):.0f}'i).")
        if pts["Karbon yoğunluğu"] < 60:
            lines.append(f"- **Karbon yoğunluğu** ({pts['Karbon yoğunluğu']:.0f}/100): {_n(k.carbon_kg_m2, 1)} kg/m², kıyas {_n(a.carbon_benchmark_for(use), 1)}.")
        if pts["Su yoğunluğu"] < 60:
            lines.append(f"- **Su yoğunluğu** ({pts['Su yoğunluğu']:.0f}/100): {_n(k.water_m3_m2, 2)} m³/m², kıyas {_n(a.benchmark_water_m3_m2, 2)}.")
        if pts["Ekipman durumu"] < 60:
            from datetime import date
            from ..engine.health import service_life
            rows = sorted(p.equipment, key=lambda e: (e.condition, e.year_installed))[:3]
            eq = "; ".join(f"{e.name} ({date.today().year - e.year_installed} yaş, durum {e.condition}/5)" for e in rows)
            lines.append(f"- **Ekipman durumu** ({pts['Ekipman durumu']:.0f}/100): en zayıflar: {eq}.")
        if not lines:
            return f"Skor **{h.total:.0f}/100** ve hiçbir bileşen zayıf değil (hepsi 60 üstü); en düşük bileşen {min(pts, key=pts.get)}."
        return (f"Skor **{h.total:.0f}/100** (not {h.grade}). Düşük kalmasının nedenleri:\n\n" + "\n".join(lines) +
                "\n\nBileşenlerin ağırlıkları: " + ", ".join(f"{n} %{v[1] * 100:.0f}" for n, v in h.components.items()) + ".")

    def _why_top(self, t) -> str:
        rows = [r for r in json.loads(t.run("get_opportunities", {})) if r["uygunluk"] != "none" and r["geri_odeme_yil"] is not None]
        if len(rows) < 2:
            return self.a_start("", t, None, [])
        rows.sort(key=lambda r: r["geri_odeme_yil"])
        a, b2 = rows[0], rows[1]
        return (f"**{a['ad']}** başta çünkü geri ödemesi en kısa: {_n(a['geri_odeme_yil'], 1)} yıl (ikinci sıradaki {b2['ad']}: {_n(b2['geri_odeme_yil'], 1)} yıl). "
                f"Yatırımı küçük ({_m(a['capex_TL'])}) ve yıllık tasarrufu {_tl(a['yillik_tasarruf_TL'])}; ekipman uygunluğu: {a['uygunluk']} "
                f"({a['uygunluk_gerekce'] or 'veriyle uyumlu'}). Tasarruf oranı için kanıt düzeyi **{a['kanit_duzeyi']}**; "
                f"düşük senaryoda bile {_tl(a['tasarruf_TL_araligi'][0])}/yıl.")

    # ---- karşılaştırma
    def a_compare(self, q, t, b, c):
        n = norm(q)
        months = find_months(q)
        if months:
            return self._month_yoy(t, months[0])
        if "elektrik" in n and "gaz" in n:
            return self._compare_utilities(t)
        return ("Neyi karşılaştırayım? Örnekler: “Merkez Ofis ile Plaza Kule'yi karşılaştır”, “elektrik mi doğalgaz mı daha çok”, "
                "“geçen yılın ocağı ile bu ocak”.")

    def _compare_buildings(self, t, ids) -> str:
        from .tools import Toolbox as _T
        rows = []
        for bid in ids[:3]:
            d = json.loads(_T(t.projects, bid).run("get_building", {}))
            rows.append(d)
        head = "| Gösterge | " + " | ".join(r["ad"] for r in rows) + " |\n|---|" + "---|" * len(rows)
        def line(label, fn):
            return f"| {label} | " + " | ".join(fn(r) for r in rows) + " |"
        body = "\n".join([
            line("Sağlık skoru", lambda r: f"{r['saglik_skoru']['toplam']:.0f} ({r['saglik_skoru']['not']})"),
            line("Enerji sınıfı", lambda r: r["enerji_sinifi"]["sinif"]),
            line("EUI (kWh/m²)", lambda r: _n(r["kpi"]["eui_kwh_m2"])),
            line("Karbon (tCO₂)", lambda r: _n(r["kpi"]["karbon_kg"] / 1000, 1)),
            line("Maliyet", lambda r: _m(r["kpi"]["toplam_maliyet_TL"])),
            line("Alan (m²)", lambda r: _n(r["alan_m2"]))])
        best = max(rows, key=lambda r: r["saglik_skoru"]["toplam"])
        return f"{head}\n{body}\n\nSağlık skoru en yüksek olan **{best['ad']}**."

    def _compare_utilities(self, t) -> str:
        p = t.projects[t.current]
        k, a = p.kpis(), p.assumptions
        from ..models import UtilityType
        ce = k.electricity_kwh * a.emission_factor_kg_per_kwh[UtilityType.ELECTRICITY]
        cg = k.gas_kwh * a.emission_factor_kg_per_kwh[UtilityType.GAS]
        tot, ctot = k.electricity_kwh + k.gas_kwh, ce + cg
        more = "elektrik" if k.electricity_kwh > k.gas_kwh else "doğalgaz"
        return (f"Enerji olarak **{more}** daha çok: elektrik {_n(k.electricity_kwh / 1000)} MWh (%{100 * k.electricity_kwh / tot:.0f}), "
                f"doğalgaz {_n(k.gas_kwh / 1000)} MWh (%{100 * k.gas_kwh / tot:.0f}).\n\n"
                f"Karbonda elektriğin payı %{100 * ce / ctot:.0f}, doğalgazınki %{100 * cg / ctot:.0f} "
                f"(emisyon faktörleri 0,469 ve 0,202 kgCO₂e/kWh).")

    def _month_yoy(self, t, m: int) -> str:
        from ..models import UtilityType
        p = t.projects[t.current]
        prev = p.previous_year()
        if prev is None:
            return "Karşılaştırma için önceki yıla ait veri yok."
        def val(y, u):
            return p.monthly(y, u)[m]
        rows = []
        for u, label in ((UtilityType.ELECTRICITY, "Elektrik"), (UtilityType.GAS, "Doğalgaz")):
            a_, b_ = val(p.year, u), val(prev, u)
            ch = (a_ / b_ - 1) * 100 if b_ else 0
            rows.append(f"- {label}: {_n(a_ / 1000, 1)} MWh ({prev}: {_n(b_ / 1000, 1)} MWh, %{abs(ch):.1f} {'arttı' if ch > 0 else 'azaldı'})")
        self._chart = self._monthly_chart(p)
        return f"**{MONTH_NAMES[m]}** ayı, {p.year} ve {prev} karşılaştırması:\n\n" + "\n".join(rows)

    # ---- eylemler (arayüz uygular)
    def a_act_status(self, q, t, b, c):
        status = find_status(q)
        if not c:
            return "Hangi projenin durumunu değiştireyim? Örneğin “VFD'yi planlandı yap” ya da “LED projesi tamamlandı”."
        if not status:
            return "Hangi duruma alayım: Planlandı, Uygulanıyor, Tamamlandı ya da Planlanmadı?"
        year = next((int(y) for y in re.findall(r"20\d\d", q)), None)
        p = t.projects[t.current]
        names = {o.code: o.name for o in p.opportunities}
        self._actions = [("status", code, status, year) for code in c]
        return "Tamam: " + ", ".join(f"**{names[code]}** → **{status}**" for code in c) + (f" ({year})" if year else "") + ". Proje takibine kaydettim."

    def a_act_open(self, q, t, b, c):
        n = norm(q)
        for words, target in NAV_TARGETS:
            if any(w in n for w in words):
                self._actions = [("open",) + target]
                return f"**{target[0]}**{' > ' + target[1] if target[1] else ''} sayfasını açıyorum."
        return "Hangi sayfayı açayım? Örnek: “portföyü aç”, “finans sayfasına git”, “ayarları aç”."

    def a_act_scenario(self, q, t, b, c):
        if not c:
            return "Hangi önerileri seçeyim? Örnek: “LED ve VFD'yi senaryoda seç”."
        self._actions = [("scenario", list(c))]
        return f"**Mevcut vs Hedef** ekranında {', '.join(c)} seçildi; sonuçları orada görebilirsin."

    def a_act_report(self, q, t, b, c):
        self._actions = [("report",)]
        return "Rapor kaydetme penceresini açıyorum (Mevcut vs Hedef'te seçili önerilere göre hazırlanır)."



def stream_chunks(text: str, size: int = 5):
    """Cevabı yazılıyormuş gibi küçük parçalara böler (arayüzde canlı yazım etkisi)."""
    for i in range(0, len(text), size):
        yield text[i:i + size]
