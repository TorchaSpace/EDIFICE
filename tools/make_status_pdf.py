"""docs/EDIFICE_Durum_Raporu.pdf üretir: mevcut özellikler, olmayanlar ve nedenleri. Kullanım: python tools/make_status_pdf.py"""
import html
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QFont, QFontDatabase, QPageLayout, QPageSize, QPdfWriter, QTextDocument
from PySide6.QtWidgets import QApplication

import edifice
from edifice.ai.local import INTENTS
from edifice.db import SCHEMA
from edifice.evidence import SOURCES, parameter_rows
from edifice.models import Assumptions

app = QApplication.instance() or QApplication([])
for f in sorted((root / "edifice" / "assets" / "fonts").glob("*.ttf")):
    QFontDatabase.addApplicationFont(str(f))

tests = int(re.search(r"(\d+) tests? collected", subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], cwd=root,
                                                                  capture_output=True, text=True).stdout).group(1))
loc = sum(len(f.read_text(encoding="utf-8").splitlines()) for f in (root / "edifice").rglob("*.py"))
tables = re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", SCHEMA)
params = parameter_rows(Assumptions())
e = html.escape

HAVE = [
    ("1. Veri girişi ve bina yönetimi", [
        "<b>Bina Ekle formu</b> (3 adım): bina bilgisi, son iki yılın 12'şer aylık elektrik/doğalgaz/su tüketimi ve tutarı, ekipman envanteri. Girişler kaydedilmeden önce doğrulanır; hatalar alan alan listelenir.",
        "<b>Adres:</b> ülke / il / ilçe / açık adres ayrı alanlardır, yazdıkça OpenStreetMap tabanlı (Photon) önerilerle tamamlanır; her alan üstteki seçime göre süzülür; listeden seçim zorunludur (internet yoksa zorlanmaz). Konum (enlem/boylam) kayıtta otomatik bulunur.",
        "<b>Excel</b>: talimatlı ve doğrulamalı şablon (boş ya da örnek dolu), doldurulan dosya içe aktarılır, hatalar hücre/sayfa adıyla bildirilir.",
        "<b>Toplu içe aktarma (CSV/Excel)</b>: geniş ve uzun biçim, ; , sekme ayırıcı, UTF-8 ve Windows-1254, 1.234,56 ve 1,234.56, “Mart 2025”/2025-03/03.2025 dönemleri; önizleme (kayıt sayısı, dönem, uyarılar, veri güvenilirliği önce/sonra) ve birleştirme; “Örnek CSV indir”.",
        "<b>Düzenleme, silme, çoklu bina</b>; bina değiştirme menüsü; tüm veri yerel SQLite'ta (~/.edifice).",
        "<b>Veri güvenilirliği skoru (0-100)</b>: eksik aylar, aykırı değer/olası birim hatası (medyanın 10 katı), tarifeden türetilmiş (gerçek fatura girilmemiş) maliyet, olmayacak alan/kat/kişi/EUI, ekipman yılları ve kategorileri, tek yıllık veri. Bina Ekle'de skor düşükse ikinci basışta kaydeder.",
    ]),
    ("2. Hesap motoru (UI'dan bağımsız, testli)", [
        "<b>KPI'lar:</b> toplam enerji, elektrik, doğalgaz, su, EUI (kWh/m²), karbon (tCO₂e ve kg/m²), maliyet; önceki yıla göre değişim.",
        "<b>Health Score (0-100):</b> enerji yoğunluğu, karbon yoğunluğu, su yoğunluğu ve ekipman durumu bileşenlerinin ağırlıklı toplamı; ağırlık duyarlılığı aralığı; ekipman ömrü türe göre (chiller, kazan, santral, pompa); bileşenler 0-100'e kırpılır.",
        "<b>Enerji sınıfı (A-G):</b> resmî BEP-TR Ep ölçeği (A&lt;40, B&lt;80, C&lt;100, D&lt;120, E&lt;140, F&lt;175, G); kıyas değeri ENERGY STAR ulusal medyanı; benzer binalara göre yüzdelik (log-normal varsayım). <i>Gösterge, resmî Enerji Kimlik Belgesi değildir.</i>",
        "<b>Dönüşüm önerileri:</b> LED, yüksek verimli chiller, fan/pompa hız kontrolü (VFD), çatı-cephe yalıtımı, yoğuşmalı kazan; her biri için düşük/tipik/yüksek tasarruf aralığı, kanıt düzeyi ve dayanak; ekipmana göre uygunluk (yüksek/orta/düşük/uygun değil/veri yok).",
        "<b>Senaryo:</b> seçilen önerilerle mevcut vs hedef (elektrik, doğalgaz, enerji, karbon, maliyet); aynı kalemi etkileyen önerilerde tasarruflar çarpımsal birleşir.",
        "<b>Finans:</b> 20 yıl reel nakit akışı, NPV, IRR, indirgenmiş geri ödeme, toplam net kazanç, düşük/yüksek tasarruf bantları, 8 satırlık duyarlılık tablosu; AB 244/2012 metodolojisine dayanır.",
        "<b>Bütçe optimizatörü:</b> verilen bütçeyle NPV'yi en yükseğe çıkaran öneri paketi (brute-force ile doğrulandı).",
        "<b>Hava normalizasyonu:</b> aylık tüketim = a + b·HDD + c·CDD regresyonu (b,c ≥ 0), son 10 yılın normal iklimine düzeltme, ham ve düzeltilmiş yıllık değişim, R² ile güven; R² &lt; 0,3 ise düzeltme yapılmaz.",
        "<b>Gerçekleşen tasarruf (M&amp;V):</b> biten projede, öncesi ≥12 ay veriden hava duyarlı baz model; sonrası ≥3 ay için “proje olmasaydı” tahmini; ±%95 belirsizlik, katalog beklentisine gerçekleşme oranı, model kalitesi (CV(RMSE), NMBE).",
        "<b>Canlı iklim ve öngörü:</b> anlık sıcaklık/nem/rüzgâr/ışınım, 7 gün geçmiş + 7 gün tahmin; HDD/CDD ile 7 günlük doğalgaz/elektrik öngörüsü ve normal haftayla kıyas; 30 dakikada bir yenilenir; günlük gözlemler birikir.",
        "<b>Çatı GES:</b> PVGIS (AB JRC) aylık verimi, aylık dengeli model, çatı sınırı, NPV'yi en yükseğe çıkaran boyut, geri ödeme/IRR/önlenen karbon.",
        "<b>Birim fiyat analizi:</b> etkin ₺/kWh aylık izlenir; medyandan %15'ten fazla sapan aylar ve olası fazla ödeme üst sınırı; tarifeden türetilmiş tutarlarda analiz yapılmaz.",
        "<b>Karbon hedefi ve yol riski:</b> kullanıcının hedefi (yıl, %), planlı projelerle birlikte; her bina için “yol aşım yılı”; radyal göstergeler; mevzuat eşikleri (C, B).",
        "<b>CRREM yolları:</b> kullanıcının crrem.org'dan kendi indirdiği resmî Excel içe aktarılır; ülke × mülk türü × ölçüt (kgCO₂e/m² ya da kWh/m²) seçilir; yol aşım yılı, grafik, isteğe bağlı şebeke dekarbonizasyonu (varsayım). Veri uygulamada yoktur (lisans).",
        "<b>Aylık anomali ve pik ay</b> tespiti; aylık maliyet/enerji/karbon grafikleri (önceki yılla).",
    ]),
    ("3. Ekranlar", [
        "<b>Sol menü (Figma yapısı):</b> Platform — Genel Bakış, Portföy, Projeler, Finans, Ortaklar; Intelligence — Asistan, Digital Twin, Sürdürülebilirlik, Raporlar, Ayarlar. Seçili sekmeye kayan gösterge, geçiş animasyonları.",
        "<b>Genel Bakış:</b> 8 KPI kartı, veri güvenilirliği paneli, hava düzeltmeli tüketim, portföy haritası ve skoru, bina skoru göstergesi, aylık maliyet, enerji sınıfı ve yüzdelik, öne çıkan fırsatlar, enerji/karbon grafikleri, proje zaman çizelgesi, son projeler. Alt sekmeler: Tüketim, İklim.",
        "<b>Portföy:</b> toplam alan/enerji/karbon/maliyet/skor/tasarruf kartları, OpenStreetMap haritası (yakınlaştırma, sürükleme, bina noktaları), bina listesi (skor, sınıf, veri güvenilirliği).",
        "<b>Projeler:</b> Öneriler tablosu; Proje takibi (durum, yıl, bitiş ayı, planlanan/biten CAPEX, M&amp;V paneli); Mevcut vs Hedef (senaryo, bütçe kaydırıcısı, finans, duyarlılık).",
        "<b>Finans:</b> Portföy finansı; Güneş enerjisi (GES); Birim fiyat analizi.",
        "<b>Sürdürülebilirlik:</b> radyal göstergeler, karbon yolu, hedef belirleme, mevzuat eşikleri, hedef yolu riski, CRREM paneli, karbon sıralaması.",
        "<b>Raporlar:</b> tek sayfalık yatırımcı PDF raporu (logolu, veri güvenilirlik satırı); Excel paketleri: ESG veri paketi (Kapsam 1-2), EKB hazırlık sayfası, portföy özeti; Kaynaklar ve Yöntem.",
        "<b>Ayarlar:</b> emisyon faktörleri, tarifeler, kıyas değerleri, Health Score ağırlıkları, ekipman ömrü, finans varsayımları, öneri kataloğu; veri güvenliği (JSON dışa aktarma, yedek klasörü).",
        "<b>Üst çubuk:</b> bina arama, gerçek verilerden bildirimler, canlı sıcaklık çipi, tarih, PDF rapor, Bina Ekle.",
    ]),
    ("4. Yerel yapay zeka asistanı", [
        f"Tamamen yerel çalışır (dış servis/API anahtarı yok): karakter n-gram TF-IDF niyet sınıflandırıcı, {len(INTENTS)} niyet, {sum(len(v) for v in INTENTS.values())} eğitim cümlesi, varlık çıkarımı (bütçe, öneri adı, bina adı, ay, durum, sayfa).",
        "Cevapladıkları: bina özeti, sorunlar, skor, sınıf, enerji/karbon/su/maliyet, yıllık değişim, pik ay, anomali, öneriler, nereden başlamalı, bütçeye göre paket, senaryo, finans, ekipman, portföy, karşılaştırmalar (iki bina, elektrik–doğalgaz, ay–yıl), “neden?”, kaynak/kanıt, veri kalitesi, hava düzeltmesi, canlı hava ve haftalık öngörü, GES, birim fiyat, gerçekleşen tasarruf.",
        "Komutlar: proje durumu değiştirme, sayfa açma, senaryo seçme, rapor üretme. Cevaplara mini grafik eklenir.",
        "Kendini eğitme: 👍/👎, anlaşılmayan sorular için Eğitim sekmesi, yeniden sorma sinyali, “şunu mu demek istedin?”; her öğrenme bozulma korumasından geçer (tüm mevcut örnekler hâlâ doğru sınıflanmalı); sıfırlama düğmesi.",
        "Rakamlar daima hesap motorundan gelir; kapsam dışı sorularda uydurmaz.",
    ]),
    ("5. Altyapı, güvenlik ve dağıtım", [
        f"<b>Veritabanı:</b> yerel SQLite, {len(tables)} tablo ({', '.join(tables)}); eski sürümlerden otomatik göç.",
        "<b>Veri güvenliği:</b> günlük otomatik yedek (son 7), açılışta bütünlük denetimi ve bozuksa yedekten geri yükleme, JSON dışa aktarma, hata günlüğü (~/.edifice/edifice.log) ve kullanıcıya bildirim.",
        "<b>Dış veri (ilk kullanımda indirilir, önbelleğe alınır, çevrimdışıyken son veri gösterilir):</b> OpenStreetMap karoları ve Photon (adres), Open-Meteo (geçmiş + canlı hava), PVGIS (güneş). Hiçbiri API anahtarı istemez.",
        "<b>Tasarım:</b> koyu premium tema, Manrope ve DM Mono gömülü yazı tipleri, özel çizimli grafikler (aşağıdan yükselen animasyon), yumuşak geçişler.",
        "<b>Paketleme:</b> macOS (Apple Silicon) DMG, Windows kurulum (.exe) ve taşınabilir zip; GitHub Actions ile otomatik derleme ve Release; paketli uygulamada otomatik kendi kendini sınama (selftest). Yayımlanan sürüm: v1.2.0 (v1.1.0 öncesi sürümler de Releases'te).",
        f"<b>Test ve doğrulama:</b> {tests} otomatik test: motor kimlikleri (KPI'ların ham veriden yeniden hesaplanması, NPV/IRR kimlikleri, optimizatör brute-force karşılaştırması, sınıf tek yönlülüğü), 60 bozuk girdi (fuzz), 8 bozuk binada tüm sayfaların açılması, hava/M&amp;V'nin bilinen gerçeği geri kazanması (yapay veri), ayrıştırıcılar, kaynak-öneri tutarlılığı, asistan akışları.",
        "<b>Belgeler:</b> docs/KAYNAKCA.md (30 kaynak, düzeyleriyle), PIYASA_FARKLARI.md, STRATEJI.md, RESMI_VERI_DURUMU.md, FIGMA_FARKLAR.md; CLAUDE.md proje notları.",
    ]),
]

