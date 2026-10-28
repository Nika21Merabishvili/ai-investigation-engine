# tests/test_answer_eval.py
"""The helpers and the per-question scoring in eval/answer_eval.py. No database, no LLM.

Run: python -m pytest test/test_answer_eval.py -q
(The score_one tests also need your answer metrics in eval/metrics.py.)
"""
import pytest

from eval.answer_eval import (
    agent_titles, latest_records, retrieved_ranking, score_one, strip_markers, unique_in_order,
)

ERROR_ANSWER = {"status": "error", "answer": "", "citations": [], "conflicts": [], "missing": []}
HOTPOT_Q = {"id": "hp_bridge_01", "source": "hotpotqa", "type": "bridge", "expected": "answer",
            "gold_answer": "Chief of Protocol", "gold_titles": ["Kiss and Tell (1945 film)", "Shirley Temple"]}


def _record(answer: dict, retrieved: list[str], mode: str = "simple", trace: dict | None = None, **extra) -> dict:
    return {"id": "x", "mode": mode, "answer": answer, "retrieved_titles": retrieved, "trace": trace,
            "seconds": 1.0, **extra}


def test_strip_markers_removes_single_and_grouped_markers():
    text = strip_markers("Paris [S1] is big [S2, S5][S7].")
    assert "S" not in text
    assert text.split() == ["Paris", "is", "big", "."]


def test_unique_in_order_keeps_first_positions():
    assert unique_in_order(["A", "B", "A", "C", "B"]) == ["A", "B", "C"]


def test_latest_records_lets_a_retry_replace_an_error():
    records = [{"id": "q1", "mode": "agent", "error": "busy"}, {"id": "q1", "mode": "simple"},
               {"id": "q1", "mode": "agent", "answer": "ok"}]
    latest = latest_records(records)
    assert latest[("q1", "agent")] == {"id": "q1", "mode": "agent", "answer": "ok"}
    assert len(latest) == 2


def test_agent_titles_follow_the_order_of_the_searches():
    trace = {"searches": [{"query": "q1", "document_titles": ["A", "B"]},
                          {"query": "q2", "document_titles": ["B", "C"]}]}
    assert agent_titles(trace) == ["A", "B", "B", "C"]
    assert agent_titles({"searches": []}) == []


def test_agent_titles_explains_a_wrong_key():
    with pytest.raises(KeyError, match="AGENT_TITLES_KEY"):
        agent_titles({"searches": [{"query": "q1", "titles": ["A"]}]})


def test_retrieved_ranking_reads_agent_titles_from_the_trace():
    trace = {"searches": [{"query": "q", "document_titles": ["A", "B"]}]}
    assert retrieved_ranking(_record(ERROR_ANSWER, [], mode="agent", trace=trace)) == ["A", "B"]
    assert retrieved_ranking(_record(ERROR_ANSWER, ["X"], mode="simple")) == ["X"]


def test_score_one_for_an_unanswerable_question_only_checks_abstention():
    q = {"id": "co_none_01", "source": "company", "type": "unanswerable", "expected": "insufficient",
         "gold_answer": "", "gold_titles": []}
    answer = {"status": "insufficient", "answer": "", "citations": [], "conflicts": [], "missing": ["memory saved"]}
    row = score_one(q, _record(answer, ["NovaPay doc"]))
    assert row["abstained"] is True
    assert row["conflict_reported"] is False
    assert "recall@5" not in row and "citation_accuracy" not in row and "f1" not in row


def test_score_one_for_a_hotpot_answer():
    answer = {"status": "answered", "answer": "She served as Chief of Protocol [S2].",
              "citations": [{"id": "S2", "document_title": "Shirley Temple", "chunk_id": 7, "text": "..."}],
              "conflicts": [], "missing": []}
    # two chunks of "Shirley Temple": as documents the ranking is Shirley Temple, X, Kiss and Tell
    row = score_one(HOTPOT_Q, _record(answer, ["Shirley Temple", "Shirley Temple", "X", "Kiss and Tell (1945 film)"]))
    assert row["recall@5"] == 1.0
    assert row["mrr"] == 1.0
    assert row["citation_accuracy"] == 1.0
    assert row["em"] == 0.0                                # a sentence is never an exact match
    assert row["f1"] == pytest.approx(2 * 0.5 * 1.0 / 1.5)  # she served as chief of protocol: 3 of 6 words
    assert row["gold_in_answer"] == 1.0
    assert row["abstained"] is False


def test_score_one_counts_an_error_as_a_failed_answer():
    # simple mode: the search ran before the LLM failed, so retrieval is still scored
    row = score_one(HOTPOT_Q, _record(ERROR_ANSWER, ["Shirley Temple"], error="busy"))
    assert row["status"] == "error"
    assert row["recall@5"] == 0.5
    assert row["f1"] == 0.0 and row["abstained"] is False
    assert row["citation_accuracy"] is None                # nothing cited, nothing to judge
    # agent mode: the trace was lost, so there is no ranking to score
    row = score_one(HOTPOT_Q, _record(ERROR_ANSWER, [], mode="agent", error="busy"))
    assert "recall@5" not in row and row["f1"] == 0.0
