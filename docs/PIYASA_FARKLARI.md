# EDIFI'CE ile yerleşik ürünler arasındaki güncel farklar

Tarih: 2026-10-10. Kaynak: aşağıdaki bağlantılar. Çoğu satıcı sayfası ya da üçüncü taraf listesidir; satıcı iddiaları doğrulanmış sayılmamalıdır.
Bu belge pazarlama değil, açık bir eksik listesidir: ✅ var · 🟡 kısmen · ❌ yok · ❔ kaynaklarda bulunamadı (rakipte olabilir).

## Bulunan kanıtlar (kısa)
- **ENERGY STAR Portfolio Manager (EPA, ücretsiz):** ulusal temsilî anket verisine (CBECS) dayanan 1–100 skor; 50 medyan, 75+ üst performans; skor tanı değil tarama aracıdır; veri girişi elle ya da bazı şirketlerin otomatik aktarımıyla. [EPA skor ölçütleri](https://www.energystar.gov/buildings/benchmark/understand-metrics/score-criteria), [skor açıklaması](https://www.energystar.gov/ENERGYSTARscore), [otomatik benchmarking örneği (SCE)](https://www.performanceservices.com/wp-content/uploads/2022/11/ENERGY_STAR_and_Automated_Benchmarking_Quick_Facts.pdf)
- **Deepki:** API, web kazıma ve SFTP ile otomatik veri toplama iddiası; Ocak 2025'te "AI destekli fizik modelleriyle sanal retrofit" modülü; GHG Protocol/SFDR/AB Taksonomisi uyumlu raporlama iddiası; ISO 27001/ISAE 3000 iddiaları yalnız üçüncü taraf listede. [Funds Europe](https://funds-europe.com/deepki-launches-ai-driven-tools-for-real-estate-decarbonisation/), [Net Zero Compare](https://netzerocompare.com/software/deepki-for-owners), [TechCrunch 2022](https://techcrunch.com/2022/03/31/deepki-grabs-166-million-to-help-real-estate-investors-reduce-carbon-emissions)
- **BMS/FDD platformları:** Johnson Controls OpenBlue'da kural tabanlı enerji hata tespiti (boşta/hafta sonu/puant tüketim, sayaç donması/çevrimdışı), otomatik iş emri; Schneider EcoStruxure Building Advisor'da sürekli hata tespiti. [JCI FDD](https://docs.johnsoncontrols.com/bas/r/Johnson-Controls/en-US/OpenBlue-Enterprise-Manager-Product-Bulletin/4.2.1/Overview-of-Energy-Manager-features/Energy-Fault-Detection-and-Diagnostics-FDD), [Schneider Building Advisor](https://www.se.com/nl/en/product-range/39297330-ecostruxure-building-advisor/)
- **Envizi (IBM):** CRREM karbon yolu modelleme aracı. [IBM belgesi](https://www.ibm.com/docs/en/SSFJN8P/topics/c_crrem_overview.html)
- **BEP-TR (resmî):** Bakanlık sunucusunda çalışan, merkezi veritabanlı EKB hesaplama yazılımı; sınıf referans bina ve birincil enerji karşılaştırmasıyla belirlenir. Sürümlerine ve etkisine yönelik eleştiriler var. [ÇŞİDB sunumu](https://webdosya.csb.gov.tr/db/ozonturkiye/haberler/4-ev-sunum-s-ubat.2024-namik-20240301105743.pdf), [EMO yayını](https://www.emo.org.tr/ekler/0d2cd51d97b9ecb_ek.pdf)

## Karşılaştırma
| Alan | Yerleşik ürünler | EDIFI'CE | Fark |
|---|---|---|---|
| **Veri girişi otomasyonu** | Utility veri aktarımı (PM), API/kazıma/SFTP, alt sayaç ve BMS (Deepki) | Elle form, Excel/CSV toplu içe aktarma | ❌ otomatik bağlantı yok (fatura PDF/foto okuma da yok) |
| **Ölçüm çözünürlüğü** | Saatlik/aralık verisi, alt sayaç, talep (kW) | Aylık fatura | ❌ saatlik/talep verisi yok → gerçek tarife optimizasyonu ve yük analizi yapılamıyor |
| **Hata tespiti (FDD)** | Kural kütüphanesi, anormal tüketim, sayaç hataları, iş emri | Aylık anomali, birim fiyat sapması | 🟡 yalnız aylık düzeyde; ekipman FDD yok |
| **Karşılaştırma (benchmark)** | CBECS tabanlı regresyonla 1–100 skor (PM) | ENERGY STAR medyan EUI + varsayımsal log-normal dağılım, BEP-TR A–G ölçeği (yaklaşık) | 🟡 Türkiye'ye özgü emsal verisi yok; skor regresyon değil; sınıf resmî EKB değil |
| **Resmî Türkiye çıktısı** | BEP-TR ile EKB (yetkili uzman) | EKB hazırlık veri sayfası, gösterge sınıfı | 🟡 resmî belge üretilmez (üretmemeli); gerçek EKB ile kalibrasyon yapılmadı |
| **Retrofit planlama** | Fizik tabanlı sanal retrofit, asset/fon/portföy (Deepki, iddia) | Literatür aralıklı tasarruf oranları, kanıt düzeyli, NPV/IRR, bütçe optimizasyonu, M&V | 🟡 şeffaf ama bina fiziğini modellemez; CAPEX birim fiyatları doğrulanmamış varsayım |
| **Gerçekleşen tasarruf (M&V)** | ❔ satıcı belgelerinde IPMVP desteği bulunamadı | Hava normalizasyonlu M&V, belirsizlikli | ✅ (rakiplerde olabilir) — ama gerçek bina verisiyle henüz hiç doğrulanmadı |
| **Karbon yolu / "stranded"** | CRREM aracı (Envizi) | Kendi hedef yolunuz | ❌ resmî CRREM yolları yok; şebeke dekarbonizasyonu modellenmiyor |
| **Raporlama/beyan** | GHG Protocol, SFDR, AB Taksonomisi, GRESB (iddialar) | Excel veri paketleri (Kapsam 1–2) | 🟡 resmî format/şablon, Kapsam 3, denetim izi yok |
| **Güvenlik ve güvence** | ISO 27001, ISAE 3000 Type 2 gibi iddialar (doğrulanmadı), SSO, roller | Yerel masaüstü, imzasız kurulum | ❌ bağımsız denetim/sertifika yok; yerel veri bir avantaj ama kurumsal satın alma "kanıt" ister |
| **Çok kullanıcı / bulut / API** | Var (kurumsal) | Tek kullanıcı, yerel | ❌ eşitleme, roller, API, denetim kaydı yok |
| **Kontrol / otomasyon** | Setpoint otomatik ayarı (JCI, 2025 duyurusu) | Yok | ❌ kapsam dışı (BMS entegrasyonu gerekir) |
| **Doğrulama ve itibar** | Yıllarca üretimde, çok sayıda bina | Pilot bina yok, bağımsız doğrulama yok | ❌ **en büyük fark**: "kendini kanıtlamış" olmak için gerçek bina sonuçları gerekir |
| **Yerelleştirme** | Çoğu Türkçe/Türkiye'ye odaklı değil (doğrulanmadı) | Türkçe, ₺, BEP-TR ölçeği, ETKB faktörü, TR adres | ✅ güçlü yön |
| **Şeffaflık** | Kapalı kutu modeller (özellikle AI retrofit) | Her sayı kaynak+kanıt düzeyiyle, veri güvenilirliği skoru, açık yöntem | ✅ güçlü yön |
| **Maliyet/gizlilik** | Abonelik, bulut | Ücretsiz/yerel, veri bilgisayarda | ✅ güçlü yön (küçük/orta ölçek için) |

## Dürüst özet
EDIFI'CE'in gerçek farkları: şeffaflık, Türkiye'ye özel kapsam, yerel/ücretsiz çalışma, yatırım karar motoru + M&V + veri güvenilirliği. Yerleşik ürünlerin açık farkı ise **güvence** ve **otomasyon**: bağımsız doğrulama, gerçek bina referansları, otomatik veri hattı, saatlik veri, kurumsal güvenlik.
"Kendini kanıtlamış" seviyesine gelmek için önce kanıt üretmek gerekir; yeni özellik eklemek bu farkı kapatmaz.

## Farkı kapatan sıra
1. **Gerçek doğrulama:** 2–3 gerçek pilot bina (en az 24 ay fatura): sınıfı gerçek EKB ile, M&V sonucunu gerçekleşmiş bir yatırımla karşılaştırıp yayımlanabilir bir vaka çalışması çıkarmak.
2. **Veri hattı:** fatura PDF/foto okuma; mümkünse dağıtım şirketi/sayaç veri bağlantısı (iş ortaklığı gerekir).
3. **Aralık verisi:** saatlik/15 dk yük içe aktarma → gerçek tarife/talep optimizasyonu, FDD kuralları, daha güvenilir GES boyutlandırma.
4. **Türkiye emsal verisi:** BEP-TR/EKB verisi ya da anonim toplanmış emsal kümesiyle gerçek benchmark.
5. **Resmî CRREM yolları** (doğrulanarak), şebeke dekarbonizasyonu.
6. **Güvence:** kod imzalama, bağımsız güvenlik incelemesi, sonra ISO 27001; çok kullanıcı/bulut/API.
