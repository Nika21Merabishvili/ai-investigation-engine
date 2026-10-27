# eval/metrics.py
"""Retrieval metrics for ONE question. The eval scripts average them over all questions.

YOU WRITE THESE (about 5 lines each). tests/test_metrics.py tells you when they're right.
Day 4 adds citation accuracy, exact match and token F1 to this file.
"""


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
