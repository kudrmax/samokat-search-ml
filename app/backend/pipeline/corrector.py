import re
from collections import Counter
from pathlib import Path
from typing import Protocol

import marisa_trie
import pymorphy3
from symspellpy import SymSpell, Verbosity

from backend.models import WordCorrection

# --- глобальное состояние корректора (заполняется init_corrector) ---
word_freq: Counter = Counter()
dictionary: set[str] = set()
trie: marisa_trie.Trie | None = None
sym_spell: SymSpell | None = None
morph: pymorphy3.MorphAnalyzer | None = None

DISTANCE_PENALTY = 10
LATIN_RE = re.compile(r"^[a-zA-Z]+$")


def init_corrector(dict_path: Path) -> None:
    """Однократная загрузка словаря, trie, SymSpell и морфоанализатора.

    Код перенесён из typos/typo_corrector_standalone.py.
    """
    global word_freq, dictionary, trie, sym_spell, morph

    word_freq = Counter()
    with open(dict_path, encoding="utf-8") as f:
        for line in f:
            term, _, count = line.rpartition(" ")
            if term:
                word_freq[term] = int(count)

    dictionary = set(word_freq)
    trie = marisa_trie.Trie(dictionary)

    sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
    sym_spell.load_dictionary(str(dict_path), 0, 1, separator=" ", encoding="utf-8")

    morph = pymorphy3.MorphAnalyzer()


# --- функции-исправлятор: ДОСЛОВНО из typo_corrector_standalone.py, НЕ МЕНЯТЬ ---

def correct_word_prefix(word, max_edit_distance=2):
    if LATIN_RE.match(word):
        return word

    if word in dictionary:
        return word

    if morph.word_is_known(word):
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
    parts = segmentation.corrected_string.replace("-", " ").split()
    if (
        len(parts) > 1
        and all(p in dictionary for p in parts)
        and segmentation.distance_sum <= max_edit_distance * len(parts)
    ):
        return " ".join(parts)

    return word


def correct_query_prefix(query, max_edit_distance=2):
    words = query.strip().split()

    merged_words = []
    i = 0
    while i < len(words):
        word = words[i]

        if word in dictionary or LATIN_RE.match(word):
            merged_words.append(word)
            i += 1
            continue

        if i + 1 < len(words) and words[i + 1] not in dictionary:
            merged = word + words[i + 1]
            if merged in dictionary:
                merged_words.append(merged)
                i += 2
                continue

            candidates = sym_spell.lookup(merged, Verbosity.CLOSEST, max_edit_distance=max_edit_distance)
            if candidates:
                best = max(candidates, key=lambda s: s.count / (DISTANCE_PENALTY ** s.distance))
                merged_words.append(best.term)
                i += 2
                continue

        merged_words.append(word)
        i += 1

    return " ".join(correct_word_prefix(w, max_edit_distance) for w in merged_words)


# --- удобный интерфейс поверх присланного кода ---

class TypoCorrector(Protocol):
    def correct(self, query: str) -> list[WordCorrection]:
        ...


class SymSpellCorrector:
    """Адаптер: инициализирует корректор и отдаёт пословный маппинг.

    Повторяет логику correct_query_prefix (склейка соседних слов + пословное
    исправление), но сохраняет соответствие исходный фрагмент -> исправление
    для подсветки. Если два слова склеиваются, original хранит оба слова через
    пробел (в вывод они не показываются, нужны только для флага changed).
    """

    def __init__(self, dict_path: Path) -> None:
        init_corrector(dict_path)

    def correct(self, query: str, max_edit_distance: int = 2) -> list[WordCorrection]:
        words = query.strip().split()

        # шаг 1: склейка соседних слов — как в correct_query_prefix,
        # но с сохранением исходного фрагмента для каждого токена
        merged: list[tuple[str, str]] = []  # (исходный фрагмент, токен)
        i = 0
        while i < len(words):
            word = words[i]

            if word in dictionary or LATIN_RE.match(word):
                merged.append((word, word))
                i += 1
                continue

            if i + 1 < len(words) and words[i + 1] not in dictionary:
                pair = f"{word} {words[i + 1]}"
                glued = word + words[i + 1]
                if glued in dictionary:
                    merged.append((pair, glued))
                    i += 2
                    continue

                candidates = sym_spell.lookup(
                    glued, Verbosity.CLOSEST, max_edit_distance=max_edit_distance
                )
                if candidates:
                    best = max(
                        candidates,
                        key=lambda s: s.count / (DISTANCE_PENALTY ** s.distance),
                    )
                    merged.append((pair, best.term))
                    i += 2
                    continue

            merged.append((word, word))
            i += 1

        # шаг 2: пословное исправление каждого токена
        return [
            WordCorrection(
                original=original,
                corrected=correct_word_prefix(token, max_edit_distance),
            )
            for original, token in merged
        ]
