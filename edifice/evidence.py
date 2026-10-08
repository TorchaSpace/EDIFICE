"""Kanıt kayıt defteri: uygulamadaki her varsayımın dayandığı kaynaklar ve doğrulama düzeyleri.

Doğrulama düzeyleri (dürüstlük için üçe ayrıldı):
  "birincil"  - kaynağın kendisi (tablo/rapor/özet sayfası) okundu, rakamlar oradan alındı
  "özet"      - makalenin özeti/yayıncı sayfası okundu; tam metin okunmadı
  "ikincil"   - rakam başka bir kaynağın aktarımından alındı; asıl kaynakla doğrulanmalı
  "varsayım"  - doğrulanabilir kaynak bulunamadı; Ayarlar'dan gerçek değerle değiştirilmeli
"""
from __future__ import annotations

import re

KBTU_FT2_TO_KWH_M2 = 3.15459   # 1 kBtu/ft² = 3,15459 kWh/m²

LEVELS = {"birincil": "Kaynak okundu", "özet": "Özet okundu", "ikincil": "İkincil aktarım", "varsayım": "Varsayım"}

SOURCES: dict[str, dict] = {
    "ES2024": dict(
        cite="U.S. EPA ENERGY STAR Portfolio Manager. U.S. Energy Use Intensity by Property Type, Technical Reference, Ağustos 2024.",
        url="https://portfoliomanager.energystar.gov/pdf/reference/US%20National%20Median%20Table.pdf", level="birincil",
        note="Ulusal medyan site EUI (CBECS tabanlı). Ofis 52,9; Konut (çok aileli) 59,6; Otel 63,0; Hastane 234,3; Okul (K-12) 48,5; "
             "Perakende 51,4; Karma kullanım 40,1 kBtu/ft². Sanayi için veri yok."),
    "ES_SCORE": dict(
        cite="U.S. EPA ENERGY STAR. How the 1-100 ENERGY STAR score is calculated.",
        url="https://www.energystar.gov/buildings/benchmark/understand-metrics/how-score-calculated", level="birincil",
        note="Benzer binalarla kıyas; işletme saatleri ve yoğunluk gibi etkenler regresyonla düzeltilir; 50 puan medyan performanstır."),
    "SAHIN2022": dict(
        cite="Sahin H., Esen H. (2022). The usage of renewable energy sources and its effects on GHG emission intensity of electricity "
             "generation in Turkey. Renewable Energy 192: 859-869. doi:10.1016/j.renene.2022.03.141",
        url="https://ideas.repec.org/a/eee/renene/v192y2022icp859-869.html", level="özet",
        note="Türkiye elektrik üretimi emisyon yoğunluğu 2008'de 563, 2020'de 437 gCO2e/kWh (üretim bazlı; iletim-dağıtım kayıpları hariç)."),
    "EMBER2024": dict(
        cite="Ember (2024). Türkiye Electricity Review 2024.",
        url="https://ember-energy.org/latest-insights/turkiye-electricity-review-2024", level="özet",
        note="2023'te kömür üretimi rekor 118 TWh; toplam üretimin yaklaşık %36'sı (322 TWh). Kömür payı yüksek kaldığı için şebeke emisyon yoğunluğu yüksektir."),
    "IPCC2006": dict(
        cite="IPCC (2006). 2006 IPCC Guidelines for National Greenhouse Gas Inventories, Vol. 2 Energy, Ch. 2 Stationary Combustion.",
        url="https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/2_Volume2/V2_2_Ch2_Stationary_Combustion.pdf", level="ikincil",
        note="Doğalgaz varsayılan CO2 faktörü 56.100 kg/TJ (%95 aralığı 54.300-58.300), net kalorifik değer bazlı. "
             "56,1 kg/GJ x 0,0036 GJ/kWh = 0,202 kgCO2/kWh. Üst ısıl değere (GCV) göre faturalanan kWh için yaklaşık %10 düşük (0,182)."),
    "MILLS2011": dict(
        cite="Mills E. (2011). Building commissioning: a golden opportunity for reducing energy costs and greenhouse-gas emissions in the "
             "United States. Energy Efficiency 4: 145-173. doi:10.1007/s12053-011-9116-8",
        url="https://doi.org/10.1007/s12053-011-9116-8", level="özet",
        note="643 ticari bina meta-analizi: mevcut binalarda medyan tüm-bina enerji tasarrufu %16, medyan geri ödeme 1,1 yıl (üst çeyrek 0,4; alt çeyrek 2,4 yıl)."),
    "PNNL24526": dict(
        cite="Davis R., Murphy A., Perrin T. (2015). Evaluation of an LED Retrofit Project at Princeton University's Carl Icahn Laboratory. "
             "PNNL-24526, Pacific Northwest National Laboratory.",
        url="https://www.pnnl.gov/main/publications/external/technical_reports/PNNL-24526.pdf", level="birincil",
        note="Aydınlatma enerjisinde LED tasarrufu armatür tipine göre: 2x2 troffer %24, 4' lineer T8 %42, CFL downlight %61; toplam %37. "
             "Doluluk sensörü/dimleme eklenince tahmini %62. (Tahmindir, ölçüm değil.)"),
    "ASHRAE_VFD": dict(
        cite="ASHRAE Annual Conference 2016, Session 19668 (değişken hızlı sürücü saha performansı oturumu).",
        url="https://ashraem.confex.com/ashraem/s16/webprogram/Session19668.html", level="ikincil",
        note="Gerçekleşen/ideal tasarruf oranı sıklıkla %40 kadar düşük; ideal hesaba dayanan teşvik programları tasarrufu ~%30 abartabilir."),
    "SCHIBUOLA2018": dict(
        cite="Schibuola L. ve ark. (2018). Değişken debili pompa ve fan sistemlerinin uzun süreli izlenen bir kamu binasında performansı.",
        url="https://air.iuav.it/handle/11578/277199", level="ikincil",
        note="Sabit hızlı sisteme göre pompa+fan enerjisinde yıllık %38,9 tasarruf (tek bina; tam metin okunamadı, başlık/dergi doğrulanmalı)."),
    "MNCEE_BOILER": dict(
        cite="Minnesota Center for Energy and Environment (MnCEE). Yoğuşmalı kazanların saha performansı izleme çalışması (12 bina).",
        url="https://www.mncee.org/sites/default/files/report-files/386675.pdf", level="ikincil",
        note="Yoğuşmalı kazanlar beklenen tasarrufun yarısından biraz fazlasını sağladı; ortalama gerçekleşen verim %88,6 (nominalin ~5 puan altı)."),
    "ORNL_ENVELOPE": dict(
        cite="ORNL saha testi (Pacific Northwest ağırlaştırma programı) ve LBL tek aile bina yalıtım çalışmaları.",
        url="https://info.ornl.gov/sites/publications/Files/Pub57672.pdf", level="ikincil",
        note="Duvar yalıtımında ölçülen tasarruf tahminin yaklaşık yarısı; LBL: tavan+duvar yalıtımı normalize yıllık tüketimde %12-21 (10 proje, konut). Ofis verisi değil."),
    "CHILLER_CASES": dict(
        cite="Üretici/yüklenici vaka çalışmaları (Danfoss/Univ. Cincinnati, Daikin/Tampa ofis, Trane/Kowloon hastane, CLEAResult kampüs).",
        url="https://www.danfoss.com/en-us/service-and-support/case-stories/cf/advanced-technology-chiller-compressors-propel-significant-energy-and-operational-savings-at-university-of-cincinnati",
        level="ikincil", note="Soğutucu değişiminde rapor edilen enerji tasarrufu ~%20-35 (tesis düzeyi + kontrol ile %41). Satıcı kaynaklı; en iyi durum olarak okunmalı."),
    "EIA_OFFICE": dict(
        cite="U.S. EIA. Commercial Buildings Energy Consumption Survey (CBECS), office buildings profile.",
        url="https://www.eia.gov/consumption/commercial/pba/office.php", level="ikincil",
        note="Ofislerde son kullanım payları (tüm yakıtlar): ısıtma %30, havalandırma %20, aydınlatma %12; diğer son kullanımların her biri ≤%8."),
    "VANDRONKELAAR2016": dict(
        cite="van Dronkelaar C., Dowson M., Burman E., Spataru C., Mumovic D. (2016). A Review of the Energy Performance Gap and Its "
             "Underlying Causes in Non-Domestic Buildings. Frontiers in Mechanical Engineering 1:17. doi:10.3389/fmech.2015.00017",
        url="https://www.frontiersin.org/articles/10.3389/fmech.2015.00017/pdf", level="birincil",
        note="62 bina: ölçülen ile tahmin edilen enerji kullanımı ortalama +%34 saptı (SS %55). Baskın nedenler: modelleme belirsizliği (%20-60), "
             "kullanıcı davranışı (%10-80), kötü işletme (%15-80)."),
    "DEWILDE2014": dict(
        cite="de Wilde P. (2014). The gap between predicted and measured energy performance of buildings: A framework for investigation. "
             "Automation in Construction 41: 40-49. doi:10.1016/j.autcon.2014.02.009",
        url="https://doi.org/10.1016/j.autcon.2014.02.009", level="özet",
        note="Tahmin-ölçüm farkı (performance gap) için kavramsal çerçeve."),
    "PERSISTENCE": dict(
        cite="Retro-commissioning tasarruf kalıcılığı: ASHRAE Journal (Aralık 2019) saha izleme çalışması; LBNL/SMUD değerlendirmesi (2004).",
        url="https://www.ashrae.org/technical-resources/ashrae-journal/featured-articles/persistence-in-energy-savings-from-retro-commissioning-measures",
        level="ikincil", note="167 önlemde ortalama ~%61 kalıcılık; SMUD: tüm-bina tasarrufu 2. yılda %10,5'ten 4. yılda %8'e düştü. "
                              "İşletme önlemleri (ayar/kontrol) donanım değişikliğinden daha çabuk erir."),
    "ASHRAE_LIFE": dict(
        cite="ASHRAE Handbook - HVAC Applications, 'Owning and Operating Costs' bölümü; ASHRAE ekipman ömrü çizelgeleri.",
        url="https://www.ashrae.org", level="ikincil",
        note="Aktarımlarda aralıklar farklı: soğutucu 15-25(30), kazan 20-30(15-30), klima santrali 15-20 (özel yapım 30), pompa 10-20 (kaideli 25), "
             "soğutma kulesi 15-25 yıl. Asıl çizelgeyle doğrulanmalı."),
    "ASHRAE_G14": dict(
        cite="ASHRAE Guideline 14: Measurement of Energy, Demand, and Water Savings.",
        url="https://www.ashrae.org", level="ikincil",
        note="Aylık veride kalibrasyon ölçütleri: CV(RMSE) ≤ %15, NMBE ≤ ±%5 (saatlik: %30 / ±%10). Gelecekte veri kalitesi kontrolünde kullanılabilir."),
    "EU244": dict(
        cite="Commission Delegated Regulation (EU) No 244/2012 (maliyet-optimal enerji performansı gereksinimleri için karşılaştırmalı metodoloji).",
        url="https://eur-lex.europa.eu/eli/reg_del/2012/244/2013-04-06/eng", level="özet",
        note="İskonto oranı reel terimlerle ifade edilir; oran duyarlılık analiziyle belirlenir; küresel maliyet = yatırım+işletme+yenileme maliyetlerinin bugünkü değeri. "
             "Sayısal oranlar doğrulanamadı."),
    "JRC2008": dict(
        cite="Nardo M., Saisana M., Saltelli A., Tarantola S., Hoffmann A., Giovannini E. (2008). Handbook on Constructing Composite Indicators: "
             "Methodology and User Guide. OECD/JRC, ISBN 978-92-64-04345-9.",
        url="https://knowledge4policy.ec.europa.eu/sites/default/files/jrc47008_handbook_final.pdf", level="özet",
        note="Bileşik gösterge kurma adımları: normalizasyon, ağırlıklandırma, birleştirme, güçlülük ve duyarlılık analizi. Health Score bu çerçeveyle kurgulandı."),
    "BEPTR": dict(
        cite="Binalarda Enerji Performansı Yönetmeliği ve BEP-TR (Çevre, Şehircilik ve İklim Değişikliği Bakanlığı).",
        url="https://eyb.metu.edu.tr/sites/eyb.metu.edu.tr/files/binalarda_enerji_performansi_yonetmeligi.pdf", level="ikincil",
        note="Türkiye'de enerji sınıfı A-G, binanın yıllık birim alan enerji tüketimi ve CO2 salımının referans binayla kıyaslanmasına dayanır; "
             "NSEB için B veya daha iyi sınıf ve %10 yenilenebilir pay istenir. Sınıf sınırlarının sayısal tablosu doğrulanamadı."),
    "EPBD2024": dict(
        cite="Directive (EU) 2024/1275 (EPBD yeniden düzenleme, 2024).",
        url="https://eur-lex.europa.eu/eli/dir/2024/1275/oj", level="ikincil",
        note="Konut dışı binalarda en kötü performanslı %16'nın 2030'a, %26'sının 2033'e kadar iyileştirilmesi hedefi; üye devletler asgari performans standartlarını belirler."),
}

