# EDIFI'CE: Proje Notları

Kaynak: `EDIFICE_MVP.pdf` (Teknik ve Ürün Önerileri, Kısa Kapsam Notu). Bu proje TradingBot ile ilgisizdir.

## Hedef (Faz 1 MVP)
Tek bir gerçek pilot binanın verilerini alıp mevcut performansını analiz eden, dönüşüm önerileri çıkaran ve bu önerilerin enerji, karbon, CAPEX, tasarruf ve geri ödeme etkisini gösteren, çalışan bir **Python desktop uygulaması**.

## Teknoloji
- Python + PySide6 (desktop UI)
- pandas / openpyxl (Excel-CSV import)
- SQLite (MVP veri tabanı), ileride PostgreSQL
- Hesaplama motoru UI'dan ayrı, modüler Python servisleri olarak tutulur

## MVP'de olması gerekenler
- Building Overview
- Elektrik / doğalgaz / su takibi
- Enerji ve karbon KPI'ları
- Building Health Score
- Dönüşüm önerileri
- Current vs Target karşılaştırması
- CAPEX, yıllık tasarruf, geri ödeme süresi
- Basit rapor çıktısı

## Sonraki fazlara bırakılanlar (scope'a ekleme)
Gerçek zamanlı IoT, kapsamlı BMS entegrasyonu, Digital Twin/BIM, 3D görselleştirme, AI optimizasyonu, predictive maintenance, gelişmiş ESG ve finansman entegrasyonları.

## Veri akışı
- Bina bilgisi: müşteri / saha ekibi
- Elektrik, doğalgaz, su: fatura, Excel veya CSV
- HVAC, aydınlatma, bina kabuğu: saha etüdü
- Akış: import → doğrulama → veri tabanına yazma → hesap motoru

## Mimari kuralları
- Building, Utility Data, Equipment, KPI, Opportunity ve Scenario yapıları baştan ayrı tutulur.
- Ham veri, hesaplanan veri ve senaryo verisi karıştırılmaz. Böylece API, BMS, IoT, PostgreSQL ve AI katmanları sonra eklenebilir.

## Geliştirme sırası
1. Çalışan arayüz + mock veri
2. Gerçek veri girişi, Excel import, hesap motoru
3. Tek gerçek pilot bina + rapor çıktısı

Her adım çalışır halde teslim edilen küçük milestone'lara bölünür.

## Açık sorular / riskler
- **En kritik eksik:** Health Score, tasarruf oranı, dönüşüm önerisi ve ROI'nin hangi girdilerle, hangi formüllerle hesaplanacağı henüz tanımlı değil. Kod yazmadan önce netleştirilmeli.
- **En büyük risk:** Gereksiz özellik ekleyerek scope'u büyütmek.

## Çalışma kuralları
- Yanıtlar Türkçe.
- Önce hesap mantığını netleştir, sonra UI.

## Durum (Milestone 1 tamam)
Mock veriyle çalışan arayüz + hesap motoru hazır: `main.py`, `edifice/` (models, engine, service, ui), `tests/`. Çalıştırma için README. Sonra eklendi: uygulamadan Bina Ekle (bina bilgisi, 12 aylık tüketim, ekipman; `edifice/ui/building_dialog.py`, doğrulama `edifice/validation.py`) ve SQLite kaydı (`edifice/db.py`, `~/.edifice/edifice.db`). Kullanıcı Excel/CSV import istemedi, veri uygulamadan girilir. Sıradaki: gerçek pilot bina verisi, formüllerin/varsayımların netleşmesi ve düzenlenebilir ayarlar ekranı, PDF rapor.

## Tasarım
UI, kullanıcının Figma Make çıktısına ("Premium SaaS Dashboard Design", koyu tema) göre yapıldı: renkler `#070C12` zemin, `#0DDD96` yeşil, `#6366F1` indigo, `#F59E0B` amber, `#F43F5E` kırmızı; fontlar Manrope + DM Mono (yüklü değilse Menlo/Helvetica'ya düşer). Tasarım tokenları `edifice/ui/widgets.py` içinde, grafikler `edifice/ui/charts.py` içinde (özel çizim, aşağıdan yukarı yükselen animasyon). Figma'daki çoklu bina/portföy sayfaları MVP kapsamı dışında, sadece tek bina ekranları uygulandı.

## Ayarlar ve düzenleme (eklendi)
Hesap varsayımları (emisyon faktörü, tarifeler, kıyas değerleri, Health Score ağırlıkları, ekipman ömrü) ve öneri kataloğu artık SQLite'ta (`settings`, `opportunities`) ve **Ayarlar** ekranından düzenlenir (`edifice/ui/settings_page.py`). Binalar sonradan düzenlenebilir (sidebar bina kartı > "Bu binayı düzenle"). Kalan: öneri kataloğunu ekipmana göre otomatik seçme, PDF rapor, senaryo kaydı, fontları gömme.

## Rapor, uygunluk, senaryo (eklendi)
PDF rapor: `edifice/ui/report_pdf.py` (QPdfWriter, tek sayfa A4; "Rapor" butonu PDF üretir). Ekipmana göre öneri uygunluğu: `edifice/engine/relevance.py` (yüksek/orta/düşük öncelik, uygun değil, veri yok). Senaryo seçimi bina başına SQLite'ta (`scenarios`). Kalan: Manrope/DM Mono fontlarını gömmek (kullanıcı izniyle indirilecek), gerçek pilot bina verisiyle deneme.

## Excel ile bina ekleme (eklendi)
"+ Bina Ekle" önce yöntem seçtirir (`ui/add_choice.py`): formu doldur ya da Excel şablonu. `edifice/excel_io.py`: `build_template(path, example)` talimatlı/doğrulamalı .xlsx üretir (boş ya da örnek dolu), `read_workbook(path, tariffs)` okur ve `validation.build_from_inputs` ile doğrular; hatalar hücre/sayfa adıyla listelenir. Başarılıysa veri Bina Ekle penceresinde "Gözden Geçir" modunda açılır, kullanıcı kontrol edip kaydeder. Şablon yerleşimi sabittir (sayfa adları Bina/Tüketim/Ekipman, hücre konumları excel_io.py üstünde).

## Yatırımcı paketi (eklendi)
Enerji sınıfı + benchmark (`engine/rating.py`, Genel Bakış'ta sınıf skalası ve dağılım eğrisi; tahmini, resmi belge değil), finans motoru (`engine/finance.py`: NPV, IRR, indirgenmiş geri ödeme, 15 yıl reel nakit akışı; varsayımlar Ayarlar'da), bütçe simülatörü (`engine/optimizer.py` + Senaryo ekranında kaydırıcı: bütçeye göre NPV'yi maksimize eden paket otomatik seçilir). PDF'e sınıf rozeti ve NPV/IRR satırı eklendi. Fikir listesinde kalanlar: anomali yakalama, portföy görünümü, hazır demo binalar.
