# EDIFI'CE: Kaynaklar ve Yöntem

Bu dosya `edifice/evidence.py` kaydından üretilir (`python tools/make_docs.py`). Doğrulama düzeyleri:

- **Kaynak okundu**: kaynağın kendisi okundu, rakamlar oradan alındı.
- **Özet okundu**: özet/yayıncı sayfası okundu, tam metin okunmadı.
- **İkincil aktarım**: rakam başka bir kaynağın aktarımından alındı, asıl kaynakla doğrulanmalı.
- **Varsayım**: doğrulanabilir kaynak bulunamadı.

## Hesap parametreleri

| Grup | Parametre | Değer | Düzey | Kaynak | Not |
|---|---|---|---|---|---|
| Karbon | Elektrik emisyon faktörü | 0,437 kgCO₂/kWh | Özet okundu | SAHIN2022, EMBER2024 | 2020 üretim bazlı değer; iletim-dağıtım kayıpları ve yıllık değişim hariç. Güncel resmi faktörle değiştirin. |
| Karbon | Doğalgaz emisyon faktörü | 0,202 kgCO₂/kWh | İkincil aktarım | IPCC2006 | Net kalorifik değer bazı. Fatura kWh'si üst ısıl değere göreyse yaklaşık 0,182 kullanın. |
| Kıyas | Kullanım tipine göre EUI kıyas değerleri | Ayarlar'daki tablo | Kaynak okundu | ES2024, ES_SCORE | ABD ulusal medyanı (CBECS). Türkiye iklimi/uygulaması farklıdır; BEP-TR referans değerleri girilirse değiştirin. |
| Kıyas | Karbon yoğunluğu kıyas değeri | kıyas EUI x ağırlıklı emisyon faktörü | Varsayım | - | Elektrik/gaz payı %50 varsayımıyla türetilir; doğrudan kaynak yok. |
| Kıyas | Su yoğunluğu kıyas değeri | 0,90 m³/m²·yıl | Varsayım | - | Kaynak bulunamadı. |
| Sınıf | Enerji sınıfı (A-G) sınırları | EUI/kıyas oranı: 0,5-0,75-1,0-1,3-1,65-2,0 | Varsayım | BEPTR | Resmi BEP-TR sınır tablosu doğrulanamadığı için göstergedir; resmi Enerji Kimlik Belgesi yerine geçmez. |
| Sınıf | Benzer binalara göre yüzdelik | log-normal model, σ=0,35 | Varsayım | ES_SCORE | Medyan = kıyas değeri; dağılım şekli varsayımdır, ENERGY STAR regresyon kullanır. |
| Skor | Health Score yöntemi | 4 bileşen, ağırlıklı ortalama | Özet okundu | JRC2008 | Normalizasyon eşikleri ve ağırlıklar uzman kararıdır; skor ağırlık duyarlılığı aralığıyla birlikte gösterilir. |
| Skor | Ekipman ömrü | Tür başına 15-30 yıl | İkincil aktarım | ASHRAE_LIFE | Soğutucu, kazan, santral ve pompa için ayrı ömür kullanılır. |
| Finans | İskonto oranı | %8,0 (reel) | Varsayım | EU244 | AB metodolojisi reel oran ve duyarlılık analizi ister; sayısal oran kaynaktan doğrulanamadı, duyarlılık tablosunda ±2 puan gösterilir. |
| Finans | Enerji fiyat artışı | %3,0 (reel) | Varsayım | - | Kaynak yok; duyarlılık tablosunda %0 senaryosu var. |
| Finans | Analiz süresi | 15 yıl | Varsayım | EU244 | Önlemlerin ömrüne göre seçilmelidir. |
| Finans | Tasarruf kaybı | %0,5/yıl | İkincil aktarım | PERSISTENCE | Donanım değişikliği için doğrudan veri yok; işletme önlemleri çok daha hızlı erir (SMUD: %10,5 → %8, 2 yılda). |
| Finans | Yatırım maliyetleri (₺/m²) | Öneri kataloğunda | Varsayım | - | Piyasa fiyatı/keşif bedeliyle değiştirin. |

## Dönüşüm önerileri: tasarruf aralıkları