# --------------------------------------------------------------------------- parametre kaydı
# Her satır: (grup, parametre adı, değer metni, kaynaklar, düzey, not)
def parameter_rows(a) -> list[tuple]:
    from .models import UtilityType
    ef_e, ef_g = a.emission_factor_kg_per_kwh[UtilityType.ELECTRICITY], a.emission_factor_kg_per_kwh[UtilityType.GAS]
    rows = [
        ("Karbon", "Elektrik emisyon faktörü", f"{ef_e:.3f} kgCO₂/kWh", ["SAHIN2022", "EMBER2024"], "özet",
         "2020 üretim bazlı değer; iletim-dağıtım kayıpları ve yıllık değişim hariç. Güncel resmi faktörle değiştirin."),
        ("Karbon", "Doğalgaz emisyon faktörü", f"{ef_g:.3f} kgCO₂/kWh", ["IPCC2006"], "ikincil",
         "Net kalorifik değer bazı. Fatura kWh'si üst ısıl değere göreyse yaklaşık 0,182 kullanın."),
        ("Kıyas", "Kullanım tipine göre EUI kıyas değerleri", "Ayarlar'daki tablo", ["ES2024", "ES_SCORE"], "birincil",
         "ABD ulusal medyanı (CBECS). Türkiye iklimi/uygulaması farklıdır; BEP-TR referans değerleri girilirse değiştirin."),
        ("Kıyas", "Karbon yoğunluğu kıyas değeri", "kıyas EUI x ağırlıklı emisyon faktörü", [], "varsayım",
         "Elektrik/gaz payı %50 varsayımıyla türetilir; doğrudan kaynak yok."),
        ("Kıyas", "Su yoğunluğu kıyas değeri", f"{a.benchmark_water_m3_m2:.2f} m³/m²·yıl", [], "varsayım", "Kaynak bulunamadı."),
        ("Sınıf", "Enerji sınıfı (A-G) sınırları", "EUI/kıyas oranı: 0,5-0,75-1,0-1,3-1,65-2,0", ["BEPTR"], "varsayım",
         "Resmi BEP-TR sınır tablosu doğrulanamadığı için göstergedir; resmi Enerji Kimlik Belgesi yerine geçmez."),
        ("Sınıf", "Benzer binalara göre yüzdelik", "log-normal model, σ=0,35", ["ES_SCORE"], "varsayım",
         "Medyan = kıyas değeri; dağılım şekli varsayımdır, ENERGY STAR regresyon kullanır."),
        ("Skor", "Health Score yöntemi", "4 bileşen, ağırlıklı ortalama", ["JRC2008"], "özet",
         "Normalizasyon eşikleri ve ağırlıklar uzman kararıdır; skor ağırlık duyarlılığı aralığıyla birlikte gösterilir."),
        ("Skor", "Ekipman ömrü", "Tür başına 15-30 yıl", ["ASHRAE_LIFE"], "ikincil", "Soğutucu, kazan, santral ve pompa için ayrı ömür kullanılır."),
        ("Finans", "İskonto oranı", f"%{a.discount_rate * 100:.1f} (reel)", ["EU244"], "varsayım",
         "AB metodolojisi reel oran ve duyarlılık analizi ister; sayısal oran kaynaktan doğrulanamadı, duyarlılık tablosunda ±2 puan gösterilir."),
        ("Finans", "Enerji fiyat artışı", f"%{a.energy_escalation * 100:.1f} (reel)", [], "varsayım", "Kaynak yok; duyarlılık tablosunda %0 senaryosu var."),
        ("Finans", "Analiz süresi", f"{a.horizon_years} yıl", ["EU244"], "varsayım", "Önlemlerin ömrüne göre seçilmelidir."),
        ("Finans", "Tasarruf kaybı", f"%{a.savings_degradation * 100:.1f}/yıl", ["PERSISTENCE"], "ikincil",
         "Donanım değişikliği için doğrudan veri yok; işletme önlemleri çok daha hızlı erir (SMUD: %10,5 → %8, 2 yılda)."),
        ("Finans", "Yatırım maliyetleri (₺/m²)", "Öneri kataloğunda", [], "varsayım", "Piyasa fiyatı/keşif bedeliyle değiştirin."),
    ]
    return [(g, n, re.sub(r"(?<=\d)\.(?=\d)", ",", v), s, l, note) for g, n, v, s, l, note in rows]