MISSING = [
    ("Digital Twin", "Sayfa yalnız “sonraki faz” notu içerir.", "Dijital ikiz için bina BIM modeli ve canlı sensör (IoT/BMS) verisi gerekir; elde yok ve ilk ürün kapsamı (tek bina analizi) dışında bırakıldı. Uydurma görsel koymadım.", "BIM/IFC modeli, sensör/BMS veri akışı, 3B görselleştirme çalışması."),
    ("Ortaklar modülü", "Sayfa yalnız “sonraki faz” notu içerir.", "Firma/teklif kaydı için gerçek veri ve bir kayıt akışı tasarımı yok; sahte ortak listesi göstermek yanıltıcı olurdu.", "Ortak/teklif kayıt formu ve (varsa) ortak ağı verisi."),
    ("Gerçek zamanlı IoT, sayaç ve BMS entegrasyonu", "Yok; veri aylık fatura ya da elle/CSV ile girilir.", "Donanım, protokol (BACnet/Modbus vb.) ve dağıtım şirketi/sayaç sağlayıcı anlaşmaları gerekir; MVP kapsamı dışı. (Hava verisi canlıdır, tüketim değildir.)", "Sayaç/BMS erişimi, protokol bağlayıcıları, güvenlik incelemesi."),
    ("Saatlik/15 dk yük ve talep (kW) verisi; gerçek tarife optimizasyonu; ekipman hata tespiti (FDD)", "Yok; yalnız aylık analiz ve birim fiyat sapma analizi var.", "Tarife grubu, güç aşımı, reaktif bedel ve FDD kuralları aralık verisi ister; elde yok. Faturadaki kalemler girilmediği için fazla ödemenin nedeni de söylenemiyor.", "Aralık verisi içe aktarma, kural kütüphanesi, tarife tabloları."),
    ("Fatura PDF/fotoğraf okuma (OCR)", "Yok.", "Öncelik sırası gereği yapılmadı; güvenilir okuma için OCR bileşeni ve fatura şablonlarına özel doğrulama gerekir (hatalı okuma verinin güvenilirliğini bozar).", "OCR kütüphanesi, dağıtım şirketi fatura şablonları, kullanıcı onay akışı."),
    ("Resmî Enerji Kimlik Belgesi (EKB) üretimi", "Yok; yalnız gösterge sınıfı ve EKB hazırlık veri sayfası var.", "EKB, yetkili uzmanca Bakanlığın BEP-TR yazılımıyla (bina kabuğu, tesisat, referans bina ve birincil enerji hesabıyla) düzenlenir; bu hesap yöntemi kapalıdır ve belge üretmek yetkiyle ilgilidir.", "BEP-TR yöntem belgesi, yetkili uzman; gerçek bir EKB ile sınıf kalibrasyonu."),
    ("BEP-TR birincil enerji katsayıları ve referans bina değerleri", "Kullanılmıyor.", "Yönetmelik metninde sayısal katsayı yok (taranıp doğrulandı); katsayılar BEP-TR yöntem belgesinde/yazılımında ve herkese açık bulunamadı. Doğrulanamayan sayıyı kullanmadım.", "BEP-TR yöntem belgesi ya da Bakanlıktan resmî tablo."),
    ("Resmî CRREM verisinin uygulamaya gömülmesi", "CRREM yolları gömülü değil; kullanıcı kendi indirip içe aktarır.", "CRREM kullanım koşulları, veriyi ticari yazılıma gömmeyi ve yeniden dağıtmayı License Partner anlaşması olmadan yasaklar; “CRREM uyumlu” etiketi de ticari üründe yasaktır.", "CRREM Foundation ile License Partner anlaşması."),
    ("Türkiye için resmî CRREM yolu", "Yok; vekil ülke seçilir (kullanıcı kararı).", "İncelenen V2.01 dosyasında 65 ülke/şehir kodu var, Türkiye yok; güncel V2.04/V2.05 için ülke listesi doğrulanamadı.", "CRREM'in Türkiye'yi eklemesi ya da CRREM ile Türkiye yolu çalışması."),
    ("CRREM V2.04/V2.05 dosya biçimi doğrulaması", "İçe aktarıcı yalnız gerçek V2.01 ile sınandı.", "Güncel dosyaya kayıt formu ve kullanım koşulları arkasından erişilir; ben formu dolduramam. Biçim farklıysa içe aktarıcı anlamlı bir hata verir.", "Kullanıcının güncel dosyayı indirip denemesi."),
    ("Resmî GRESB / CSRD / TSRS beyan formatları", "Yok; Excel veri paketleri var ve “resmî beyan değildir” der.", "Beyan şablonları, kapsam 3 verisi, denetim izi ve üçüncü taraf doğrulama gerektirir; yanlış “uyumludur” iddiası riskli olurdu.", "Resmî şablonlar, Kapsam 3 verisi, denetçi."),
    ("Kapsam 3 ve soğutucu akışkan emisyonları", "Dahil değil; raporlarda belirtilir.", "Veri toplanmıyor (satın alınan mal/hizmet, kaçaklar vb.).", "Ek veri alanları ve emisyon faktörleri."),
    ("Resmî yenileme birim fiyatları", "CAPEX birim fiyatları varsayımdır (açıkça işaretli).", "Bakanlık 2026 birim fiyat listesi yayımlanmış ancak yalıtım/yenileme pozlarının sayısal fiyatları bulunamadı; piyasa rehberleri resmî değil.", "Birim fiyat kitabının ilgili pozları ya da gerçek teklifler."),
    ("Türkiye emsal (benchmark) verisi", "ENERGY STAR (ABD) medyanı kullanılıyor.", "Türkiye'ye özgü bina stoku tüketim verisi herkese açık bulunamadı.", "EKB veri tabanı ya da anonim emsal verisi."),
    ("Çok kullanıcı, bulut eşitleme, roller, API, denetim kaydı", "Yok; tek kullanıcı, yerel.", "Sunucu, kimlik doğrulama, güvenlik ve işletme maliyeti gerektirir; yerel/gizli çalışma bilinçli bir tercih.", "Sunucu altyapısı, kimlik yönetimi, güvenlik incelemesi."),
    ("Bağımsız güvenlik/doğruluk güvencesi (ISO 27001 vb.), kod imzalama", "Yok; kurulum dosyaları imzasız (SmartScreen/Gatekeeper uyarı verir).", "Apple Developer ve Windows kod imzalama sertifikaları ücretli ve hesap/kimlik gerektirir; sertifikasyon kurumsal süreçtir.", "Sertifikalar, imzalama hattı, bağımsız denetim."),
    ("Gerçek pilot bina doğrulaması", "Yapılmadı; demo bina sentetik.", "Gerçek bina verisi ve gerçekleşmiş bir yatırım henüz yok; M&amp;V ve hava normalizasyonu yalnız bilinen gerçeği olan yapay veriyle doğrulandı. “Kendini kanıtlamış” olmanın en büyük eksiği budur.", "En az 24 aylık fatura içeren 2-3 gerçek bina, varsa EKB ve tamamlanmış bir yatırım."),
    ("Windows'ta gerçek PC testi ve Intel Mac derlemesi", "Windows yalnız GitHub otomasyonunda sınandı; Intel Mac yok.", "Windows PC'ye ve Intel Mac'e erişimim yok; derleme hattı yalnız Apple Silicon ve Windows x64 üretir.", "Gerçek Windows PC denemesi; Intel Mac için ek derleme işi."),
    ("Serbest konuşan dil modeli", "Yok; asistan kural+niyet tabanlıdır.", "Kullanıcı dış API kullanılmamasını istedi; yerel model 1-4 GB indirme, yavaşlık ve zayıf Türkçe getirir. Asistan kapsam dışında uydurmaz, bunu söyler.", "Yerel model kararı (boyut/dil), ya da kullanıcı izniyle bulut modeli."),
    ("Sesli soru/yanıt, mobil/saha uygulaması, çoklu dil", "Yok.", "Kapsam dışı bırakıldı; arayüz yalnız Türkçe.", "Ayrı ürün işleri."),
    ("Teşvik/hibe/kredi bulucu", "Yok.", "Güncel ve doğrulanmış kaynak (mevzuat, çağrılar) ve düzenli güncelleme gerektirir; doğrulanamayan bilgi vermek riskli.", "Doğrulanmış teşvik veri seti ve güncelleme süreci."),
    ("Yatırım/finansal tavsiye", "Verilmez.", "Bilinçli tercih: uygulama seçenekleri ve sayıları sunar, kararı kullanıcıya bırakır.", "—"),
    ("Hava ve harita verisinin ticari kullanımı", "Şu an yalnız ticari olmayan kullanım için uygun.", "Open-Meteo ücretsiz planı ticari olmayan kullanım içindir; OSM karoları için ağır ticari kullanım politikası uygulanır; PVGIS kaynak gösterimi ister.", "Open-Meteo ticari planı veya kendi barındırma, karo sağlayıcı anlaşması."),
]

