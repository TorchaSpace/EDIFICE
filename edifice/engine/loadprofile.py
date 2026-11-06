"""Saatlik/aralıklı yük verisi (akıllı sayaç CSV'si): yük profili, boşta tüketim, pik, çok zamanlı tarife karşılaştırması. UI'dan bağımsız.

Giriş: zaman damgası + değer sütunları (15 dk, 30 dk ya da saatlik). Değer kWh (aralık enerjisi) ya da kW (ortalama güç) olabilir;
sütun adında «kW» geçip «kWh» geçmiyorsa kW kabul edilir. Zaman dilimi dönüşümü yapılmaz (yerel saat varsayılır).

Çok zamanlı tarife dilimleri (T1 gündüz 06-17, T2 puant 17-22, T3 gece 22-06) ve fiyat ORANLARI varsayımdır; güncel EPDK tarifesine göre girin."""
from __future__ import annotations

import csv
import io
import re
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .. import bulk_import as bi

BANDS = {"T1": range(6, 17), "T2": range(17, 22), "T3": tuple(list(range(22, 24)) + list(range(0, 6)))}
DEFAULT_RATIOS = {"T1": 1.0, "T2": 1.5, "T3": 0.6}      # tek zamanlı birim fiyata oranlar: VARSAYIM


@dataclass
class Series:
    points: list[tuple[datetime, float]]          # (başlangıç zamanı, ortalama kW)
    step_hours: float
    warnings: list[str] = field(default_factory=list)

    @property
    def kwh(self) -> float:
        return sum(v for _, v in self.points) * self.step_hours


