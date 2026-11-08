"""Teşvik bulucu: eşleştirme, kapsam uyarısı, hibe uygulaması (çift sayım yok, tavan, kredi CAPEX'i düşürmez), Store kaydı."""
import pytest

from edifice.db import Store
from edifice.engine.incentives import CATALOG, Terms, apply_grants, find_matches
from edifice.service import Project


def test_catalog_has_no_default_numbers_and_all_flagged():
    assert all(p.level == "doğrulanmadı" and p.url.startswith("http") for p in CATALOG)


def test_matching_and_scope_warning():
    ms = {m.program.code: m for m in find_matches(["LED", "GES"], "Ofis")}
    assert ms["VAP"].in_scope is False and "kapsam dışı" in ms["VAP"].why
    assert ms["LISANSSIZ_GES"].measures == ["GES"] and ms["YESIL_BINA_KONUT"].in_scope is False
    assert {m.program.code for m in find_matches(["LED"], "Konut")} >= {"YESIL_BINA_KONUT"}
    assert find_matches(["XYZ"], "Ofis") == []


def test_no_terms_means_no_discount():
    ms = find_matches(["LED", "VFD"], "Sanayi")
    r = apply_grants({"LED": 100.0, "VFD": 50.0}, ms, {})
    assert r.grant_total == 0 and r.capex_after == 150.0 and r.per_program == {}


def test_grant_applied_cap_and_scope():
    ms = find_matches(["LED", "VFD"], "Sanayi")
    r = apply_grants({"LED": 100.0, "VFD": 50.0}, ms, {"VAP": Terms(0.3, None, True)})
    assert r.grant_total == pytest.approx(45.0) and r.capex_after == pytest.approx(105.0) and r.note.startswith("Oranlar kullanıcı")
    r = apply_grants({"LED": 100.0, "VFD": 50.0}, ms, {"VAP": Terms(0.3, 10.0, False)})
    assert r.grant_total == 10.0 and "doğrulanmadı" in r.note
    ofis = find_matches(["LED"], "Ofis")                    # VAP ofiste kapsam dışı: oran girilse de uygulanmaz
    assert apply_grants({"LED": 100.0}, ofis, {"VAP": Terms(0.3)}).grant_total == 0


def test_no_double_funding_across_programs():
    ms = find_matches(["LED"], "Sanayi")
    r = apply_grants({"LED": 100.0}, ms, {"VAP": Terms(0.5), "KOSGEB": Terms(0.5)})
    assert r.capex_after == pytest.approx(25.0) and r.grant_total == pytest.approx(75.0)   # 50 + kalanın %50'si, 100'ü aşmaz


def test_loan_does_not_reduce_capex():
    ms = find_matches(["LED"], "Ofis")
    r = apply_grants({"LED": 100.0}, ms, {"YESIL_KREDI": Terms(0.9)})
    assert r.capex_after == 100.0


def test_store_roundtrip_and_project_finance(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    st.save_incentive_terms("KOSGEB", 0.25, 500000.0, True)
    t = st.load_incentive_terms()
    assert t["KOSGEB"] == Terms(0.25, 500000.0, True)
    p = Project.mock()
    codes = [o.code for o in p.opportunities][:3]
    f0, g0, _ = p.finance_with_grants(codes, {})
    f1, g1, _ = p.finance_with_grants(codes, {"KOSGEB": Terms(0.25, None, True), "KALKINMA_AJANS": Terms(0.0)})
    assert g0.grant_total == 0 and g1.grant_total > 0 and f1.npv > f0.npv and f1.capex < f0.capex
