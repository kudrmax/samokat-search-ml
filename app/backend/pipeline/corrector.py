from collections import Counter
from pathlib import Path
from typing import Protocol

import marisa_trie
from symspellpy import SymSpell, Verbosity

from backend.models import WordCorrection

# --- глобальное состояние корректора (заполняется init_corrector) ---
word_freq: Counter = Counter()
dictionary: set[str] = set()
trie: marisa_trie.Trie | None = None
sym_spell: SymSpell | None = None

DISTANCE_PENALTY = 10


def init_corrector(dict_path: Path) -> None:
    """Однократная загрузка словаря, trie и SymSpell в глобальное состояние.

    Код перенесён из ispravlator.ipynb (в ноутбуке был на уровне модуля).
    """
    global word_freq, dictionary, trie, sym_spell

    word_freq = Counter()
    with open(dict_path, encoding="utf-8") as f:
        for line in f:
            term, _, count = line.rpartition(" ")
            if term:
                word_freq[term] = int(count)

    dictionary = set(word_freq)
    trie = marisa_trie.Trie(dictionary)

    sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
    sym_spell.load_dictionary(str(dict_path), 0, 1, separator=' ', encoding='utf-8')


# --- функции-исправлятор: ДОСЛОВНО из ispravlator.ipynb, НЕ МЕНЯТЬ ---

def correct_word_prefix(word, max_edit_distance=2):
    if word in dictionary:
        return word

    if len(word) >= 2:
        completions = trie.keys(word)
        if completions:
            return max(completions, key=lambda w: word_freq.get(w, 0))

    candidates = sym_spell.lookup(word, Verbosity.ALL, max_edit_distance=max_edit_distance)
    if candidates:
        best = max(candidates, key=lambda s: s.count / (DISTANCE_PENALTY ** s.distance))
        return best.term

    segmentation = sym_spell.word_segmentation(word, max_edit_distance=max_edit_distance)
    parts = segmentation.corrected_string.split()
    if (
        len(parts) > 1
        and all(p in dictionary for p in parts)
        and segmentation.distance_sum <= max_edit_distance
        and all(word_freq.get(p, 0) >= 3 for p in parts)
    ):
        return segmentation.corrected_string

    return word


def correct_query_prefix(query, max_edit_distance=2):
    query = query.strip()
    words = query.split()
    return ' '.join(correct_word_prefix(w, max_edit_distance) for w in words)


# --- удобный интерфейс поверх присланного кода ---

class TypoCorrector(Protocol):
    def correct(self, query: str) -> list[WordCorrection]:
        ...


class SymSpellCorrector:
    """Адаптер: инициализирует корректор и отдаёт пословный маппинг.

    Логику исправления НЕ меняет — переиспользует correct_word_prefix
    по каждому слову (ровно как correct_query_prefix внутри),
    сохраняя соответствие исходное слово -> исправление для подсветки.
    """

    def __init__(self, dict_path: Path) -> None:
        init_corrector(dict_path)

    def correct(self, query: str) -> list[WordCorrection]:
        words = query.strip().split()
        return [
            WordCorrection(original=word, corrected=correct_word_prefix(word))
            for word in words
        ]