LIMITS = [
    "Tüm ekran ve akış denemeleri yazılım ortamında (ekransız render ve otomatik test) yapıldı; gerçek kullanıcılarla kullanılabilirlik testi yapılmadı.",
    "Demo bina verisi sentetiktir; ekrandaki hava düzeltmesi, M&amp;V ve öngörü sayıları anlam taşımaz. Yöntemler yalnız bilinen gerçeği olan yapay veriyle doğrulandı.",
    "Enerji sınıfı resmî değildir (kıyas: ENERGY STAR medyanı, nihai enerji); yüzdelik log-normal varsayımdır.",
    "Öneri tasarruf oranları literatür aralıklarıdır (çoğu ikincil kaynak); bina özelinde etüt ya da ölçümün yerini tutmaz. Tahmin–ölçüm farkı literatürde ortalama +%34'tür.",
    "GES birim maliyeti (25.000 ₺/kWp), eşzamanlılık (%85), fazla üretim değeri (0), çatı kullanımı (%60) ve 6 m²/kWp varsayımdır; sonuç maliyete çok duyarlıdır.",
    "Derece-gün taban sıcaklıkları (15/22 °C) ve veri kalitesi eşikleri sağduyu varsayımıdır (isimli sabitler; gerçek veriyle ayarlanmalı).",
    "Günlük enerji öngörüsü aylık modelin günlüğe indirilmesidir; hafta sonu/tatil etkisini bilmez. Hava verisi modellenmiştir, istasyon ölçümü değildir.",
    "Asistan bilmediği soruda bunu söyler; serbest sohbet yapamaz. Eğitim sekmesi ve 👍/👎 ile gelişir.",
    "Kurulum dosyaları imzasızdır; Windows ve Mac ilk açılışta uyarı verebilir. Windows yalnız GitHub otomasyonunda sınandı.",
]

