# eval/metrics.py
"""Retrieval metrics for ONE question. The eval scripts average them over all questions.

YOU WRITE THESE (about 5 lines each). tests/test_metrics.py tells you when they're right.
Day 4 adds citation accuracy, exact match and token F1 to this file.
"""
import re
import string
from collections import Counter


def recall_at_k(retrieved: list[str], gold: list[str], k: int) -> float:
    """Share of the gold items that appear among the first k retrieved items.

    retrieved: document titles, best first (the same title may appear twice).
    gold:      the titles that answer the question (HotpotQA: usually 2).
    Example:   retrieved = ["X", "A", "Y", "B"], gold = ["A", "B"]
               k=1 -> 0.0, k=2 -> 0.5 (only A), k=4 -> 1.0
    Empty gold -> raise ValueError: a question with nothing to find can't be scored.
    """
    if not gold:
        raise ValueError("gold is empty: a question with nothing to find can't be scored")
    top_k = set(retrieved[:k])
    gold_set = set(gold)
    found = len(top_k & gold_set)
    return found / len(gold_set)


def mrr(retrieved: list[str], gold: list[str]) -> float:
    """Reciprocal rank of the FIRST gold item: 1 / rank, ranks start at 1; 0.0 if no gold item is retrieved.

    This is one question's score; the "Mean" in MRR is the average the eval script takes.
    Example: retrieved = ["X", "A", "Y", "B"], gold = ["A", "B"] -> first gold is A at rank 2 -> 0.5
    """
    gold_set = set(gold)
    for rank, title in enumerate(retrieved, start=1):
        if title in gold_set:
            return 1 / rank
    return 0.0

# ---- Day 4: answer metrics ----

def normalize_answer(text: str) -> str:
    """Lowercase, remove punctuation, remove the words a/an/the, collapse whitespace.
    "The Eiffel Tower!" -> "eiffel tower";  "1,284 customers." -> "1284 customers"
    """
    raise NotImplementedError("Write normalize_answer() yourself")


def exact_match(prediction: str, gold: str) -> float:
    """1.0 if both strings are equal after normalize_answer(), else 0.0."""
    raise NotImplementedError("Write exact_match() yourself")


def token_f1(prediction: str, gold: str) -> float:
    """Word-overlap F1 of the normalized strings. A repeated word counts as often as BOTH have it.
    "the Eiffel Tower in Paris" vs "Eiffel Tower": common 2, precision 2/4, recall 2/2 -> 0.667
    """
    raise NotImplementedError("Write token_f1() yourself")


def gold_in_answer(prediction: str, gold: str) -> float:
    """1.0 if the normalized gold appears in the normalized prediction as whole words.
    "No, they were not." contains "no" -> 1.0;  "I do not know" does not -> 0.0
    """
    raise NotImplementedError("Write gold_in_answer() yourself")


def citation_accuracy(cited: list[str], gold: list[str]) -> float | None:
    """Share of the cited DOCUMENTS that are gold; each document counts once.
    ["A", "A", "X"] with gold ["A", "B"] -> documents {A, X} -> 0.5
    Nothing cited -> None. Empty gold -> raise ValueError.
    """
    raise NotImplementedError("Write citation_accuracy() yourself")