# tests/test_answer_metrics.py
"""Hand-computed examples for the Day 4 answer metrics in eval/metrics.py.

Run: python -m pytest test/test_answer_metrics.py -q
"""
import pytest

from eval.metrics import citation_accuracy, exact_match, gold_in_answer, normalize_answer, token_f1


def test_normalize_lowercases_and_removes_punctuation():
    assert normalize_answer("The Eiffel Tower!") == "eiffel tower"
    assert normalize_answer("1,284 customers.") == "1284 customers"


def test_normalize_removes_whole_word_articles_only():
    # "a" and "an" go, but the "a" inside "apple" and "day" must stay
    assert normalize_answer("  An   apple, a day ") == "apple day"


def test_exact_match_ignores_case_punctuation_and_articles():
    assert exact_match("The Eiffel Tower.", "eiffel tower") == 1.0
    assert exact_match("Eiffel Tower in Paris", "Eiffel Tower") == 0.0


def test_token_f1_partial_overlap():
    # prediction words: eiffel tower in paris (4); gold: eiffel tower (2); common: 2
    # precision 2/4 = 0.5, recall 2/2 = 1.0, F1 = 2 * 0.5 * 1.0 / 1.5 = 0.667
    assert token_f1("the Eiffel Tower in Paris", "Eiffel Tower") == pytest.approx(2 / 3)


def test_token_f1_counts_a_repeated_word_only_as_often_as_both_have_it():
    # prediction: yes yes (2); gold: yes (1); common: 1 -> precision 1/2, recall 1/1, F1 2/3
    assert token_f1("yes yes", "yes") == pytest.approx(2 / 3)


def test_token_f1_is_zero_without_overlap_or_for_an_empty_answer():
    assert token_f1("Paris", "London") == 0.0
    assert token_f1("", "London") == 0.0   # an abstention has no answer text


def test_gold_in_answer_matches_whole_words():
    assert gold_in_answer("She served as Chief of Protocol.", "Chief of Protocol") == 1.0
    assert gold_in_answer("No, they were not both American.", "no") == 1.0
    assert gold_in_answer("I do not know.", "no") == 0.0   # "not" and "know" are not the word "no"
    assert gold_in_answer("", "London") == 0.0


def test_citation_accuracy_is_the_share_of_cited_documents_that_are_gold():
    assert citation_accuracy(["A", "X"], ["A", "B"]) == 0.5
    assert citation_accuracy(["A", "B"], ["A", "B", "C"]) == 1.0   # not citing C is recall's business


def test_citation_accuracy_counts_each_document_once():
    assert citation_accuracy(["A", "A", "A", "X"], ["A"]) == 0.5   # documents cited: A and X


def test_citation_accuracy_is_none_when_nothing_is_cited():
    assert citation_accuracy([], ["A"]) is None


def test_citation_accuracy_refuses_an_empty_gold_set():
    with pytest.raises(ValueError):
        citation_accuracy(["A"], [])
