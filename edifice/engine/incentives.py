"""Teşvik / hibe / kredi bulucu: seçili önerilere uygun programları listeler ve kullanıcının girdiği orana göre CAPEX etkisini hesaplar.

DÜRÜSTLÜK KURALI: Program koşulları, oranları ve açık/kapalı durumu sık değişir ve burada doğrulanmış resmî metin yoktur.
Katalog yalnız "böyle bir program türü var, buradan bakın" der (`level="doğrulanmadı"`); sayısal oran ancak kullanıcı programı
kontrol edip girerse hesaba girer. Hiçbir oran varsayılan olarak CAPEX'ten düşülmez."""
from __future__ import annotations

from dataclasses import dataclass, field

ALL_MEASURES = ("LED", "CHILLER", "VFD", "ENVELOPE", "BOILER", "GES")


@dataclass(frozen=True)
class Program:
    code: str
    name: str
    provider: str
    kind: str                       # hibe | kredi | vergi/tarife | teknik destek
    measures: tuple = ALL_MEASURES
    use_types: tuple = ()           # boş = tüm bina tipleri
    audience: str = ""
    rate_hint: str = ""             # kaynakta görülen ifade, hesaba GİRMEZ
    status: str = "bilinmiyor"      # açık | kapalı | bilinmiyor
    url: str = ""
    level: str = "doğrulanmadı"
    note: str = ""


CATALOG: tuple[Program, ...] = (
    Program("VAP", "Verimlilik Artırıcı Projeler (VAP) desteği", "T.C. Enerji ve Tabii Kaynaklar Bakanlığı", "hibe",
            measures=("LED", "CHILLER", "VFD", "ENVELOPE", "BOILER"), use_types=("Sanayi",),
            audience="Sanayi işletmeleri ve OSB'ler (çağrıya bağlı)", rate_hint="haberlerde «%30'a kadar» hibe geçiyor",
            url="https://www.yatirimadestek.gov.tr/assets/upload/dosyalar/ozet_enerji_verimliligi_destekleri.pdf",
            note="Sanayi odaklıdır; ofis/ticari/konut binası için kapsam dışı olabilir. Çağrı dönemleri ve oran her yıl değişir, güncel çağrı metnini okuyun."),
    Program("LISANSSIZ_GES", "Lisanssız elektrik üretimi (çatı GES) mevzuatı", "EPDK / T.C. Enerji ve Tabii Kaynaklar Bakanlığı", "vergi/tarife",
            measures=("GES",), audience="Tüketim tesisine bağlı üretim (kendi tüketimi için)",
            rate_hint="kurulu güç sınırı ve mahsuplaşma kuralları değişken; saatlik dengeleme haberi var",
            url="https://www.cnbce.com/enerji/lisanssiz-elektrikte-yeni-duzenleme-uretim-ve-tuketim-artik-her-saat-dengelenecek-h27723",
            note="Doğrudan hibe değil, işletme çerçevesidir. UYARI: mahsuplaşma saatlik olursa uygulamanın GES modeli (aylık denge) iyimser kalır; "
                 "güncel EPDK kararını kontrol edin."),
    Program("KALKINMA_AJANS", "Kalkınma ajansları mali destek programları", "Bölge kalkınma ajansları", "hibe",
            audience="Program çağrısına göre (genelde kâr amacı gütmeyen kuruluşlar, KOBİ, belediyeler)",
            url="https://kalkinma.com.tr/en/about-us/our-resources", note="Yalnız açık çağrı varsa; bölgeye göre ajansın sitesine bakın."),
    Program("KOSGEB", "KOSGEB enerji verimliliği destekleri", "KOSGEB", "hibe",
            audience="KOBİ", url="https://www.alomaliye.com/2016/04/29/kosgeb-enerji-verimliligi-yatirim-firsatlarini-kobilere-aciyor/amp/",
            note="Kaynak eski bir haberdir; programın bugün açık olup olmadığı doğrulanmadı."),
    Program("YESIL_KREDI", "Yeşil dönüşüm / enerji verimliliği kredi hatları (TSKB, TKYB, EIB kaynaklı)", "Aracı bankalar", "kredi",
            audience="Şirketler (banka değerlendirmesi)", rate_hint="vade ve faiz bankaya göre",
            url="https://www.eib.org/fr/press/all/2026-202-eib-resumes-financing-in-turkiye-with-eur200-million-to-support-the-decarbonisation-of-turkish-companies?lang=tr",
            note="Kredi CAPEX'i düşürmez, finansman maliyetini değiştirir; uygulama kredi modeli içermez."),
    Program("YESIL_BINA_KONUT", "Yeşil bina kredi avantajı (konut)", "Bankalar", "kredi", use_types=("Konut",),
            audience="Konut alıcıları / projeler", url="https://www.donanimhaber.com/yesil-binalara-kredi-avantaji-enerji-tasarruflu-konutlara-destek--202062",
            note="Haber başlığından; koşullar doğrulanmadı."),
)
BY_CODE = {p.code: p for p in CATALOG}


