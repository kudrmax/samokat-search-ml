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
