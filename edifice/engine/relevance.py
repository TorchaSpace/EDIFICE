"""Önerinin binanın ekipmanına uygunluğu: yaşlı/kötü durumdaki ekipman için öncelik yüksek, zaten verimli olan için düşük."""
from __future__ import annotations

from datetime import date

from ..models import Equipment

# öneri kodu -> (ekipman kategorisi, ad anahtar sözcükleri; boşsa kategorideki tüm ekipman)
MATCH = {
    "LED": ("Aydınlatma", ()),
    "CHILLER": ("HVAC", ("chiller", "soğutucu", "soğutma grubu")),
    "VFD": ("HVAC", ("fan", "pompa", "santral", "klima", "ahu")),
    "BOILER": ("HVAC", ("kazan", "boiler")),
    "ENVELOPE": ("Bina Kabuğu", ()),
}
EFFICIENT_WORDS = ("led", "yoğuşmalı", "inverter", "vfd", "sürücülü")

LABELS = {"high": "Yüksek öncelik", "medium": "Orta öncelik", "low": "Düşük öncelik",
          "none": "Uygun değil", "unknown": "Veri yok"}


def _urgency(e: Equipment, life: int, today: int) -> float:
    age = min(1.0, max(0.0, (today - e.year_installed) / max(life, 1)))
    cond = (5 - e.condition) / 4
    return 0.5 * age + 0.5 * cond


def assess(code: str, equipment: list[Equipment], life: int = 20, today: int | None = None) -> tuple[str, str]:
    """-> (fit, açıklama). fit: high | medium | low | none | unknown"""
    today = today or date.today().year
    if code not in MATCH:
        return "unknown", "Bu öneri için ekipman eşlemesi tanımlı değil"
    if not equipment:
        return "unknown", "Ekipman girilmediği için uygunluk değerlendirilemedi"
    cat, words = MATCH[code]
    group = [e for e in equipment if e.category == cat]
    if words:
        group = [e for e in group if any(w in e.name.lower() for w in words)]
    if not group:
        return "unknown", f"İlgili ekipman ({cat}) kayıtlı değil; uygunluk bilinmiyor"
    already = [e for e in group if any(w in e.name.lower() for w in EFFICIENT_WORDS) and e.condition >= 3]
    if len(already) == len(group):
        return "none", f"{already[0].name} zaten verimli görünüyor"
    worst = max(group, key=lambda e: _urgency(e, life, today))
    u = _urgency(worst, life, today)
    age = today - worst.year_installed
    detail = f"{worst.name}: {age} yaşında, durum {worst.condition}/5"
    if u >= 0.6:
        return "high", detail
    if u >= 0.35:
        return "medium", detail
    return "low", detail
