"""Finansal analiz: NPV, IRR, geri ödeme ve yıllık nakit akışı (reel, enflasyondan arındırılmış değerlerle)."""
from __future__ import annotations

from dataclasses import dataclass

from ..models import Assumptions


@dataclass
class FinanceResult:
    capex: float
    years: list[int]
    cash_flows: list[float]        # yıl 0: -capex, sonrası yıllık tasarruf
    cumulative: list[float]        # kümülatif nakit akışı
    npv: float
    irr: float | None
    simple_payback: float          # kümülatif sıfırı kestiği yıl (enerji fiyat artışı dahil); sonsuz olabilir
    discounted_payback: float | None
    total_net: float               # analiz süresi sonunda toplam net kazanç (iskontosuz)


def _crossing(values: list[float]) -> float | None:
    for i in range(1, len(values)):
        if values[i - 1] < 0 <= values[i]:
            span = values[i] - values[i - 1]
            return (i - 1) + (-values[i - 1] / span if span else 0)
    return None


def _irr(flows: list[float]) -> float | None:
    if flows[0] >= 0 or sum(flows) <= 0:
        return None

    def npv(rate: float) -> float:
        return sum(f / (1 + rate) ** t for t, f in enumerate(flows))
    lo, hi = -0.95, 10.0
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(120):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def analyze(capex: float, annual_saving: float, a: Assumptions, savings_factor: float = 1.0,
            escalation: float | None = None) -> FinanceResult:
    n = int(a.horizon_years)
    esc = a.energy_escalation if escalation is None else escalation
    saving0 = annual_saving * savings_factor
    flows = [-capex] + [saving0 * ((1 + esc) * (1 - a.savings_degradation)) ** (t - 1) for t in range(1, n + 1)]
    cumulative, run = [], 0.0
    for f in flows:
        run += f
        cumulative.append(run)
    disc, drun = [], 0.0
    for t, f in enumerate(flows):
        drun += f / (1 + a.discount_rate) ** t
        disc.append(drun)
    simple = _crossing(cumulative)
    return FinanceResult(
        capex=capex, years=list(range(n + 1)), cash_flows=flows, cumulative=cumulative, npv=disc[-1],
        irr=_irr(flows), simple_payback=simple if simple is not None else float("inf"),
        discounted_payback=_crossing(disc), total_net=cumulative[-1])
