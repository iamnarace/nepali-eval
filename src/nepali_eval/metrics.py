"""Scoring metrics. All are pure functions with no third-party dependencies.

``chrf`` follows the algorithm used by sacrebleu (Popovic 2015/2017): character
n-grams (whitespace removed), optional word n-grams (chrF++), statistics summed over a
corpus, precision/recall averaged over the n-gram orders that occur, then an F-beta
score (beta=2). ``tests/test_metrics.py`` cross-checks it against sacrebleu.
"""

from __future__ import annotations

import string
from collections import Counter
from collections.abc import Iterable, Sequence

from .normalize import extract_numbers, normalize_text, script_stats

_PUNCT = set(string.punctuation)


def exact_match(prediction: str, references: Sequence[str]) -> float:
    """1.0 if the normalised prediction equals any normalised reference."""
    p = normalize_text(prediction, strip_punct=True)
    return float(any(p == normalize_text(r, strip_punct=True) for r in references))


def numbers_preserved(prediction: str, references: Sequence[str]) -> float:
    """1.0 if the multiset of numbers in the prediction equals that of any reference
    that contains numbers; 1.0 trivially if no reference contains numbers.

    Digit systems are unified (२०८२ == 2082) and thousands separators ignored.
    """
    ref_sets = [Counter(extract_numbers(r)) for r in references]
    ref_sets = [c for c in ref_sets if c]
    if not ref_sets:
        return 1.0
    pred = Counter(extract_numbers(prediction))
    return float(any(pred == c for c in ref_sets))


def devanagari_ratio(prediction: str) -> float:
    return script_stats(prediction)["devanagari"]


def _remove_punct(sentence: str) -> list[str]:
    tokens: list[str] = []
    for w in sentence.split():
        if len(w) == 1:
            tokens.append(w)
        elif w[-1] in _PUNCT:
            tokens += [w[:-1], w[-1]]
        elif w[0] in _PUNCT:
            tokens += [w[0], w[1:]]
        else:
            tokens.append(w)
    return tokens


def _ngrams(seq: Sequence[str], n: int) -> Counter:
    return Counter(tuple(seq[i : i + n]) for i in range(len(seq) - n + 1))


def _stats(hyp: str, ref: str, char_order: int, word_order: int) -> list[int]:
    out: list[int] = []
    h_chars, r_chars = list("".join(hyp.split())), list("".join(ref.split()))
    h_words, r_words = _remove_punct(hyp), _remove_punct(ref)
    for n in range(1, char_order + 1):
        out += _count(_ngrams(h_chars, n), _ngrams(r_chars, n))
    for n in range(1, word_order + 1):
        out += _count(_ngrams(h_words, n), _ngrams(r_words, n))
    return out


def _count(h: Counter, r: Counter) -> list[int]:
    match = sum(min(c, r[g]) for g, c in h.items())
    return [sum(h.values()), sum(r.values()), match]


def _fscore(stats: Sequence[int], order: int, beta: float) -> float:
    factor = beta**2
    avg_p = avg_r = 0.0
    eff = 0
    for i in range(order):
        n_hyp, n_ref, n_match = stats[3 * i : 3 * i + 3]
        if n_hyp > 0 and n_ref > 0:
            avg_p += n_match / n_hyp
            avg_r += n_match / n_ref
            eff += 1
    if eff == 0:
        return 0.0
    avg_p, avg_r = avg_p / eff, avg_r / eff
    if avg_p + avg_r == 0:
        return 0.0
    return 100 * (1 + factor) * avg_p * avg_r / (factor * avg_p + avg_r)


def chrf(
    hypotheses: Iterable[str],
    references: Iterable[str],
    *,
    char_order: int = 6,
    word_order: int = 0,
    beta: float = 2.0,
) -> float:
    """Corpus-level chrF (``word_order=0``) or chrF++ (``word_order=2``), on a 0-100 scale.

    Inputs are normalised with :func:`normalize_text` first so that digit systems and
    dandas do not affect the score.
    """
    total = [0] * (3 * (char_order + word_order))
    for h, r in zip(hypotheses, references, strict=True):
        s = _stats(normalize_text(h), normalize_text(r), char_order, word_order)
        total = [a + b for a, b in zip(total, s, strict=True)]
    return _fscore(total, char_order + word_order, beta)


def sentence_chrf(prediction: str, references: Sequence[str], *, word_order: int = 0) -> float:
    """Best sentence-level chrF/chrF++ over several acceptable references (0-100)."""
    return max(chrf([prediction], [r], word_order=word_order) for r in references)
