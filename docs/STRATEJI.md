# Piyasa konumu ve geliştirme yol haritası

Bu belge, EDIFI'CE'in benzer ürünlerin önüne geçmesi için nerede güçlü olduğunu ve neyin eksik olduğunu özetler.
Rakip bilgileri üçüncü taraf listelerden ve satıcı sayfalarından derlendi (aşağıdaki bağlantılar); doğrulanmamış pazarlama iddiaları olabilir.

## Rakiplerin durumu (bulunan kaynaklara göre)
| Ürün | Güçlü olduğu yer | Zayıf/bilinmeyen |
|---|---|---|
| ENERGY STAR Portfolio Manager (ücretsiz, EPA) | Karşılaştırma (benchmark), puanlama, tanınırlık; en az 11 ardışık ay fatura ister | Retrofit senaryosu/ROI yok; ABD odaklı |
| Measurabl | ENERGY STAR eşitlemesi, GRESB ve ESG raporlama | Retrofit modelleme ayrıntısı bulunamadı |
| Deepki | Sanal retrofit/senaryo ve ROI, otomatik veri toplama (API, sayaç, BMS), büyük kurumsal portföy | Fiyat kurumsal ve opak; küçük/orta mal sahibi için ağır |
| Envizi (IBM) | CRREM modelleme aracı (karbon yolu ve “stranded asset” analizi) | Karmaşık, kurumsal |

Kaynaklar: [Nectar karşılaştırması](https://nectarclimate.com/compare/measurabl-vs-deepki-vs-yardi), [CB Insights Deepki–Measurabl](https://www.cbinsights.com/compare/deepki-vs-measurabl), [Net Zero Compare – Deepki](https://netzerocompare.com/software/deepki-for-owners), [ENERGY STAR Portfolio Manager](https://www.energystar.gov/node/156), [IBM Envizi CRREM](https://www.ibm.com/docs/en/SSFJN8P/topics/c_crrem_overview.html), [Springwise – Deepki](https://www.springwise.com/innovation/property-construction/ESG-monitoring-software-for-real-estate).

## EDIFI'CE'in bugünkü farkı
1. **Karar motoru:** öneri → tasarruf aralığı (düşük/tipik/yüksek) → CAPEX → NPV/IRR/duyarlılık → bütçeye göre en iyi paket. Portfolio Manager'da yok; Deepki'de var ama kapalı kutu.
2. **Şeffaflık:** her sayı kanıt düzeyiyle (birincil/özet/ikincil/varsayım) ve kaynakla; veri güvenilirliği skoru.
3. **Türkiye'ye özel:** BEP-TR sınıf ölçeği, ETKB emisyon faktörü, ₺ ve Türkçe arayüz/asistan. (Rakiplerin Türkiye desteğini doğrulamadım.)
4. **Yerel ve gizli:** masaüstü, veri bilgisayarda; kendi yerel yapay zekası; abonelik/bulut zorunluluğu yok.

## En büyük açıklar (rakiplerin önüne geçmek için)
1. **Hava normalizasyonu (derece-gün):** tüketimi iklime göre düzeltmeden yıllar arası karşılaştırma ve tasarruf iddiası güvenilir sayılmaz.
2. **Gerçekleşen tasarruf takibi (M&V, IPMVP):** önerilen vs gerçekleşen tasarrufu ölçmek; rakiplerin çoğu “tahmin”de kalıyor.
3. **Veri girişi sürtünmesi:** fatura PDF/foto okuma, toplu Excel/CSV, sayaç/API bağlantısı. Portfolio Manager'ın en büyük derdi veri girişi.
4. **Karbon yolu ve “stranded asset” (CRREM benzeri):** bina hangi yıl hedef yolunu aşar; şu an basit doğrusal hedef var.
5. **Raporlama paketleri:** EKB veri sayfası, TSRS/CSRD, GRESB, AB Taksonomisi; tek tıkla.
6. **Güneş enerjisi (GES) ve tarife optimizasyonu:** Türkiye'de en çok sorulan yatırım; henüz yok.
7. **Teşvik/hibe bulucu:** uygun kredi, hibe ve vergi teşviklerini projeye eşlemek (kaynaklar doğrulanmalı).
8. **Çok kullanıcı ve bulut eşitleme, roller, saha denetim (mobil) uygulaması.**

## Önerilen sıra
1 → 3 → 2 → 6 → 4 → 5 → 7 → 8. Gerekçe: önce hesapların güvenilirliği (1), sonra veri girişinin kolaylığı (3), sonra ürünün “tahmin değil sonuç” iddiası (2).

## Durum
- ✅ 1. Hava normalizasyonu (derece-gün), ✅ 2. Toplu CSV/Excel içe aktarma (fatura PDF/foto okuma henüz yok), ✅ 3. Gerçekleşen tasarruf takibi (M&V).
- ✅ 4. GES (PVGIS ile) ve birim fiyat analizi (gerçek tarife optimizasyonu saatlik/demand verisi ister, yok), ✅ 5. Hedef yolu riski (kendi hedef yolunuzla; resmî CRREM verisi alınmadı), ✅ 6. Raporlama paketleri (ESG veri paketi, EKB hazırlık sayfası, portföy özeti; resmî beyan değil).
- Sıradaki: resmî CRREM yolları (veri doğrulanarak), fatura PDF/foto okuma, saatlik yük/demand verisiyle tarife optimizasyonu, teşvik/hibe bulucu, çok kullanıcı ve bulut eşitleme.
