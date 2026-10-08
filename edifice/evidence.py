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
    "ETKB_EF2023": dict(
        cite="T.C. Enerji ve Tabii Kaynaklar Bakanlığı, EVÇED. Türkiye Elektrik Üretimi ve Elektrik Tüketim Noktası Emisyon Faktörleri Bilgi Formu "
             "(ETKB-EVÇED-FRM-042 Rev.01), hesaplama dönemi 2023, yayım 26.12.2025.",
        url="https://enerji.gov.tr/Media/Dizin/EVCED/tr/%C3%87evreVe%C4%B0klim/%C4%B0klimDe%C4%9Fi%C5%9Fikli%C4%9Fi/EmisyonFaktorleri/2023_Turkiye_Elektrik_UretimiveElektrik_Tuketim_Noktasi_Emisyon_Faktorleri.pdf",
        level="birincil",
        note="Resmî faktörler (tCO2e/MWh): Türkiye geneli elektrik üretimi 0,434; iletim hattından bağlı tüketim noktası 0,436; "
             "dağıtım hattından bağlı tüketim noktası 0,469 (CO2 olarak 0,430 / 0,433 / 0,465). Binalar çoğunlukla dağıtımdan bağlı olduğu için 0,469 kullanılır."),
    "BEPYON": dict(
        cite="Binalarda Enerji Performansı Yönetmeliği (RG 5.12.2008/27075; son değişiklik RG 16.5.2026/33255), mevzuat.gov.tr.",
        url="https://www.mevzuat.gov.tr/MevzuatMetin/yonetmelik/7.5.13594.pdf", level="birincil",
        note="Md. 26: EKB'de birincil enerji tüketiminin A-G referans ölçeğine göre sınıfı ve CO2 salımı sınıfı gösterilir. Md. 27(5): BEP-TR ile belge alacak yeni binalar D "
             "veya daha kötü sınıfta olamaz. NSEB: sınıf B veya daha iyi ve birincil enerjinin en az %10'u yerinde yenilenebilir. Md. 27/A (2026): düşük karbonlu bina belgesi için "
             "sera gazı sınıfı en az B ve enerji performans sınıfı en az C. Sınıf eşikleri yönetmelikte değil, ÇŞİDB sınıflandırma tablosundadır."),
    "CSB_EKB": dict(
        cite="T.C. Çevre, Şehircilik ve İklim Değişikliği Bakanlığı. Binalarda Enerji Kimlik Belgesi (EKB) Nedir? (BEP-TR bilgilendirme belgesi).",
        url="https://webdosya.csb.gov.tr/db/samsun/webmenu/webmenu4379.pdf", level="birincil",
        note="Referans binanın birincil enerji değeri Ep=100 (D sınıfının üst sınırı). Sınıflar: A 0-39, B 40-79, C 80-99, D 100-119, E 120-139, F 140-174, G 175 ve üzeri. "
             "EKB 10 yıl geçerlidir. Mücavir alan dışında 1.000 m²'den küçük binalar kapsam dışıdır."),
    "ETKB_KIYASLAMA": dict(
        cite="T.C. Enerji ve Tabii Kaynaklar Bakanlığı, EVÇED. Binalarda Kıyaslama Raporu Hazırlama Rehberi (Enerji Verimliliğinde Kurumsal Kapasitenin "
             "Geliştirilmesi İçin Teknik Destek Projesi, AB finansmanlı).",
        url="https://enerji.gov.tr/Media/Dizin/EVCED/tr/EnerjiVerimlili%C4%9Fi/OVDegerlendirme/Belgeler/K%C4%B1yaslamaC/BKRHRehberi.pdf", level="birincil",
        note="EKB değerleri teorik (standart iklim ve kapsam) olduğundan gerçek tüketimi yansıtmaz; bu yüzden fatura/sayaç verisine dayalı ölçülmüş (operasyonel) kıyaslama önerilir. "
             "Resmî göstergeler: spesifik nihai enerji (SNET, kWh/m²·yıl), spesifik birincil enerji (SBET), sera gazı (kg CO2e/m²·yıl), kişi başı enerji, su (m³/m²·yıl). "
             "16 bina tipinden biri ofislerdir. Enerji akışları alt ısıl değere göre kWh'ye çevrilir. Sayısal kıyas değerleri belgede yer almaz."),
    "YAPI2026": dict(
        cite="Mimarlık ve Mühendislik Hizmet Bedellerinin Hesabında Kullanılacak 2026 Yılı Yapı Yaklaşık Birim Maliyetleri Hakkında Tebliğ, "
             "ÇŞİDB, Resmî Gazete 3.2.2026 / 33157.",
        url="https://www.hukukihaber.net/mimarlik-ve-muhendislik-hizmet-bedellerinin-hesabinda-kullanilacak-2026-yili-yapi-yaklasik-birim-maliyetleri-hakkinda-teblig",
        level="birincil",
        note="KDV hariç, genel gider ve kâr dahil yaklaşık birim maliyet (TL/m²). İş merkezleri/ticari yapılar: ≤3 kat 21.050; 21,5 m altı 23.400; 21,5-30,5 m 26.450; "
             "30,5-51,5 m 33.900; 51,5 m üzeri 40.500-42.350. Metin resmî gazete içeriğinin bir aynasından okundu. Yeniden inşa maliyeti bağlamı içindir, yenileme maliyeti değildir."),
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
        cite="Commission Delegated Regulation (EU) No 244/2012, Annex I (maliyet-optimal enerji performansı için karşılaştırmalı metodoloji).",
        url="https://www.legislation.gov.uk/eur/2012/244/annex/I/data.htm", level="birincil",
        note="Hesap süresi: konut ve kamu binaları 30 yıl, ticari konut dışı binalar 20 yıl. İskonto oranı reel terimlerle ifade edilir; en az iki oranla duyarlılık analizi yapılır "
             "(makroekonomik hesapta oranlardan biri reel %3). Duyarlılık analizi en azından enerji fiyat gelişimini ve iskonto oranını kapsamalıdır. Finansal iskonto oranının değeri "
             "üye devletlerce belirlenir (sayısal değer verilmez)."),
    "JRC2008": dict(
        cite="Nardo M., Saisana M., Saltelli A., Tarantola S., Hoffmann A., Giovannini E. (2008). Handbook on Constructing Composite Indicators: "
             "Methodology and User Guide. OECD/JRC, ISBN 978-92-64-04345-9.",
        url="https://knowledge4policy.ec.europa.eu/sites/default/files/jrc47008_handbook_final.pdf", level="özet",
        note="Bileşik gösterge kurma adımları: normalizasyon, ağırlıklandırma, birleştirme, güçlülük ve duyarlılık analizi. Health Score bu çerçeveyle kurgulandı."),
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
        ("Karbon", "Elektrik emisyon faktörü", f"{ef_e:.3f} kgCO₂e/kWh", ["ETKB_EF2023", "SAHIN2022"], "birincil",
         "ETKB resmî 2023 değeri, dağıtım hattından bağlı tüketim noktası (iletimden bağlıysa 0,436). Şahin & Esen (2022) 2020 üretim bazlı 0,437 ile tutarlı."),
        ("Karbon", "Doğalgaz emisyon faktörü", f"{ef_g:.3f} kgCO₂/kWh", ["IPCC2006"], "ikincil",
         "Net kalorifik değer bazı. Fatura kWh'si üst ısıl değere göreyse yaklaşık 0,182 kullanın."),
        ("Kıyas", "Gösterge seti (EUI, karbon, su)", "SNET kWh/m²·yıl · kgCO₂e/m²·yıl · m³/m²·yıl", ["ETKB_KIYASLAMA"], "birincil",
         "Uygulamadaki göstergeler ETKB'nin önerdiği ölçülmüş (operasyonel) kıyaslama göstergeleriyle aynıdır; birincil enerji (SBET) için resmî katsayılara ulaşılamadı."),
        ("Kıyas", "Kullanım tipine göre EUI kıyas değerleri", "Ayarlar'daki tablo", ["ES2024", "ES_SCORE"], "birincil",
         "ABD ulusal medyanı (CBECS). Türkiye iklimi/uygulaması farklıdır; BEP-TR referans değerleri girilirse değiştirin."),
        ("Kıyas", "Karbon yoğunluğu kıyas değeri", "kıyas EUI x ağırlıklı emisyon faktörü", [], "varsayım",
         "Elektrik/gaz payı %50 varsayımıyla türetilir; doğrudan kaynak yok."),
        ("Kıyas", "Su yoğunluğu kıyas değeri", f"{a.benchmark_water_m3_m2:.2f} m³/m²·yıl", [], "varsayım", "Kaynak bulunamadı."),
        ("Sınıf", "Enerji sınıfı (A-G) sınırları", "Ep = 100×EUI/kıyas: 40-80-100-120-140-175", ["CSB_EKB", "BEPYON"], "birincil",
         "Resmî BEP-TR ölçeği (referans bina Ep=100, D'nin üst sınırı)."),
        ("Sınıf", "Referans bina yerine kıyas değeri", "ENERGY STAR medyanı (Ayarlar)", ["ES2024"], "varsayım",
         "Resmî sınıf, modellenmiş referans binaya ve birincil enerjiye göredir; burada kıyas medyanı ve nihai enerji (EUI) kullanılır. Sonuç göstergedir, Enerji Kimlik Belgesi değildir."),
        ("Sınıf", "Benzer binalara göre yüzdelik", "log-normal model, σ=0,35", ["ES_SCORE"], "varsayım",
         "Medyan = kıyas değeri; dağılım şekli varsayımdır, ENERGY STAR regresyon kullanır."),
        ("Skor", "Health Score yöntemi", "4 bileşen, ağırlıklı ortalama", ["JRC2008"], "özet",
         "Normalizasyon eşikleri ve ağırlıklar uzman kararıdır; skor ağırlık duyarlılığı aralığıyla birlikte gösterilir."),
        ("Skor", "Ekipman ömrü", "Tür başına 15-30 yıl", ["ASHRAE_LIFE"], "ikincil", "Soğutucu, kazan, santral ve pompa için ayrı ömür kullanılır."),
        ("Finans", "İskonto oranı", f"%{a.discount_rate * 100:.1f} (reel)", ["EU244"], "varsayım",
         "AB metodolojisi reel oran ve en az iki oranla duyarlılık analizi ister (makroekonomik referans reel %3); finansal oranın değeri belirtilmez. Duyarlılık tablosunda %3 ve ±2 puan gösterilir."),
        ("Finans", "Enerji fiyat artışı", f"%{a.energy_escalation * 100:.1f} (reel)", [], "varsayım", "Kaynak yok; duyarlılık tablosunda %0 senaryosu var."),
        ("Finans", "Analiz süresi", f"{a.horizon_years} yıl", ["EU244"], "birincil",
         "AB 244/2012: ticari konut dışı binalar için 20 yıl, konut ve kamu binaları için 30 yıl."),
        ("Finans", "Tasarruf kaybı", f"%{a.savings_degradation * 100:.1f}/yıl", ["PERSISTENCE"], "ikincil",
         "Donanım değişikliği için doğrudan veri yok; işletme önlemleri çok daha hızlı erir (SMUD: %10,5 → %8, 2 yılda)."),
        ("Finans", "Yatırım maliyetleri (₺/m²)", "Öneri kataloğunda", [], "varsayım",
         "Resmî bir yenileme birim fiyatı bulunamadı; teklif ya da keşifle değiştirin. Bağlam için paket yatırımı, 2026 yeniden inşa birim maliyetiyle (YAPI2026) oranlanır."),
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


