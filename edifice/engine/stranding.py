"""Yol aşımı ("stranded asset") analizi: binanın öngörülen yoğunluğu bir hedef/CRREM yolunu hangi yıl aşıyor?

Öngörü = bugünkü yoğunluk − planlı projelerin kümülatif tasarrufu (aynı birimde). Karbon ölçütünde isteğe bağlı olarak elektrik payına, seçilen
(vekil) ülkenin şebeke emisyon eğrisinin göreli düşüşü uygulanır; bu bir MODEL VARSAYIMIDIR (Türkiye için resmî CRREM eğrisi yoktur)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Stranding:
    years: list[int] = field(default_factory=list)
    projected: list[float] = field(default_factory=list)
    pathway: list[float] = field(default_factory=list)
    stranded_year: int | None = None      # ilk aşım yılı; None = analiz ufkunda aşmıyor
    excess_total: float = 0.0             # ufuk boyunca yolun üstündeki toplam fazla (birim × yıl)
    gap_now: float = 0.0                  # bugünkü yoğunluk − bugünkü yol
    note: str = ""


def analyze(pathway: dict[int, float], base_year: int, current: float, savings_by_year: dict[int, float] | None = None,
            elec_part: float = 0.0, grid_scale: dict[int, float] | None = None, horizon: int = 2050) -> Stranding:
    out = Stranding()
    if not pathway:
        out.note = "Seçilen yol için veri yok."
        return out
    savings = savings_by_year or {}
    years = [y for y in sorted(pathway) if base_year <= y <= horizon]
    if not years:
        out.note = f"Yol {base_year} yılını kapsamıyor."
        return out
    cum = 0.0
    for y in range(base_year, years[0]):
        cum += savings.get(y, 0.0)
    for y in years:
        cum += savings.get(y, 0.0)
        scale = (grid_scale or {}).get(y, 1.0)
        proj = max(0.0, (current - elec_part) + elec_part * scale - cum)
        out.years.append(y)
        out.projected.append(proj)
        out.pathway.append(pathway[y])
        if proj > pathway[y] + 1e-9:
            out.excess_total += proj - pathway[y]
            if out.stranded_year is None:
                out.stranded_year = y
    out.gap_now = current - pathway[years[0]]
    return out