def _parse_dt(v) -> datetime | None:
    if isinstance(v, datetime):
        return v
    s = str(v or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M",
                "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d %H", "%d.%m.%Y %H"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def parse_interval_text(text: str) -> Series | None:
    """CSV metni -> Series. Başlık satırı beklenir. Okunamazsa None değil boş Series + uyarı döner."""
    warnings: list[str] = []
    sample = text[:4000]
    delim = max(";,\t", key=sample.count)
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    if len(rows) < 3:
        return Series([], 1.0, ["Dosyada yeterli satır yok."])
    head = [bi.norm(c) for c in rows[0]]
    t_i = next((i for i, h in enumerate(head) if re.search(r"tarih|zaman|time|date|donem|saat", h)), 0)
    v_i = next((i for i, h in enumerate(head) if i != t_i and re.search(r"kwh|kw|tuketim|enerji|guc|demand|consumption|energy|load", h)), None)
    if v_i is None:
        v_i = 1 if t_i == 0 else 0
    is_power = bool(re.search(r"\bkw\b|kw\)|\(kw|guc|demand", head[v_i])) and "kwh" not in head[v_i]
    raw, bad = [], 0
    for r in rows[1:]:
        if len(r) <= max(t_i, v_i):
            continue
        dt, val = _parse_dt(r[t_i]), bi.parse_number(r[v_i])
        if dt is None or val is None:
            bad += 1
            continue
        if val < 0:
            bad += 1
            continue
        raw.append((dt, val))
    if bad:
        warnings.append(f"{bad} satır okunamadı ya da negatifti, atlandı.")
    if len(raw) < 3:
        return Series([], 1.0, warnings + ["Geçerli zaman/değer satırı bulunamadı (başlıkta tarih-saat ve kWh ya da kW sütunu olmalı)."])
    raw.sort()
    dedup = {}
    for dt, v in raw:
        dedup[dt] = v
    raw = list(dedup.items())
    if len(raw) != len(dedup):
        warnings.append("Aynı zamana ait tekrarlar son değerle birleştirildi.")
    deltas = [(b[0] - a[0]).total_seconds() for a, b in zip(raw, raw[1:]) if b[0] > a[0]]
    step = statistics.median(deltas) / 3600 if deltas else 1.0
    if not (0.05 <= step <= 24):
        return Series([], 1.0, warnings + [f"Aralık anlaşılamadı ({step:.2f} saat)."])
    gaps = sum(1 for d in deltas if d > step * 3600 * 1.5)
    if gaps:
        warnings.append(f"{gaps} yerde veri boşluğu var (aralıktan uzun); boşluklar hesaplamada sıfır sayılmaz, atlanır.")
    pts = [(dt, v if is_power else v / step) for dt, v in raw]
    return Series(pts, step, warnings)


def parse_interval_file(path: str) -> Series:
    data = open(path, "rb").read()
    for enc in ("utf-8-sig", "cp1254"):
        try:
            return parse_interval_text(data.decode(enc))
        except UnicodeDecodeError:
            continue
    return Series([], 1.0, ["Dosya kodlaması okunamadı."])


@dataclass
class LoadReport:
    ok: bool
    note: str = ""
    days: int = 0
    kwh: float = 0.0
    peak_kw: float = 0.0
    peak_at: datetime | None = None
    avg_kw: float = 0.0
    base_kw: float = 0.0              # %5'lik dilim: boşta/temel yük
    load_factor: float = 0.0          # ortalama / pik
    base_to_peak: float = 0.0
    off_hours_share: float = 0.0      # gece (22-06) + hafta sonu tüketim payı
    weekday_profile: list[float] = field(default_factory=lambda: [0.0] * 24)
    weekend_profile: list[float] = field(default_factory=lambda: [0.0] * 24)
    band_kwh: dict = field(default_factory=dict)
    top_days: list[tuple[str, float]] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def analyze(s: Series) -> LoadReport:
    if len(s.points) < 24 / max(s.step_hours, 0.05) * 2:
        return LoadReport(False, "En az 2 günlük veri gerekir.", warnings=s.warnings)
    vals = [v for _, v in s.points]
    peak_i = max(range(len(vals)), key=vals.__getitem__)
    srt = sorted(vals)
    base = srt[int(0.05 * (len(srt) - 1))]
    avg = sum(vals) / len(vals)
    r = LoadReport(True, kwh=s.kwh, peak_kw=vals[peak_i], peak_at=s.points[peak_i][0], avg_kw=avg, base_kw=base, warnings=list(s.warnings))
    r.days = len({dt.date() for dt, _ in s.points})
    r.load_factor = avg / r.peak_kw if r.peak_kw else 0.0
    r.base_to_peak = base / r.peak_kw if r.peak_kw else 0.0
    wk, we = [[] for _ in range(24)], [[] for _ in range(24)]
    off = 0.0
    daily: dict = {}
    bands = {k: 0.0 for k in BANDS}
    for dt, v in s.points:
        (we if dt.weekday() >= 5 else wk)[dt.hour].append(v)
        e = v * s.step_hours
        daily[dt.date()] = daily.get(dt.date(), 0.0) + e
        for k, hrs in BANDS.items():
            if dt.hour in hrs:
                bands[k] += e
        if dt.weekday() >= 5 or dt.hour >= 22 or dt.hour < 6:
            off += e
    r.weekday_profile = [statistics.fmean(x) if x else 0.0 for x in wk]
    r.weekend_profile = [statistics.fmean(x) if x else 0.0 for x in we]
    r.band_kwh = bands
    r.off_hours_share = off / r.kwh if r.kwh else 0.0
    r.top_days = [(d.isoformat(), e) for d, e in sorted(daily.items(), key=lambda kv: -kv[1])[:5]]
    p95 = srt[int(0.95 * (len(srt) - 1))]
    if r.base_to_peak > 0.4:
        r.findings.append(f"Boşta/temel yük yüksek: en düşük %5'lik dilim {base:.0f} kW, pikin %{r.base_to_peak * 100:.0f}'i. Gece-hafta sonu kapanmayan HVAC, aydınlatma ya da ekipman olabilir.")
    wd_day = statistics.fmean(r.weekday_profile[8:18]) if any(r.weekday_profile) else 0
    we_day = statistics.fmean(r.weekend_profile[8:18]) if any(r.weekend_profile) else 0
    if we_day and wd_day and we_day > 0.8 * wd_day:
        r.findings.append(f"Hafta sonu gündüz yükü hafta içinin %{we_day / wd_day * 100:.0f}'i: hafta sonu çalışma programı/otomasyon gözden geçirilmeli.")
    if p95 and r.peak_kw > 1.4 * p95:
        r.findings.append(f"Pik ({r.peak_kw:.0f} kW) %95'lik dilimin ({p95:.0f} kW) %{(r.peak_kw / p95 - 1) * 100:.0f} üstünde: kısa süreli pik; kademeli devreye alma ile azaltılabilir (talep bedeli faturada ayrıca incelenmeli).")
    if r.load_factor < 0.35:
        r.findings.append(f"Yük faktörü düşük ({r.load_factor:.2f}): kurulu/çekilen güç ortalamaya göre yüksek.")
    if not r.findings:
        r.findings.append("Belirgin bir yük profili sorunu görülmedi (eşikler sağduyu değerleridir, resmî standart değil).")
    return r


@dataclass
class TariffComparison:
    single_cost: float
    tou_cost: float
    band_cost: dict
    saving: float                    # tek zamanlı - çok zamanlı (pozitif = çok zamanlı ucuz)
    shift_gain: float                # puant tüketiminin %20'si geceye kaydırılırsa ek kazanç
    ratios: dict


def compare_tariffs(rep: LoadReport, single_price: float, ratios: dict | None = None) -> TariffComparison:
    """Aynı tüketimin tek zamanlı ve çok zamanlı tarifedeki maliyeti. Çok zamanlı fiyatlar = tek zamanlı fiyat × oran (varsayım)."""
    ratios = {**DEFAULT_RATIOS, **(ratios or {})}
    single = rep.kwh * single_price
    band_cost = {k: rep.band_kwh.get(k, 0.0) * single_price * ratios[k] for k in BANDS}
    tou = sum(band_cost.values())
    moved = rep.band_kwh.get("T2", 0.0) * 0.2
    gain = moved * single_price * (ratios["T2"] - ratios["T3"])
    return TariffComparison(single, tou, band_cost, single - tou, gain, ratios)