| Öneri | Düşük | Tipik | Yüksek | Düzey | Kaynak | Türetme |
|---|---|---|---|---|---|---|
| LED aydınlatma dönüşümü | %4.0 | %6.5 | %10.5 | İkincil aktarım | PNNL24526, EIA_OFFICE | Aydınlatma ofis enerjisinin ~%12'si (EIA) ≈ elektriğin %17'si (elektrik payı ~%70 varsayımı); LED tasarrufu aydınlatma enerjisinde %24-61, ort. %37 (PNNL-24526); kontrolle tahmini %62 → elektrikte %4-10,5. |
| Yüksek verimli chiller | %2.0 | %4.0 | %7.0 | İkincil aktarım | CHILLER_CASES, EIA_OFFICE | Soğutma ofis enerjisinde ≤%8 (EIA) ≈ elektriğin ≤%11; soğutucu değişiminde rapor edilen enerji tasarrufu %20-35 (satıcı vaka çalışmaları) → elektrikte %2-4; sıcak iklimde soğutma payı yüksekse üst sınır %7. |
| Fan/pompa hız kontrolü (VFD) | %4.0 | %7.0 | %11.0 | İkincil aktarım | SCHIBUOLA2018, ASHRAE_VFD, EIA_OFFICE | Havalandırma ofis enerjisinin ~%20'si (EIA) ≈ elektriğin %29'u; fan+pompa tasarrufu %38,9'a kadar (Schibuola 2018), saha gerçekleşmesi idealin ~%40'ına inebilir (ASHRAE 2016) → %15-39 → elektrikte %4-11. |
| Çatı ve cephe yalıtımı | %8.0 | %15.0 | %21.0 | İkincil aktarım | ORNL_ENVELOPE | Kabuk iyileştirmesinde ölçülen normalize ısıtma tasarrufu %12-21 (LBL, konut) ve tipik %10-20; ölçülen tasarruf çoğunlukla tahminin ~yarısı (ORNL) → temkinli %15. Ofis verisi değil. |
| Yoğuşmalı kazan | %7.0 | %12.0 | %21.0 | İkincil aktarım | MNCEE_BOILER | Nominal verimi %70-82 olan eski kazandan, ölçülen ortalama %88,6'ya (MnCEE, 12 bina) geçişte yakıt tasarrufu 1-η_eski/η_yeni = %7-21 (η=%78 için %12). Gazın ısıtmaya gittiği varsayımı. |

## Kaynakça

### ES2024 (Kaynak okundu)

U.S. EPA ENERGY STAR Portfolio Manager. U.S. Energy Use Intensity by Property Type, Technical Reference, Ağustos 2024.

Ulusal medyan site EUI (CBECS tabanlı). Ofis 52,9; Konut (çok aileli) 59,6; Otel 63,0; Hastane 234,3; Okul (K-12) 48,5; Perakende 51,4; Karma kullanım 40,1 kBtu/ft². Sanayi için veri yok.

https://portfoliomanager.energystar.gov/pdf/reference/US%20National%20Median%20Table.pdf

### ES_SCORE (Kaynak okundu)

U.S. EPA ENERGY STAR. How the 1-100 ENERGY STAR score is calculated.

Benzer binalarla kıyas; işletme saatleri ve yoğunluk gibi etkenler regresyonla düzeltilir; 50 puan medyan performanstır.

https://www.energystar.gov/buildings/benchmark/understand-metrics/how-score-calculated

### SAHIN2022 (Özet okundu)

Sahin H., Esen H. (2022). The usage of renewable energy sources and its effects on GHG emission intensity of electricity generation in Turkey. Renewable Energy 192: 859-869. doi:10.1016/j.renene.2022.03.141

Türkiye elektrik üretimi emisyon yoğunluğu 2008'de 563, 2020'de 437 gCO2e/kWh (üretim bazlı; iletim-dağıtım kayıpları hariç).

https://ideas.repec.org/a/eee/renene/v192y2022icp859-869.html

### EMBER2024 (Özet okundu)

Ember (2024). Türkiye Electricity Review 2024.

2023'te kömür üretimi rekor 118 TWh; toplam üretimin yaklaşık %36'sı (322 TWh). Kömür payı yüksek kaldığı için şebeke emisyon yoğunluğu yüksektir.

https://ember-energy.org/latest-insights/turkiye-electricity-review-2024

### IPCC2006 (İkincil aktarım)

IPCC (2006). 2006 IPCC Guidelines for National Greenhouse Gas Inventories, Vol. 2 Energy, Ch. 2 Stationary Combustion.

Doğalgaz varsayılan CO2 faktörü 56.100 kg/TJ (%95 aralığı 54.300-58.300), net kalorifik değer bazlı. 56,1 kg/GJ x 0,0036 GJ/kWh = 0,202 kgCO2/kWh. Üst ısıl değere (GCV) göre faturalanan kWh için yaklaşık %10 düşük (0,182).

https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/2_Volume2/V2_2_Ch2_Stationary_Combustion.pdf

### MILLS2011 (Özet okundu)

Mills E. (2011). Building commissioning: a golden opportunity for reducing energy costs and greenhouse-gas emissions in the United States. Energy Efficiency 4: 145-173. doi:10.1007/s12053-011-9116-8

