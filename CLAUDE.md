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
Mock veriyle çalışan arayüz + hesap motoru hazır: `main.py`, `edifice/` (models, engine, service, ui), `tests/`. Çalıştırma için README. Sıradaki: Excel/CSV import + doğrulama, SQLite, gerçek pilot bina verisi, formüllerin netleştirilmesi.
