# EDIFI'CE

Tek pilot bina için enerji, karbon ve dönüşüm analizi yapan Python masaüstü uygulaması (Faz 1 MVP). Kapsam: `EDIFICE_MVP.pdf`, proje notları: `CLAUDE.md`.

## Çalıştırma
```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
.venv/bin/python -m pytest
```

## Kullanım
Sağ üstteki **+ Bina Ekle** ile bina bilgisi, 12 aylık tüketim (Excel'den yapıştırılabilir) ve ekipmanlar girilir. Veriler `~/.edifice/edifice.db` (SQLite) içinde saklanır; sol alttaki bina kartından binalar arasında geçilir. İlk açılışta bir demo bina gelir.

## Yapı
- `edifice/models.py`: ham veri, varsayım, hesaplanan veri ve senaryo yapıları
- `edifice/engine/`: UI'dan bağımsız hesaplar (KPI, Health Score, öneriler/senaryo)
- `edifice/service.py`: UI ile motor arasındaki tek giriş
- `edifice/ui/`: PySide6 ekranları
- `edifice/mock_data.py`: Gerçek veri gelene kadar mock pilot bina

Not: Health Score ağırlıkları, kıyas değerleri, emisyon faktörleri ve tasarruf oranları varsayımdır; pilot bina verisiyle doğrulanmalı.

## Uygulama ikonu
Proje klasöründeki `EDIFICE.app` çift tıklayınca uygulamayı açar (önce yukarıdaki kurulum yapılmış olmalı). Masaüstüne kısayol için `EDIFICE.app`'i Option+Cmd ile sürükleyip alias oluşturun. İkonu/başlatıcıyı yeniden üretmek için `tools/make_app.sh`.

## Kurulum dosyaları (Windows ve Mac)
- **macOS (Apple Silicon):** `EDIFICE-<sürüm>-macOS-arm64.dmg`: aç, EDIFICE'yi Applications'a sürükle. İmzasız olduğu için ilk açılışta sağ tık > Aç demek gerekir.
- **Windows (64 bit):** `EDIFICE-Setup-<sürüm>.exe` (kurulum sihirbazı) ya da `...-portable.zip`. İlk açılışta SmartScreen uyarısı çıkarsa "Ek bilgi > Yine de çalıştır".
- Üretim: Mac'te `packaging/build_mac.sh`; Windows'ta `packaging\build_windows.bat`; ikisi birden GitHub Actions ile (`.github/workflows/build.yml`): `v*` etiketi (örn. `git tag v1.0.1 && git push --tags`) atılınca testler çalışır, Windows + Mac dosyaları üretilir ve Releases sayfasına yüklenir.