643 ticari bina meta-analizi: mevcut binalarda medyan tüm-bina enerji tasarrufu %16, medyan geri ödeme 1,1 yıl (üst çeyrek 0,4; alt çeyrek 2,4 yıl).

https://doi.org/10.1007/s12053-011-9116-8

### PNNL24526 (Kaynak okundu)

Davis R., Murphy A., Perrin T. (2015). Evaluation of an LED Retrofit Project at Princeton University's Carl Icahn Laboratory. PNNL-24526, Pacific Northwest National Laboratory.

Aydınlatma enerjisinde LED tasarrufu armatür tipine göre: 2x2 troffer %24, 4' lineer T8 %42, CFL downlight %61; toplam %37. Doluluk sensörü/dimleme eklenince tahmini %62. (Tahmindir, ölçüm değil.)

https://www.pnnl.gov/main/publications/external/technical_reports/PNNL-24526.pdf

### ASHRAE_VFD (İkincil aktarım)

ASHRAE Annual Conference 2016, Session 19668 (değişken hızlı sürücü saha performansı oturumu).

Gerçekleşen/ideal tasarruf oranı sıklıkla %40 kadar düşük; ideal hesaba dayanan teşvik programları tasarrufu ~%30 abartabilir.

https://ashraem.confex.com/ashraem/s16/webprogram/Session19668.html

### SCHIBUOLA2018 (İkincil aktarım)

Schibuola L. ve ark. (2018). Değişken debili pompa ve fan sistemlerinin uzun süreli izlenen bir kamu binasında performansı.

Sabit hızlı sisteme göre pompa+fan enerjisinde yıllık %38,9 tasarruf (tek bina; tam metin okunamadı, başlık/dergi doğrulanmalı).

https://air.iuav.it/handle/11578/277199

### MNCEE_BOILER (İkincil aktarım)

Minnesota Center for Energy and Environment (MnCEE). Yoğuşmalı kazanların saha performansı izleme çalışması (12 bina).

Yoğuşmalı kazanlar beklenen tasarrufun yarısından biraz fazlasını sağladı; ortalama gerçekleşen verim %88,6 (nominalin ~5 puan altı).

https://www.mncee.org/sites/default/files/report-files/386675.pdf

### ORNL_ENVELOPE (İkincil aktarım)

ORNL saha testi (Pacific Northwest ağırlaştırma programı) ve LBL tek aile bina yalıtım çalışmaları.

Duvar yalıtımında ölçülen tasarruf tahminin yaklaşık yarısı; LBL: tavan+duvar yalıtımı normalize yıllık tüketimde %12-21 (10 proje, konut). Ofis verisi değil.

https://info.ornl.gov/sites/publications/Files/Pub57672.pdf

### CHILLER_CASES (İkincil aktarım)

Üretici/yüklenici vaka çalışmaları (Danfoss/Univ. Cincinnati, Daikin/Tampa ofis, Trane/Kowloon hastane, CLEAResult kampüs).

Soğutucu değişiminde rapor edilen enerji tasarrufu ~%20-35 (tesis düzeyi + kontrol ile %41). Satıcı kaynaklı; en iyi durum olarak okunmalı.

https://www.danfoss.com/en-us/service-and-support/case-stories/cf/advanced-technology-chiller-compressors-propel-significant-energy-and-operational-savings-at-university-of-cincinnati

### EIA_OFFICE (İkincil aktarım)

U.S. EIA. Commercial Buildings Energy Consumption Survey (CBECS), office buildings profile.

Ofislerde son kullanım payları (tüm yakıtlar): ısıtma %30, havalandırma %20, aydınlatma %12; diğer son kullanımların her biri ≤%8.

https://www.eia.gov/consumption/commercial/pba/office.php

### VANDRONKELAAR2016 (Kaynak okundu)

van Dronkelaar C., Dowson M., Burman E., Spataru C., Mumovic D. (2016). A Review of the Energy Performance Gap and Its Underlying Causes in Non-Domestic Buildings. Frontiers in Mechanical Engineering 1:17. doi:10.3389/fmech.2015.00017

62 bina: ölçülen ile tahmin edilen enerji kullanımı ortalama +%34 saptı (SS %55). Baskın nedenler: modelleme belirsizliği (%20-60), kullanıcı davranışı (%10-80), kötü işletme (%15-80).

https://www.frontiersin.org/articles/10.3389/fmech.2015.00017/pdf

### DEWILDE2014 (Özet okundu)

de Wilde P. (2014). The gap between predicted and measured energy performance of buildings: A framework for investigation. Automation in Construction 41: 40-49. doi:10.1016/j.autcon.2014.02.009

