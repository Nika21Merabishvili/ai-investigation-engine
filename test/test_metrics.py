# tests/test_metrics.py
"""Hand-computed examples for the retrieval metrics. Run: python -m pytest tests/test_metrics.py -q"""
import pytest

from eval.metrics import mrr, recall_at_k

RETRIEVED = ["X", "A", "Y", "B", "Z"]   # A is at rank 2, B at rank 4
GOLD = ["A", "B"]


def test_recall_counts_gold_found_in_the_top_k():
    assert recall_at_k(RETRIEVED, GOLD, 1) == 0.0    # top 1: X
    assert recall_at_k(RETRIEVED, GOLD, 2) == 0.5    # top 2: X, A -> 1 of 2 gold
    assert recall_at_k(RETRIEVED, GOLD, 4) == 1.0    # top 4: X, A, Y, B -> 2 of 2


def test_recall_with_k_longer_than_the_list():
    assert recall_at_k(["A"], GOLD, 10) == 0.5


def test_recall_counts_a_repeated_title_once():
    assert recall_at_k(["A", "A", "Y"], GOLD, 3) == 0.5


def test_recall_refuses_an_empty_gold_set():
    with pytest.raises(ValueError):
        recall_at_k(RETRIEVED, [], 5)


def test_mrr_uses_the_first_gold_hit_only():
    assert mrr(RETRIEVED, GOLD) == 0.5           # A at rank 2; B at rank 4 doesn't matter
    assert mrr(["B", "X"], GOLD) == 1.0          # either gold title counts


def test_mrr_is_zero_when_nothing_relevant_is_retrieved():
    assert mrr(["X", "Y", "Z"], GOLD) == 0.0
    assert mrr([], GOLD) == 0.0