NEXT = [
    "Gerçek pilot bina(lar) (24 ay fatura, varsa EKB) ile doğrulama ve vaka çalışması.",
    "Fatura OCR ve dağıtım şirketi veri bağlantısı; aralık (saatlik) veri desteği.",
    "BEP-TR yöntem belgesi ve gerçek EKB ile sınıf kalibrasyonu; Türkiye emsal verisi.",
    "CRREM License Partner anlaşması ya da kullanıcı içe aktarmasıyla devam; güncel dosya biçimi doğrulaması.",
    "Kod imzalama, çok kullanıcı/bulut, bağımsız güvenlik incelemesi.",
]


def table(rows, header, widths):
    out = ['<table width="100%" cellspacing="0" cellpadding="5" style="border-collapse:collapse">']
    out.append("<tr>" + "".join(f'<th align="left" width="{w}%" bgcolor="#0B3D2E" style="color:#ffffff;font-size:8.5pt">{h}</th>' for h, w in zip(header, widths)) + "</tr>")
    for i, r in enumerate(rows):
        bg = "#F4F7F6" if i % 2 else "#FFFFFF"
        out.append(f'<tr bgcolor="{bg}">' + "".join(f'<td valign="top" style="border-bottom:1px solid #D5DDDA;font-size:8.5pt">{c}</td>' for c in r) + "</tr>")
    out.append("</table>")
    return "".join(out)