Tahmin-ölçüm farkı (performance gap) için kavramsal çerçeve.

https://doi.org/10.1016/j.autcon.2014.02.009

### PERSISTENCE (İkincil aktarım)

Retro-commissioning tasarruf kalıcılığı: ASHRAE Journal (Aralık 2019) saha izleme çalışması; LBNL/SMUD değerlendirmesi (2004).

167 önlemde ortalama ~%61 kalıcılık; SMUD: tüm-bina tasarrufu 2. yılda %10,5'ten 4. yılda %8'e düştü. İşletme önlemleri (ayar/kontrol) donanım değişikliğinden daha çabuk erir.

https://www.ashrae.org/technical-resources/ashrae-journal/featured-articles/persistence-in-energy-savings-from-retro-commissioning-measures

### ASHRAE_LIFE (İkincil aktarım)

ASHRAE Handbook - HVAC Applications, 'Owning and Operating Costs' bölümü; ASHRAE ekipman ömrü çizelgeleri.

Aktarımlarda aralıklar farklı: soğutucu 15-25(30), kazan 20-30(15-30), klima santrali 15-20 (özel yapım 30), pompa 10-20 (kaideli 25), soğutma kulesi 15-25 yıl. Asıl çizelgeyle doğrulanmalı.

https://www.ashrae.org

### ASHRAE_G14 (İkincil aktarım)

ASHRAE Guideline 14: Measurement of Energy, Demand, and Water Savings.

Aylık veride kalibrasyon ölçütleri: CV(RMSE) ≤ %15, NMBE ≤ ±%5 (saatlik: %30 / ±%10). Gelecekte veri kalitesi kontrolünde kullanılabilir.

https://www.ashrae.org

### EU244 (Özet okundu)

Commission Delegated Regulation (EU) No 244/2012 (maliyet-optimal enerji performansı gereksinimleri için karşılaştırmalı metodoloji).

İskonto oranı reel terimlerle ifade edilir; oran duyarlılık analiziyle belirlenir; küresel maliyet = yatırım+işletme+yenileme maliyetlerinin bugünkü değeri. Sayısal oranlar doğrulanamadı.

https://eur-lex.europa.eu/eli/reg_del/2012/244/2013-04-06/eng

### JRC2008 (Özet okundu)

Nardo M., Saisana M., Saltelli A., Tarantola S., Hoffmann A., Giovannini E. (2008). Handbook on Constructing Composite Indicators: Methodology and User Guide. OECD/JRC, ISBN 978-92-64-04345-9.

Bileşik gösterge kurma adımları: normalizasyon, ağırlıklandırma, birleştirme, güçlülük ve duyarlılık analizi. Health Score bu çerçeveyle kurgulandı.

https://knowledge4policy.ec.europa.eu/sites/default/files/jrc47008_handbook_final.pdf

### BEPTR (İkincil aktarım)

Binalarda Enerji Performansı Yönetmeliği ve BEP-TR (Çevre, Şehircilik ve İklim Değişikliği Bakanlığı).

Türkiye'de enerji sınıfı A-G, binanın yıllık birim alan enerji tüketimi ve CO2 salımının referans binayla kıyaslanmasına dayanır; NSEB için B veya daha iyi sınıf ve %10 yenilenebilir pay istenir. Sınıf sınırlarının sayısal tablosu doğrulanamadı.

https://eyb.metu.edu.tr/sites/eyb.metu.edu.tr/files/binalarda_enerji_performansi_yonetmeligi.pdf

### EPBD2024 (İkincil aktarım)

Directive (EU) 2024/1275 (EPBD yeniden düzenleme, 2024).

Konut dışı binalarda en kötü performanslı %16'nın 2030'a, %26'sının 2033'e kadar iyileştirilmesi hedefi; üye devletler asgari performans standartlarını belirler.

https://eur-lex.europa.eu/eli/dir/2024/1275/oj

## Sınırlamalar

- Kıyas değerleri ABD ulusal medyanıdır; Türkiye'ye özgü BEP-TR değerleriyle değiştirilmelidir.
- Enerji sınıfı göstergedir, resmi Enerji Kimlik Belgesi değildir; sınır tablosu resmi kaynaktan doğrulanamadı.
- Tasarruf aralıkları literatürden türetildi; bina özelinde etüt/ölçümün yerini tutmaz (tahmin-ölçüm farkı ortalama +%34, SS %55).
- Yatırım maliyetleri doğrulanmış kaynağa dayanmaz.
- Hava normalizasyonu ve M&V (IPMVP / ASHRAE Guideline 14) bu sürümde yok.
