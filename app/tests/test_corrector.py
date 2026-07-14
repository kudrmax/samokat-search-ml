from pathlib import Path

import pytest

from backend.models import WordCorrection
from backend.pipeline.corrector import SymSpellCorrector

DICT_PATH = Path(__file__).resolve().parents[2] / "data" / "domain_dictionary.txt"


@pytest.fixture(scope="module")
def corrector() -> SymSpellCorrector:
    return SymSpellCorrector(DICT_PATH)


def test_fixes_simple_typo(corrector: SymSpellCorrector):
    words = corrector.correct("крсовки")
    assert words == [WordCorrection(original="крсовки", corrected="кроссовки")]


def test_splits_glued_words(corrector: SymSpellCorrector):
    words = corrector.correct("укропбатон")
    assert words == [WordCorrection(original="укропбатон", corrected="укроп батон")]


def test_keeps_multiple_words_and_marks_changes(corrector: SymSpellCorrector):
    words = corrector.correct("крсовки молоко")
    assert len(words) == 2
    assert words[0].corrected == "кроссовки"
    assert words[0].changed is True
    assert words[1].original == "молоко"
    assert words[1].changed is False