@dataclass
class Match:
    program: Program
    measures: list[str]
    in_scope: bool
    why: str


@dataclass
class Terms:
    grant_pct: float = 0.0          # kullanıcı girdisi, 0-1
    cap: float | None = None        # ₺ tavan, boş = sınırsız
    verified: bool = False          # kullanıcı güncel koşulu kontrol etti


@dataclass
class GrantResult:
    capex_before: float
    grant_total: float
    capex_after: float
    per_program: dict = field(default_factory=dict)
    note: str = ""


def find_matches(codes: list[str], use_type: str, catalog=CATALOG) -> list[Match]:
    """Seçili öneri kodlarına (ve GES varsa 'GES') uyan programlar; bina tipi kapsam dışıysa işaretlenir."""
    out = []
    for p in catalog:
        ms = [c for c in codes if c in p.measures]
        if not ms:
            continue
        ok = not p.use_types or use_type in p.use_types
        why = "" if ok else f"Program {', '.join(p.use_types).lower()} için; bu bina «{use_type}» tipinde, kapsam dışı olabilir."
        out.append(Match(p, ms, ok, why))
    return out


def apply_grants(capex_by_code: dict, matches: list[Match], terms: dict) -> GrantResult:
    """Kullanıcı oranı girdiği hibe programlarını uygular. Aynı kalem iki kez desteklenmez: yüksek oranlı program önce, sonrakiler kalan tutara işler.
    Yalnız kind=='hibe' ve kapsam içi programlar; krediler ve çerçeve düzenlemeler CAPEX'i düşürmez."""
    remaining = dict(capex_by_code)
    total0 = sum(remaining.values())
    res = GrantResult(total0, 0.0, total0)
    active = [m for m in matches if m.program.kind == "hibe" and m.in_scope and terms.get(m.program.code, Terms()).grant_pct > 0]
    for m in sorted(active, key=lambda m: -terms[m.program.code].grant_pct):
        t = terms[m.program.code]
        base = sum(remaining.get(c, 0.0) for c in m.measures)
        g = base * min(max(t.grant_pct, 0.0), 1.0)
        if t.cap is not None:
            g = min(g, max(t.cap, 0.0))
        if g <= 0:
            continue
        for c in m.measures:                 # hibeyi kalemlere orantılı dağıt
            if base:
                remaining[c] -= remaining[c] / base * g
        res.per_program[m.program.code] = g
        res.grant_total += g
    res.capex_after = total0 - res.grant_total
    unverified = [c for c in res.per_program if not terms[c].verified]
    if res.per_program:
        res.note = "Oranlar kullanıcı girdisidir" + (f"; doğrulanmadı işaretli: {', '.join(unverified)}" if unverified else "") + "."
    return res
