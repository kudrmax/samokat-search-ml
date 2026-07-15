import re
from pathlib import Path

import marisa_trie
import pymorphy3
from symspellpy import SymSpell, Verbosity

DOMAIN_DICTIONARY_PATH = Path(__file__).parent / "domain_dictionary.txt"
LATIN_RE = re.compile(r'^[a-zA-Z]+$')
DISTANCE_PENALTY = 10

morph = pymorphy3.MorphAnalyzer()

word_freq = {}
with open(DOMAIN_DICTIONARY_PATH, encoding='utf-8') as f:
    for line in f:
        word, count = line.rsplit(' ', 1)
        word_freq[word] = int(count)

dictionary = set(word_freq)
trie = marisa_trie.Trie(dictionary)

sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
sym_spell.load_dictionary(str(DOMAIN_DICTIONARY_PATH), 0, 1, separator=' ', encoding='utf-8')


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
    parts = segmentation.corrected_string.replace('-', ' ').split()
    if (
        len(parts) > 1
        and all(p in dictionary for p in parts)
        and segmentation.distance_sum <= max_edit_distance * len(parts)
    ):
        return ' '.join(parts)

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

    return ' '.join(correct_word_prefix(w, max_edit_distance) for w in merged_words)


if __name__ == '__main__':
    examples = ['туалетная ьумагп', 'кокт', 'укропбатон', 'ку сочки']
    for q in examples:
        print(f'{q!r:25} -> {correct_query_prefix(q)!r}')
