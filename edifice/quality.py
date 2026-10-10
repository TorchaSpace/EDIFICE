"""Veri kalitesi ve güvenilirlik değerlendirmesi (UI'dan bağımsız).

Her bina için 0-100 bir "veri güvenilirliği" skoru ve nedenleri üretir. Skor, girilen verinin eksikliğini, iç tutarlılığını
ve makul aralıkları kontrol eder; hesapların doğruluğunu değil, girdilerin ne kadar güvenilir olduğunu söyler.
Eşikler fiziksel/işletme mantığına dayanan sağduyu sınırlarıdır (resmî bir standart değildir) ve aşağıda isimlendirilmiştir."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from statistics import median

from .models import Building, UtilityType
from .service import Project

# --- sağduyu sınırları (doğrulanmış standart değil; bu yüzden sabit olarak görünür) ---
EUI_RANGE = (15.0, 900.0)              # kWh/m²·yıl: bunun dışı büyük olasılıkla alan ya da birim hatası
AREA_PER_FLOOR = (30.0, 150_000.0)     # m² / kat
AREA_PER_OCCUPANT = (2.0, 600.0)       # m² / kişi
OUTLIER_HIGH, OUTLIER_LOW = 3.0, 0.25  # aylık değer / medyan
UNIT_ERROR_RATIO = 10.0               # aylık değer / medyan: bu kadar büyükse büyük olasılıkla birim ya da yazım hatası
PRICE_BAND = (0.3, 3.0)                # fatura birim fiyatı / varsayılan tarife
TARIFF_MATCH = 0.005                   # bu kadar yakınsa maliyet "tarifeden türetilmiş" sayılır

SEVERITY_POINTS = {"kritik": 22, "uyarı": 8, "bilgi": 3}


@dataclass
class Issue:
    severity: str          # kritik | uyarı | bilgi
    area: str              # Tüketim | Maliyet | Bina | Ekipman | Kapsam
    message: str


@dataclass
class QualityReport:
    score: float
    level: str             # Yüksek | Orta | Düşük
    issues: list[Issue] = field(default_factory=list)
    completeness: float = 1.0   # son iki yılın 36 elektrik/gaz/su ayından dolu olan oran

    @property
    def color_key(self) -> str:
        return {"Yüksek": "good", "Orta": "warn", "Düşük": "bad"}[self.level]


def _level(score: float) -> str:
    return "Yüksek" if score >= 85 else "Orta" if score >= 65 else "Düşük"


def assess(project: Project) -> QualityReport:
    b: Building = project.building
    issues: list[Issue] = []
    add = lambda sev, area, msg: issues.append(Issue(sev, area, msg))
    today = date.today().year

    # ---- bina bilgisi
    if b.floor_area_m2 <= 0:
        add("kritik", "Bina", "Brüt alan sıfır ya da eksik: tüm yoğunluk (EUI) hesapları anlamsız.")
    else:
        per_floor = b.floor_area_m2 / max(b.floors, 1)
        if not AREA_PER_FLOOR[0] <= per_floor <= AREA_PER_FLOOR[1]:
            add("uyarı", "Bina", f"Kat başına alan {per_floor:,.0f} m²; alan ya da kat sayısı hatalı olabilir.".replace(",", "."))
        if b.occupants > 0:
            per_person = b.floor_area_m2 / b.occupants
            if not AREA_PER_OCCUPANT[0] <= per_person <= AREA_PER_OCCUPANT[1]:
                add("bilgi", "Bina", f"Kişi başına {per_person:.0f} m² düşüyor; kullanıcı sayısını kontrol edin.")
    if not 1800 <= b.year_built <= today:
        add("uyarı", "Bina", f"Yapım yılı ({b.year_built}) olağan dışı.")

    # ---- tüketim eksikliği ve aykırı değerler
    year, prev = project.year, project.previous_year()
    years = [year] + ([prev] if prev is not None else [])
    filled = total = 0
    for u, label in ((UtilityType.ELECTRICITY, "Elektrik"), (UtilityType.GAS, "Doğalgaz"), (UtilityType.WATER, "Su")):
        for y in years:
            vals = project.monthly(y, u)
            total += 12
            nz = [v for v in vals if v > 0]
            filled += len(nz)
            if u != UtilityType.GAS and not nz:
                add("kritik" if y == year else "uyarı", "Tüketim", f"{label}: {y} yılında hiç veri yok.")
                continue
            if u == UtilityType.GAS and not nz:
                add("bilgi", "Tüketim", f"Doğalgaz: {y} yılında tüketim yok (doğalgaz kullanılmıyorsa sorun değil).")
                continue
            missing = [m + 1 for m, v in enumerate(vals) if v <= 0]
            # ısıtma yazlık değilse boş aylar normal olabilir: gaz için yalnız 4+ ay hatalı sayılır
            if missing and (u != UtilityType.GAS or len(missing) <= 8 and len(nz) < 4):
                add("uyarı", "Tüketim", f"{label} {y}: {len(missing)} ay boş ({', '.join(map(str, missing))}).")
            if len(nz) >= 6:
                med = median(nz)
                for m, v in enumerate(vals):
                    if v > 0 and med > 0 and (v > OUTLIER_HIGH * med or v < OUTLIER_LOW * med) and u != UtilityType.GAS:
                        extreme = v > UNIT_ERROR_RATIO * med
                        add("kritik" if extreme else "uyarı", "Tüketim",
                            f"{label} {y}, {m + 1}. ay: {v:,.0f} (medyanın {v / med:.1f} katı); "
                            f"{'olası birim hatası (kWh/MWh) ya da fazladan rakam' if extreme else 'girişi kontrol edin'}.".replace(",", "."))
            if any(v < 0 for v in vals):
                add("kritik", "Tüketim", f"{label} {y}: negatif değer var.")
    completeness = filled / total if total else 0.0
    if prev is None:
        add("bilgi", "Kapsam", "Tek yıllık veri var: yıllık değişim, anomali ve trend analizleri yapılamaz.")

    # ---- maliyet tutarlılığı
    tariffs = project.assumptions.default_tariffs
    for u, label in ((UtilityType.ELECTRICITY, "Elektrik"), (UtilityType.GAS, "Doğalgaz"), (UtilityType.WATER, "Su")):
        rs = [r for r in project.readings if r.utility == u and r.year == year and r.consumption > 0]
        if not rs:
            continue
        ratios = [(r.cost / r.consumption) / tariffs[u] for r in rs if tariffs.get(u)]
        if ratios and all(abs(x - 1) <= TARIFF_MATCH for x in ratios):
            add("bilgi", "Maliyet", f"{label}: tüm aylarda fiyat varsayılan tarifeyle birebir aynı; gerçek fatura tutarı girilmemiş olabilir (maliyet/NPV tahmindir).")
        elif ratios and (median(ratios) < PRICE_BAND[0] or median(ratios) > PRICE_BAND[1]):
            add("uyarı", "Maliyet", f"{label}: ortalama birim fiyat varsayılan tarifenin {median(ratios):.1f} katı; tutar ya da birim hatalı olabilir.")
        zero_cost = sum(1 for r in rs if r.cost <= 0)
        if zero_cost:
            add("uyarı", "Maliyet", f"{label} {year}: {zero_cost} ayda tüketim var ama tutar sıfır.")

    # ---- yoğunluk makullüğü
    if b.floor_area_m2 > 0:
        eui = project.kpis().eui_kwh_m2
        if eui > 0 and not EUI_RANGE[0] <= eui <= EUI_RANGE[1]:
            add("kritik", "Tüketim", f"EUI {eui:,.0f} kWh/m²·yıl makul aralığın ({EUI_RANGE[0]:.0f}–{EUI_RANGE[1]:.0f}) dışında: alan, birim (kWh/MWh) ya da tüketim hatalı olabilir.".replace(",", "."))

    # ---- ekipman
    if not project.equipment:
        add("uyarı", "Ekipman", "Ekipman girilmemiş: öneri uygunluğu ve Health Score'un ekipman bileşeni varsayılan değere düşer.")
    else:
        cats = {e.category for e in project.equipment}
        for need in ("HVAC", "Aydınlatma", "Bina Kabuğu"):
            if need not in cats:
                add("bilgi", "Ekipman", f"{need} kategorisinde ekipman yok; ilgili öneriler “veri yok” kalır.")
        for e in project.equipment:
            if e.year_installed > today:
                add("kritik", "Ekipman", f"{e.name}: kurulum yılı ({e.year_installed}) gelecekte.")
            elif e.year_installed < 1900:
                add("uyarı", "Ekipman", f"{e.name}: kurulum yılı ({e.year_installed}) olağan dışı.")
            if not 1 <= e.condition <= 5:
                add("uyarı", "Ekipman", f"{e.name}: durum puanı 1-5 dışında.")
        old = [e for e in project.equipment if e.year_installed < b.year_built - 5 and 1900 <= e.year_installed]
        for e in old:
            add("bilgi", "Ekipman", f"{e.name}: kurulum yılı bina yapım yılından ({b.year_built}) önce; taşınmış ekipman değilse kontrol edin.")

    score = max(0.0, 100.0 - sum(SEVERITY_POINTS[i.severity] for i in issues))
    # eksiklik doğrudan puan düşürür (son iki yılın 36 aylık verisinin doluluğu)
    score = max(0.0, score - 30.0 * max(0.0, 0.85 - completeness) / 0.85) if completeness < 0.85 else score
    order = {"kritik": 0, "uyarı": 1, "bilgi": 2}
    issues.sort(key=lambda i: order[i.severity])
    return QualityReport(round(score, 0), _level(score), issues, completeness)
