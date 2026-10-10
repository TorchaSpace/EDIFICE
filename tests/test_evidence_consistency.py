"""Kanıt kaydının iç tutarlılığı: her öneri kaynaklara bağlı, aralıklar mantıklı, belge güncel."""
from pathlib import Path

from edifice import mock_data
from edifice.evidence import SOURCES, render_markdown
from edifice.models import Assumptions

LEVELS = {"birincil", "özet", "ikincil", "varsayım"}


def test_every_opportunity_is_traceable_and_ranges_are_sane():
    for o in mock_data.opportunities():
        assert o.evidence_level in LEVELS, o.code
        assert o.basis.strip(), f"{o.code}: dayanak açıklaması yok"
        if o.evidence_level != "varsayım":
            assert o.evidence, f"{o.code}: kaynak anahtarı yok"
        for key in o.evidence:
            assert key in SOURCES, f"{o.code}: bilinmeyen kaynak {key}"
        assert o.saving_low is not None and o.saving_high is not None
        assert 0 < o.saving_low <= o.saving_pct <= o.saving_high <= 0.9, o.code


def test_every_source_has_level_citation_and_https_link():
    for key, src in SOURCES.items():
        assert src["level"] in LEVELS, key
        assert src["cite"].strip() and src["note"].strip(), key
        assert src["url"].startswith("https://"), f"{key}: bağlantı https değil"


def test_kaynakca_document_is_up_to_date():
    doc = Path(__file__).resolve().parent.parent / "docs" / "KAYNAKCA.md"
    assert doc.read_text(encoding="utf-8").strip() == render_markdown(Assumptions()).strip(), \
        "docs/KAYNAKCA.md eski: python tools/make_docs.py çalıştırın"