parts = [f"""
<h1 style="color:#0B3D2E;font-size:22pt;margin-bottom:0">EDIFI'CE · Durum Raporu</h1>
<p style="color:#555;font-size:10pt">Sürüm {edifice.__version__} (GitHub Releases'te yayımlandı) · Hazırlanma tarihi: {date.today():%d.%m.%Y} · Bu belge neyin VAR, neyin YOK olduğunu ve nedenini dürüstçe listeler.</p>
<h2 style="color:#0B3D2E">Özet</h2>
<ul>
<li>EDIFI'CE, tek ya da birkaç binanın enerji, karbon, su ve maliyet verisini analiz eden, dönüşüm önerilerini finansal olarak değerlendiren, Türkiye'ye uyarlanmış bir <b>masaüstü uygulamasıdır</b> (Python/PySide6; macOS Apple Silicon ve Windows).</li>
<li>Kod tabanı yaklaşık {loc} satır Python, <b>{tests} otomatik test</b>, {len(SOURCES)} kaynaklı kanıt kaydı, {len(tables)} veritabanı tablosu.</li>
<li><b>Güçlü yanlar:</b> her sayı kaynak ve kanıt düzeyiyle şeffaf; yerel/gizli çalışma; yatırım karar motoru (NPV, bütçe optimizasyonu), hava normalizasyonlu M&amp;V, veri güvenilirliği skoru, yerel kendini eğiten asistan.</li>
<li><b>En büyük eksik:</b> gerçek bina referansı ve bağımsız doğrulama yok; veri girişi otomatik değil (aylık fatura); resmî belgeler (EKB, CRREM verisi gömülü, GRESB/CSRD) üretilmez ya da lisans/erişim nedeniyle yapılamaz.</li>
<li>Kanıt düzeyleri: <b>birincil</b> = resmî/orijinal belge okundu; <b>özet</b> = derleme/meta-analiz; <b>ikincil</b> = tek çalışma/vaka; <b>varsayım</b> = doğrulanamadı.</li>
</ul>
<h2 style="color:#0B3D2E">İçindekiler</h2>
<p>A. Mevcut özellikler (5 bölüm) · B. Kanıt ve varsayım kaydı · C. Olmayanlar ve nedenleri · D. Bilinen sınırlamalar · E. Önerilen sonraki adımlar</p>
<h1 style="color:#0B3D2E;font-size:17pt;page-break-before:always">A. Mevcut özellikler</h1>
"""]
for title, items in HAVE:
    parts.append(f'<h2 style="color:#0B3D2E;margin-top:14px">{title}</h2><ul>')
    parts += [f'<li style="margin-bottom:5px">{it}</li>' for it in items]
    parts.append("</ul>")
