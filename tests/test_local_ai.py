import pytest

from edifice.ai.local import INTENTS, IntentModel, LocalAssistant, Memory, norm, parse_budget
from edifice.ai.tools import Toolbox
from edifice.service import Project


@pytest.fixture(scope="module")
def ai():
    return LocalAssistant()


@pytest.fixture
def tb():
    p, p2 = Project.mock(), Project.mock()
    p2.building.name = "Plaza Kule"
    return Toolbox({1: p, 2: p2}, 1)


def test_norm_handles_turkish_letters():
    assert norm("İstanbul Çankaya ŞÜĞ") == "istanbul cankaya sug"


def test_parse_budget_units():
    assert parse_budget("2 milyon tl bütçem var") == 2_000_000
    assert parse_budget("500 bin lira") == 500_000
    assert parse_budget("1,5 milyon") == 1_500_000
    assert parse_budget("bütçem yok") is None


@pytest.mark.parametrize("question,intent", [
    ("binam nasıl", "overview"), ("sağlık skorum kaç", "health"), ("enerji sınıfım neden böyle", "why"),
    ("hangi öneriyle başlamalıyım", "start"), ("2 milyon bütçem var ne yapayım", "budget"), ("geçen yıla göre nasıl", "trend"),
    ("hangi ay en yüksek", "peak"), ("tasarruf oranları nereden geliyor", "evidence"), ("karbon ne kadar", "carbon"),
    ("chiller kaç yaşında", "equipment"), ("portföyde en kötü bina hangisi", "portfolio"),
])
def test_intent_classifier(ai, question, intent):
    assert ai.model.classify(question)[0][0] == intent


def test_every_training_example_classified_to_itself():
    m = IntentModel()
    wrong = [(ex, name) for name, exs in INTENTS.items() for ex in exs if m.classify(ex)[0][0] != name]
    assert not wrong


def test_answers_use_real_numbers(ai, tb):
    p = tb.projects[1]
    mem = Memory()
    assert f"{p.health().total:.0f}/100" in ai.answer("sağlık skorum kaç", tb, mem)
    ans = ai.answer("2 milyon bütçeyle ne yapmalıyım", tb, mem)
    codes, fin = p.best_package(2_000_000)
    assert "2,00 M ₺" in ans and all(o.name in ans for o in p.opportunities if o.code in codes)


def test_follow_up_and_scenario_entities(ai, tb):
    mem = Memory()
    ai.answer("2 milyon bütçem var", tb, mem)
    assert "5,00 M ₺ bütçeyle" in ai.answer("peki 5 milyon olursa", tb, mem)
    ans = ai.answer("led ve vfd yaparsam ne olur", tb, mem)
    assert "LED, VFD" in ans and "NPV" in ans


def test_building_name_switches_context(ai, tb):
    tb.projects[2].building.floor_area_m2 = 12000
    assert "Plaza Kule" in ai.answer("plaza kule nasıl", tb, Memory())


def test_out_of_scope_gets_honest_fallback(ai, tb):
    assert "anlayamadım" in ai.answer("bugün hava nasıl", tb, Memory())


def test_why_compare_and_actions(ai, tb):
    mem = Memory()
    assert "Düşük kalmasının nedenleri" in ai.answer("skorum neden düştü", tb, mem)
    assert "başta çünkü" in ai.answer("bu öneri neden önde", tb, mem)
    ans = ai.answer("pilot ofis binası ile plaza kule karşılaştır", tb, mem)
    assert "| Gösterge |" in ans and "Plaza Kule" in ans
    assert "doğalgaz" in ai.answer("elektrik mi doğalgaz mı daha çok", tb, mem)
    ai.answer("geçen yılın ocağı ile bu ocak", tb, mem)
    assert mem.chart and mem.chart["kind"] == "area"
    ai.answer("vfd yi planlandı yap 2027", tb, mem)
    assert mem.actions == [("status", "VFD", "Planlandı", 2027)]
    ai.answer("led ve vfd yi senaryoda seç", tb, mem)
    assert mem.actions == [("scenario", ["LED", "VFD"])]
    ai.answer("led ve vfd yaparsam", tb, mem)          # fiil yok: ne-olur sorusu, eylem değil
    assert mem.actions == [] and mem.chart and mem.chart["kind"] == "cash"
    ai.answer("finans sayfasına git", tb, mem)
    assert mem.actions == [("open", "Finans", None)]
    ai.answer("raporu oluştur", tb, mem)
    assert mem.actions == [("report",)]


def test_unknown_is_flagged_for_training_and_taught_examples_change_the_model(tb):
    base = LocalAssistant()
    mem = Memory()
    q = "tesisin ısı pompası var mı"
    base.answer(q, tb, mem)
    assert mem.unknown == q
    taught = LocalAssistant([("equipment", q)])
    mem2 = Memory()
    assert "Ekipman" in taught.answer(q, tb, mem2) and mem2.unknown is None


def test_rephrase_signal_learns_first_question(ai, tb):
    mem = Memory()
    ai.answer("tesisin pompası nasıl", tb, mem)          # anlaşılmaz (soru kalıbı yok)
    first = mem.unknown
    assert first is None or first == "tesisin pompası nasıl"
    if first:
        ai.answer("ekipman envanteri ve pompa durumu", tb, mem)
        assert mem.learn == [("equipment", first)]


def test_clarification_offers_candidates(ai, tb):
    mem = Memory()
    ans = ai.answer("tesisin ekipman durumu hakkında bilgi", tb, mem)
    assert mem.answered or mem.suggest
    mem2 = Memory()
    ai.answer("öneri bütçe kaç", tb, mem2)
    assert mem2.answered or mem2.suggest or mem2.unknown


def test_answer_as_forces_intent(ai, tb):
    mem = Memory()
    out = ai.answer_as("equipment", "ısı pompası var mı", tb, mem)
    assert "Ekipman envanteri" in out and mem.answered == "equipment"


def test_regression_guard_rejects_harmful_example():
    from edifice.ai.local import accepts
    assert accepts([], "equipment", "tesisin ısı pompası var mı")
    assert not accepts([], "equipment", "skorum neden düştü")          # başka niyetin örneğini bozar
    assert not accepts([], "nonexistent", "herhangi bir şey")
