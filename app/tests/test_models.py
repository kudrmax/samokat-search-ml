import pytest
from pydantic import ValidationError

from backend.models import CorrectRequest, CorrectResponse, WordCorrection


def test_word_correction_changed_true_when_differs():
    wc = WordCorrection(original="кросчовки", corrected="кроссовки")
    assert wc.changed is True


def test_word_correction_changed_false_when_same():
    wc = WordCorrection(original="молоко", corrected="молоко")
    assert wc.changed is False


def test_word_correction_changed_in_dump():
    wc = WordCorrection(original="кросчовки", corrected="кроссовки")
    assert wc.model_dump()["changed"] is True


def test_correct_request_rejects_empty_query():
    with pytest.raises(ValidationError):
        CorrectRequest(query="")


def test_correct_response_holds_words():
    resp = CorrectResponse(
        original="кросчовки",
        corrected="кроссовки",
        words=[WordCorrection(original="кросчовки", corrected="кроссовки")],
    )
    assert resp.words[0].corrected == "кроссовки"


def test_category_score_fields():
    from backend.models import CategoryScore

    cs = CategoryScore(name="безалкогольные напитки", score=1.0)
    assert cs.name == "безалкогольные напитки"
    assert cs.score == 1.0


def test_analyze_response_holds_categories():
    from backend.models import AnalyzeResponse, CategoryScore, WordCorrection

    resp = AnalyzeResponse(
        original="кола",
        corrected="кола",
        words=[WordCorrection(original="кола", corrected="кола")],
        categories=[CategoryScore(name="безалкогольные напитки", score=1.0)],
    )
    assert resp.categories[0].name == "безалкогольные напитки"
    assert resp.words[0].changed is False
