import pytest

from nepali_eval import metrics

sacrebleu = pytest.importorskip("sacrebleu")
from sacrebleu.metrics import CHRF  # noqa: E402

PAIRS = [
    ("The cat sat on the mat.", "The cat is sitting on the mat."),
    ("Kathmandu is the capital of Nepal.", "Kathmandu is Nepal's capital."),
    ("I like tea.", "I like tea."),
    ("completely different words here", "nothing in common at all"),
    ("Please close the door.", "Close the door, please!"),
    ("म भोलि आउँछु।", "म भोलि आउनेछु।"),
    ("धेरै धन्यवाद", "तपाईंलाई धेरै धन्यवाद"),
    ("a", "b"),
]


@pytest.mark.parametrize("word_order", [0, 2])
def test_corpus_chrf_matches_sacrebleu(word_order):
    # Compare on pre-normalised text so only the scoring algorithm is under test.
    hyps = [metrics.normalize_text(h) for h, _ in PAIRS]
    refs = [metrics.normalize_text(r) for _, r in PAIRS]
    expected = CHRF(word_order=word_order).corpus_score(hyps, [refs]).score
    assert metrics.chrf(hyps, refs, word_order=word_order) == pytest.approx(expected, abs=1e-6)


@pytest.mark.parametrize("word_order", [0, 2])
def test_sentence_chrf_matches_sacrebleu(word_order):
    for h, r in PAIRS:
        hn, rn = metrics.normalize_text(h), metrics.normalize_text(r)
        expected = CHRF(word_order=word_order).sentence_score(hn, [rn]).score
        assert metrics.sentence_chrf(h, [r], word_order=word_order) == pytest.approx(
            expected, abs=1e-6), (h, r)


def test_chrf_ignores_digit_system_and_danda():
    assert metrics.sentence_chrf("भोलि १० बजे।", ["भोलि 10 बजे."]) == pytest.approx(100.0)


def test_best_of_multiple_references():
    refs = ["completely unrelated", "I like tea."]
    assert metrics.sentence_chrf("I like tea.", refs) == pytest.approx(100.0)


def test_exact_match_tolerates_punctuation_and_variants_in_list():
    assert metrics.exact_match("काठमाडौं।", ["काठमाडौँ", "काठमाडौं"]) == 1.0
    assert metrics.exact_match("पोखरा", ["काठमाडौं"]) == 0.0


def test_numbers_preserved():
    refs = ["Let's meet at 10."]
    assert metrics.numbers_preserved("मिलौं १०", refs) == 1.0  # digit system independent
    assert metrics.numbers_preserved("Let's meet at 11.", refs) == 0.0
    assert metrics.numbers_preserved("anything", ["no numbers here"]) == 1.0
    assert metrics.numbers_preserved("Rs. 1,500", ["Rs. 1500"]) == 1.0


def test_empty_prediction_scores_zero():
    assert metrics.sentence_chrf("", ["abc"]) == 0.0