def render_markdown(a) -> str:
    """docs/KAYNAKCA.md içeriği: parametre kaydı + kaynakça (uygulamadaki Kaynaklar ve Yöntem ekranıyla aynı veri)."""
    from .mock_data import opportunities
    out = ["# EDIFI'CE: Kaynaklar ve Yöntem", "",
           "Bu dosya `edifice/evidence.py` kaydından üretilir (`python tools/make_docs.py`). Doğrulama düzeyleri:", ""]
    for k, v in LEVELS.items():
        out.append(f"- **{v}**: " + {"birincil": "kaynağın kendisi okundu, rakamlar oradan alındı.",
                                      "özet": "özet/yayıncı sayfası okundu, tam metin okunmadı.",
                                      "ikincil": "rakam başka bir kaynağın aktarımından alındı, asıl kaynakla doğrulanmalı.",
                                      "varsayım": "doğrulanabilir kaynak bulunamadı."}[k])
    out += ["", "## Hesap parametreleri", "", "| Grup | Parametre | Değer | Düzey | Kaynak | Not |", "|---|---|---|---|---|---|"]
    for g, n, v, s, lvl, note in parameter_rows(a):
        out.append(f"| {g} | {n} | {v} | {LEVELS[lvl]} | {', '.join(s) or '-'} | {note} |")
    out += ["", "## Dönüşüm önerileri: tasarruf aralıkları", "", "| Öneri | Düşük | Tipik | Yüksek | Düzey | Kaynak | Türetme |", "|---|---|---|---|---|---|---|"]
    for o in opportunities():
        out.append(f"| {o.name} | %{o.saving_for('low') * 100:.1f} | %{o.saving_pct * 100:.1f} | %{o.saving_for('high') * 100:.1f} | "
                   f"{LEVELS[o.evidence_level]} | {', '.join(o.evidence)} | {o.basis} |")
    out += ["", "## Kaynakça", ""]
    for key, s in SOURCES.items():
        out += [f"### {key} ({LEVELS[s['level']]})", "", s["cite"], "", s["note"], "", s["url"], ""]
    out += ["## Sınırlamalar", "",
            "- Kıyas değerleri ABD ulusal medyanıdır; Türkiye'ye özgü BEP-TR değerleriyle değiştirilmelidir.",
            "- Enerji sınıfı göstergedir, resmi Enerji Kimlik Belgesi değildir; sınır tablosu resmi kaynaktan doğrulanamadı.",
            "- Tasarruf aralıkları literatürden türetildi; bina özelinde etüt/ölçümün yerini tutmaz (tahmin-ölçüm farkı ortalama +%34, SS %55).",
            "- Yatırım maliyetleri doğrulanmış kaynağa dayanmaz.",
            "- Hava normalizasyonu ve M&V (IPMVP / ASHRAE Guideline 14) bu sürümde yok.", ""]
    return "\n".join(out)