parts.append('<h1 style="color:#0B3D2E;font-size:17pt;page-break-before:always">B. Kanıt ve varsayım kaydı</h1>')
parts.append(f"<p>Hesaplarda kullanılan temel parametreler ve doğrulama düzeyleri ({len(params)} kalem; <b>{sum(1 for p in params if p[4] == 'varsayım')} tanesi varsayım</b>). Ayrıntı ve kaynakça: docs/KAYNAKCA.md ve uygulamada Raporlar › Kaynaklar ve Yöntem.</p>")
colors = {"birincil": "#0A7A53", "özet": "#2F8F6B", "ikincil": "#B7791F", "varsayım": "#C53030"}
rows = [(e(g), e(n), e(v), f'<b style="color:{colors[l]}">{l}</b>', e(note)) for g, n, v, s, l, note in params]
parts.append(table(rows, ["Grup", "Parametre", "Değer", "Düzey", "Not"], [9, 18, 18, 15, 40]))
parts.append(f"<p style='font-size:8.5pt;color:#555'>Kaynak düzeyleri (toplam {len(SOURCES)}): " + ", ".join(f"{k} {v}" for k, v in sorted(
    {l: sum(1 for s in SOURCES.values() if s['level'] == l) for l in ('birincil', 'özet', 'ikincil')}.items())) + ".</p>")
