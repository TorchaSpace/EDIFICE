# Figma tasarımı ile uygulama arasındaki farklar

Kaynak: `Premium SaaS Dashboard Design/src/App.tsx` (10 sayfa). Durum: ✅ var, 🟡 kısmen, ❌ yok.
"Veri" sütunu: ekranın gerçek veriyle yapılıp yapılamayacağı (uygulama sahte veri göstermez).

## Sayfa sayfa

| Figma sayfası | Figma'daki bileşenler | Durum | Eksik olanlar | Veri |
|---|---|---|---|---|
| Dashboard | 7 KPI, Avrupa haritası, Portfolio Score, AI Recommendations, Active Renovations, Recent Projects, Partners | ✅/🟡 | Harita, portföy skoru, öneri kartları, zaman çizelgesi ve son projeler eklendi; ortak kartları yok | gerçek (bina, proje takibi) |
| Portfolio | 4 KPI, bina kartları (görsel, durum rozeti), tablo | 🟡 | Kart ızgarası (şimdi liste), filtre/sıralama, durum rozeti, ort. enerji sınıfı ve skor KPI'ları | gerçek |
| Projects | 4 KPI (bütçe, harcanan, zamanında, riskli), tüm projeler tablosu, zaman çizelgesi (Gantt) | 🟡 | Bütçe/harcanan/riskli KPI'ları, tablo, gerçek Gantt (şimdi yıl işaretleri), proje başlangıç-bitiş | gerçek (proje takibine tarih/harcama alanı eklenirse) |
| Finance | 4 KPI, finansman karması (pasta), başvurular, ödeme planı, ROI çizgi grafiği | 🟡 | Pasta grafik, finansman araçları (kredi/hibe) kaydı, ödeme planı, ROI zaman serisi | NPV/IRR gerçek; kredi/hibe kaydı için giriş formu gerekir |
| Partners | 4 KPI, ortak kartları (puan, ülke, kategori) | ❌ | Tüm sayfa | veri girişi gerekir (firma, iş, teklif) |
| AI Assistant | 4 KPI, öneri kartları (öncelik rozetli), gerçek vs AI-optimize tüketim grafiği, bakım olayları | ✅ | Hepsi eklendi (kural tabanlı bulgular + sohbet + eğitim) | gerçek |
| Digital Twin | 142 sensörlü bina, canlı sıcaklık/elektrik/su/gaz/CO₂, sensör grafiği | ❌ | Tüm sayfa | BIM + IoT verisi gerekir (MVP dışı) |
| ESG | 4 KPI, radyal ilerleme halkaları, aylık karbon çizgisi, Karbon Yolu 2020–2030 çubuk grafiği, sertifikalar | ✅/🟡 | Radyal halkalar, karbon yolu (kullanıcı hedefi), mevzuat eşikleri eklendi; sertifika kaydı (BREEAM/LEED) yok | karbon gerçek; hedef kullanıcıdan |
| Reports | 4 KPI, rapor kütüphanesi (tür, tarih, indir) | 🟡 | Rapor listesi/geçmişi, rapor türleri (yatırımcı, karbon denetimi), toplu indirme | gerçek (üretilen raporlar kaydedilirse) |
| Settings | Profil, tercihler, güvenlik, bildirimler, API anahtarları | 🟡 | Profil/kullanıcı, bildirim tercihleri, dil/para birimi, tema; (varsayım düzenleme zaten var) | gerçek |

## Genel kabuk
- Sol alt kullanıcı kartı (şimdi bina değiştirme kartı) ❌ — kullanıcı/hesap kavramı yok.
- Üst çubuk: "Export PDF" düğmesinin üretiliyor durumu 🟡; arama ✅, bildirim ✅ (gerçek uyarılarla).
- Grafik üzerinde fare ile ipucu kutusu (ChartTip), radyal/pasta/çok eksenli grafik türleri 🟡 — çizgi/alan/çubuk var, pasta ve radyal yok.
- Giriş animasyonları ✅, kart üst ışık çizgisi ✅, koyu tema ✅, Manrope/DM Mono ✅.

## Önerilen sıra (gerçek veriyle yapılabilecekler önce)
1. Dashboard'a harita + portföy skoru + öneri/yenileme kartları (Figma ana ekranı).
2. ESG: radyal halkalar + karbon yolu (hedef girişiyle) + sertifika takibi.
3. AI sayfası: "gerçek vs optimize" grafiği + bakım tahmini + öncelik rozetli kartlar.
4. Projeler: bütçe/harcanan KPI'ları, tablo, Gantt (başlangıç-bitiş alanları).
5. Finans: pasta grafik + kredi/hibe kaydı + ROI zaman serisi.
6. Raporlar: rapor geçmişi ve türleri.
7. Ortaklar: kayıt formu + kartlar.
8. Digital Twin: ayrı faz (BIM/IoT).
