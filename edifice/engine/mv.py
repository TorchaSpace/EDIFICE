"""Ölçüm ve doğrulama (M&V, IPMVP "Option C" yaklaşımı): biten projenin gerçekleşen tasarrufunu ölçer.

Yöntem: proje öncesi aylardan hava duyarlı bir baz model kurulur (aylık tüketim = a + b·HDD + c·CDD, b,c ≥ 0); proje sonrası aylar için
"proje olmasaydı" tüketimi tahmin edilir; tahmin − gerçek = ölçülen tasarruf. Belirsizlik: model artık hatasından (RMSE) türetilir.
Yetersiz veri (öncesi < 12 ay, sonrası < 3 ay, hava verisi yok) varsa sonuç üretilmez ve nedeni söylenir."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..models import UtilityType
from .weather_norm import _fit

MIN_PRE, MIN_POST = 12, 3
CVRMSE_LIMIT = 0.15       # ASHRAE Guideline 14 aylık kalibrasyon ölçütü (varsayım olarak alındı; kaynak doğrudan okunmadı)
NMBE_LIMIT = 0.05
Z95 = 1.96


@dataclass
class MVResult:
    code: str
    name: str
    utility: str
    completed: tuple[int, int]
    ok: bool
    note: str = ""
    n_pre: int = 0
    n_post: int = 0
    cv_rmse: float = 0.0
    nmbe: float = 0.0
    predicted_kwh: float = 0.0       # proje olmasaydı (sonrası aylar)
    actual_kwh: float = 0.0
    saved_kwh: float = 0.0
    saved_pct: float = 0.0
    uncertainty_kwh: float = 0.0     # %95
    expected_kwh: float = 0.0        # öneri katalogundaki tasarruf oranından beklenen
    realization_pct: float | None = None
    significant: bool = False
    model_ok: bool = False


def _months(project, u):
    return {(r.year, r.month): r.consumption for r in project.readings if r.utility == u and r.consumption > 0}


def measure(project, dd: dict, completed: dict[str, tuple[int, int]]) -> list[MVResult]:
    """completed: öneri kodu -> (yıl, ay) (bitiş). Her biri için bir MVResult."""
    out = []
    catalog = {o.code: o for o in project.opportunities}
    for code, (y, m) in completed.items():
        o = catalog.get(code)
        if o is None:
            continue
        u = o.affects
        res = MVResult(code, o.name, u.value, (y, m), False)
        series = _months(project, u)
        pre = {k: v for k, v in series.items() if k < (y, m) and k in dd and dd[k][2] >= 27}
        post = {k: v for k, v in series.items() if k >= (y, m) and k in dd and dd[k][2] >= 27}
        res.n_pre, res.n_post = len(pre), len(post)
        if not dd:
            res.note = "Hava verisi yok (konum girin; ilk açılışta internet gerekir)."
        elif len(pre) < MIN_PRE:
            res.note = f"Proje öncesi veri yetersiz ({len(pre)} ay < {MIN_PRE}). Eski faturaları içe aktarın."
        elif len(post) < MIN_POST:
            res.note = f"Proje sonrası veri yetersiz ({len(post)} ay < {MIN_POST}); birkaç ay daha bekleyin."
        else:
            ks = sorted(pre)
            yv = np.array([pre[k] for k in ks])
            (a, b, c), r2 = _fit(yv, np.array([dd[k][0] for k in ks]), np.array([dd[k][1] for k in ks]))
            pred_pre = np.array([a + b * dd[k][0] + c * dd[k][1] for k in ks])
            dof = max(len(yv) - 3, 1)
            rmse = math.sqrt(float(((yv - pred_pre) ** 2).sum()) / dof)
            res.cv_rmse = rmse / float(yv.mean())
            res.nmbe = float((yv - pred_pre).sum()) / (dof * float(yv.mean()))
            res.model_ok = res.cv_rmse <= CVRMSE_LIMIT and abs(res.nmbe) <= NMBE_LIMIT
            pk = sorted(post)
            pred = np.array([max(a + b * dd[k][0] + c * dd[k][1], 0.0) for k in pk])
            act = np.array([post[k] for k in pk])
            res.predicted_kwh, res.actual_kwh = float(pred.sum()), float(act.sum())
            res.saved_kwh = res.predicted_kwh - res.actual_kwh
            res.saved_pct = res.saved_kwh / res.predicted_kwh if res.predicted_kwh else 0.0
            res.uncertainty_kwh = Z95 * rmse * math.sqrt(len(pk))
            res.significant = abs(res.saved_kwh) > res.uncertainty_kwh
            res.expected_kwh = res.predicted_kwh * o.saving_pct
            res.realization_pct = 100 * res.saved_kwh / res.expected_kwh if res.expected_kwh else None
            res.ok = True
            if not res.model_ok:
                res.note = f"Baz model zayıf (CV(RMSE) {res.cv_rmse:.0%}, NMBE {res.nmbe:+.1%}); sonuç yalnız yönlendiricidir."
            elif len(post) < 12:
                res.note = "Sonrası 12 aydan kısa: mevsimsel etki sonucu etkileyebilir."
        out.append(res)
    return out