def replacement_cost_per_m2(use_type: str, floors: int) -> float | None:
    """2026 Yapı Yaklaşık Birim Maliyetleri (TL/m²) - yalnız ofis/ticari için, kat sayısından (3,5 m/kat varsayımıyla) yüksekliğe göre sınıf."""
    if use_type not in ("Ofis", "Ticari / AVM"):
        return None
    h = floors * 3.5
    if floors <= 3:
        return 21050.0
    if h < 21.5:
        return 23400.0
    if h < 30.5:
        return 26450.0
    if h < 51.5:
        return 33900.0
    return 40500.0


OFFICIAL_THRESHOLDS = [
    ("Enerji sınıfı ölçeği", "A 0-39 · B 40-79 · C 80-99 · D 100-119 · E 120-139 · F 140-174 · G 175+ (referans bina = 100)", "CSB_EKB"),
    ("Yeni binalar", "BEP-TR ile belge alacak yeni binalar D veya daha kötü sınıfta olamaz", "BEPYON"),
    ("Neredeyse sıfır enerjili bina (NSEB)", "Enerji sınıfı B veya daha iyi ve birincil enerjinin en az %10'u yerinde yenilenebilir", "BEPYON"),
    ("Düşük karbonlu bina belgesi (2026)", "Sera gazı sınıfı en az B ve enerji performans sınıfı en az C", "BEPYON"),
    ("Enerji Kimlik Belgesi geçerliliği", "10 yıl; binanın birincil enerji ihtiyacı değişirse bir yıl içinde yenilenir", "CSB_EKB"),
    ("Kapsam dışı", "Mücavir alan dışında toplam inşaat alanı 1.000 m²'den küçük binalar; 50 m² altı yapılar", "CSB_EKB"),
]