parts.append('<h1 style="color:#0B3D2E;font-size:17pt;page-break-before:always">C. Olmayanlar ve nedenleri</h1>')
parts.append("<p>Aşağıdaki kalemler uygulamada <b>yoktur ya da sınırlıdır</b>. Her biri için durumun ne olduğu, neden olmadığı ve gerçekleşmesi için neyin gerektiği yazılıdır.</p>")
parts.append(table([(f"<b>{i + 1}. {a}</b>", b, c, d) for i, (a, b, c, d) in enumerate(MISSING)],
                   ["Kalem", "Mevcut durum", "Neden yok / sınırlı", "Gerekli olan"], [22, 22, 34, 22]))
parts.append('<h1 style="color:#0B3D2E;font-size:17pt;margin-top:18px">D. Bilinen sınırlamalar</h1><ul>' + "".join(f'<li style="margin-bottom:5px">{x}</li>' for x in LIMITS) + "</ul>")
parts.append('<h1 style="color:#0B3D2E;font-size:17pt">E. Önerilen sonraki adımlar</h1><ol>' + "".join(f'<li style="margin-bottom:4px">{x}</li>' for x in NEXT) + "</ol>")
parts.append("<p style='color:#777;font-size:8pt;margin-top:16px'>Bu belge EDIFI'CE deposundaki kod, testler ve belgelerden üretilmiştir (tools/make_status_pdf.py). Resmî bir sertifika ya da denetim raporu değildir.</p>")

body = "".join(parts)
doc = QTextDocument()
font = QFont("Manrope" if "Manrope" in QFontDatabase.families() else "Helvetica", 10)
font.setWeight(QFont.Normal)
font.setStyleName("Regular")
doc.setDefaultFont(font)
doc.setDefaultStyleSheet("body{font-size:10pt;color:#1B2B27} li{margin-top:2px} h2{font-size:13pt}")
doc.setHtml(f"<html><body>{body}</body></html>")
out = root / "docs" / "EDIFICE_Durum_Raporu.pdf"
w = QPdfWriter(str(out))
w.setPageSize(QPageSize(QPageSize.A4))
w.setPageMargins(QMarginsF(16, 16, 16, 18), QPageLayout.Millimeter)
w.setTitle("EDIFI'CE Durum Raporu")
doc.print_(w)
print(out, out.stat().st_size, "bayt")
