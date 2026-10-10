# EDIFI'CE

Binalar için enerji, karbon, su ve maliyet analizi; dönüşüm önerilerinin finansal değerlendirmesi; ESG ve iklim göstergeleri. Türkiye'ye uyarlanmış, **yerel çalışan** bir masaüstü uygulaması (Python, PySide6; macOS Apple Silicon ve Windows). Verileriniz bilgisayarınızda kalır.

> Enerji sınıfı yaklaşık bir göstergedir, resmî Enerji Kimlik Belgesi değildir. Hesaplar karar desteğidir, yatırım tavsiyesi değildir.

## Neler var
- **Veri girişi:** Bina Ekle formu, Excel şablonu, toplu CSV/Excel tüketim içe aktarma, ülke/il/ilçe adres otomatik tamamlama (konum otomatik).
- **Analiz:** KPI'lar, Health Score, BEP-TR ölçeğinde (gösterge) enerji sınıfı, 5 dönüşüm önerisi (kanıt düzeyli tasarruf aralıkları), senaryo, NPV/IRR/duyarlılık, bütçeye göre en iyi paket.
- **Güvenilirlik:** her sayı kaynak ve kanıt düzeyiyle; veri güvenilirliği skoru; hava normalizasyonu (derece-gün); gerçekleşen tasarruf ölçümü (M&V).
- **İklim ve enerji:** canlı hava + 7 günlük tahmin ve enerji öngörüsü; çatı GES analizi (PVGIS); birim fiyat analizi.
- **Karbon ve ESG:** karbon hedefi ve yol aşımı; kullanıcının içe aktardığı resmî CRREM yolları (veri uygulamada yoktur, lisans); mevzuat eşikleri.
- **Portföy:** harita, toplu kartlar, bina karşılaştırması.
- **Yerel yapay zeka asistanı:** internet/API gerektirmez; sorular, komutlar, grafikler; 👍/👎 ve Eğitim sekmesiyle kendini geliştirir.
- **Raporlar:** PDF yatırımcı raporu; Excel: ESG veri paketi, EKB hazırlık sayfası, portföy özeti.
- **Güvenlik:** günlük otomatik yedek, açılışta bütünlük denetimi, JSON dışa aktarma, hata günlüğü.

Ayrıntılı özellik ve eksik listesi: `docs/EDIFICE_Durum_Raporu.pdf`. Piyasa karşılaştırması: `docs/PIYASA_FARKLARI.md`. Kaynakça: `docs/KAYNAKCA.md`. Resmî veri girişimleri: `docs/RESMI_VERI_DURUMU.md`.

## Çalıştırma (geliştirici)
```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
.venv/bin/python -m pytest
.venv/bin/python main.py --selftest   # paket sonrası hızlı sağlık kontrolü
```
İlk açılışta bir demo bina gelir (sentetik veri; sayılar anlam taşımaz). Veriler `~/.edifice/edifice.db` (SQLite) içindedir; yedekler `~/.edifice/backups`.

## İnternet kullanımı
Harita karoları, adres önerileri, geçmiş/canlı hava ve güneş verisi ilk kullanımda internetten indirilir ve önbelleğe alınır; çevrimdışıyken son veri gösterilir. Hiçbiri API anahtarı istemez.
- Hava: [Open-Meteo.com](https://open-meteo.com) (CC BY 4.0, **ücretsiz plan ticari olmayan kullanım içindir**; ticari dağıtımda ücretli plan ya da kendi barındırma gerekir: `edifice/weather.py` içindeki adresler).
- Harita/adres: © OpenStreetMap katkıda bulunanlar, Photon. Güneş: PVGIS (AB JRC).
- CRREM: kullanım koşulları ticari yazılıma gömmeyi yasakladığı için veri uygulamada yoktur; `https://crrem.org/library/pathways-datasets/` adresinden kendiniz indirip içe aktarın.

## Yapı
- `edifice/models.py`, `edifice/service.py`: veri yapıları ve UI ile motor arasındaki tek giriş
- `edifice/engine/`: UI'dan bağımsız hesaplar (KPI, health, rating, finans, optimizasyon, hava, M&V, GES, fiyat, yol aşımı, öngörü)
- `edifice/ai/`: yerel asistan (niyet sınıflandırıcı, araçlar)
- `edifice/ui/`: PySide6 ekranları; `edifice/db.py`: SQLite; `edifice/safety.py`: yedek/kurtarma/günlük
- `edifice/evidence.py`: kaynak ve kanıt kaydı (`tools/make_docs.py` ile `docs/KAYNAKCA.md`)

## Kurulum dosyaları (Windows ve Mac)
- **macOS (Apple Silicon):** `EDIFICE-<sürüm>-macOS-arm64.dmg`: aç, EDIFICE'yi Applications'a sürükle. İmzasız olduğu için ilk açılışta sağ tık > Aç gerekir.
- **Windows (64 bit):** `EDIFICE-Setup-<sürüm>.exe` ya da `...-portable.zip`. SmartScreen uyarısında "Ek bilgi > Yine de çalıştır".
- Üretim: `packaging/build_mac.sh`, `packaging\build_windows.bat`; ya da `v*` etiketi atınca GitHub Actions (`.github/workflows/build.yml`) testleri çalıştırır, paketler ve Release'e yükler.

## Yazı tipleri
`edifice/assets/fonts/` içinde Manrope ve DM Mono (SIL Open Font License 1.1; lisans metinleri aynı klasörde).
