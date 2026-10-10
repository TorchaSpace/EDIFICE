import json

import pytest

from edifice import solar
from edifice.engine.solar_sizing import SELF_MATCH, evaluate, max_kwp, size_for_best_npv
from edifice.models import Assumptions

YIELD = [65, 83, 116, 134, 143, 151, 170, 166, 147, 120, 99, 72]      # Ankara, kWh/kWp (PVGIS örneği)
FLAT = [60000.0] * 12
A = Assumptions()


def test_parse_pvgis_and_rejects_garbage():
    payload = {"outputs": {"monthly": {"fixed": [{"month": m + 1, "E_m": v} for m, v in enumerate(YIELD)]}}}
    assert solar.parse_pvgis(json.dumps(payload).encode()) == [float(v) for v in YIELD]
    assert solar.parse_pvgis(b"nope") is None and solar.parse_pvgis(b'{"outputs": {}}') is None


def test_energy_balance_and_scaling():
    p = evaluate(100, YIELD, FLAT, 4.0, A)
    assert p.production_kwh == pytest.approx(100 * sum(YIELD))
    assert p.self_kwh + p.export_kwh == pytest.approx(p.production_kwh)
    assert p.self_kwh <= p.production_kwh * 1.0001 and p.self_kwh <= sum(FLAT) * SELF_MATCH + 1e-6
    assert p.saving == pytest.approx(p.self_kwh * 4.0)               # export 0 varsayımı
    assert p.coverage_pct == pytest.approx(100 * p.self_kwh / sum(FLAT))
    assert p.carbon_avoided_kg == pytest.approx(p.self_kwh * A.emission_factor_kg_per_kwh[next(iter(A.emission_factor_kg_per_kwh))]) or p.carbon_avoided_kg > 0


def test_self_consumption_saturates_when_oversized():
    small, big = evaluate(20, YIELD, FLAT, 4.0, A), evaluate(2000, YIELD, FLAT, 4.0, A)
    assert big.self_kwh <= sum(FLAT) * SELF_MATCH + 1e-6
    assert big.self_kwh / big.production_kwh < small.self_kwh / small.production_kwh        # büyüdükçe öz tüketim oranı düşer


def test_best_size_is_interior_and_npv_maximal():
    best, sweep = size_for_best_npv(YIELD, FLAT, 4.0, A, kwp_cap=2000)
    assert best is not None and best.finance.npv == max(s.finance.npv for s in sweep)
    assert 5 < best.kwp < 2000
    none, _ = size_for_best_npv(YIELD, FLAT, 0.05, A, kwp_cap=100)          # çok ucuz elektrik: yatırım kendini ödemez
    assert none is None


def test_roof_limit():
    assert max_kwp(6000, 8) == pytest.approx(6000 / 8 * 0.6 / 6.0)
    assert max_kwp(0, 1) == 0


def test_assistant_answers_solar_and_price():
    from edifice.ai.local import LocalAssistant, Memory
    from edifice.ai.tools import Toolbox
    from edifice.service import Project
    p = Project.mock()
    tb = Toolbox({1: p}, 1)
    ai = LocalAssistant()
    assert "güneş verisi yok" in ai.answer("çatıya güneş paneli kurulur mu", tb, Memory())
    tb.solar[1] = YIELD
    ans = ai.answer("ges geri ödeme süresi kaç", tb, Memory())
    assert "kWp" in ans and "NPV" in ans and "varsayım" in ans
    pr = ai.answer("fazla ödeme var mı", tb, Memory())
    assert "Birim fiyat analizi" in pr
