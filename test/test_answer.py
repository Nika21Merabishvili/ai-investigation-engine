# tests/test_answer.py
"""answer.py without a database or an LLM: numbering, parsing, validation, the JSON retry and the gate."""
import json

import pytest

from app import answer, config
from app.llm import LLMUnavailable


def chunk(n, dense_score=0.8):
    return {"chunk_id": n, "document_title": f"Doc {n}", "text": f"Title: Doc {n}\nFact {n}.", "dense_score": dense_score}


SOURCE_MAP = {"S1": chunk(10), "S2": chunk(20)}


def reply(**fields):
    base = {"status": "answered", "answer": "", "citations": [], "conflicts": [], "missing": []}
    return {**base, **fields}


# --- format_sources -----------------------------------------------------------

def test_format_sources_numbers_from_s1():
    text, source_map = answer.format_sources([chunk(10), chunk(20)])
    assert list(source_map) == ["S1", "S2"]
    assert source_map["S2"]["chunk_id"] == 20
    assert text.startswith("[S1] Title: Doc 10")


# --- parse_reply --------------------------------------------------------------

def test_parse_reply_accepts_code_fence():
    assert answer.parse_reply('```json\n{"status": "partial", "answer": "x"}\n```')["status"] == "partial"


@pytest.mark.parametrize("text", ["not json", "[1, 2]", '{"status": "maybe"}', '{"status": "answered", "citations": "S1"}'])
def test_parse_reply_rejects_bad_replies(text):
    with pytest.raises(ValueError):
        answer.parse_reply(text)


# --- finalize -----------------------------------------------------------------

def test_unknown_source_is_dropped():
    result = answer.finalize(reply(answer="A [S1]. B [S9].", citations=["S1", "S9"]), SOURCE_MAP)
    assert result["answer"] == "A [S1]. B ."
    assert [c["id"] for c in result["citations"]] == ["S1"]
    assert result["citations"][0] == {"id": "S1", "document_title": "Doc 10", "chunk_id": 10, "text": "Title: Doc 10\nFact 10."}


def test_combined_marker_is_split():
    result = answer.finalize(reply(answer="A [S1, S2]."), SOURCE_MAP)
    assert result["answer"] == "A [S1][S2]."
    assert [c["id"] for c in result["citations"]] == ["S1", "S2"]


def test_answer_without_valid_citation_becomes_insufficient():
    result = answer.finalize(reply(answer="Made-up fact [S7]."), SOURCE_MAP)
    assert result["status"] == "insufficient"
    assert result["answer"] == "" and result["citations"] == []


def test_conflict_needs_two_valid_sides():
    conflicts = [
        {"topic": "kept", "positions": [{"claim": "x", "sources": ["S1"]}, {"claim": "y", "sources": ["S2"]}]},
        {"topic": "dropped", "positions": [{"claim": "x", "sources": ["S1"]}, {"claim": "y", "sources": ["S5"]}]},
    ]
    result = answer.finalize(reply(answer="A [S1].", conflicts=conflicts), SOURCE_MAP)
    assert [c["topic"] for c in result["conflicts"]] == ["kept"]
    assert [c["id"] for c in result["citations"]] == ["S1", "S2"]  # conflict sources are citable too


# --- ask_llm_json: one retry on an unusable reply -----------------------------

def fake_llm(monkeypatch, replies):
    calls = []

    def chat_json(messages):
        calls.append(messages)
        return replies.pop(0)

    monkeypatch.setattr(answer, "chat_json", chat_json)
    return calls


def test_invalid_json_is_retried_once(monkeypatch):
    calls = fake_llm(monkeypatch, ["oops", json.dumps(reply(answer="A [S1]."))])
    assert answer.ask_llm_json([{"role": "user", "content": "q"}])["answer"] == "A [S1]."
    assert len(calls) == 2
    assert calls[1][-2] == {"role": "assistant", "content": "oops"}  # the model sees its own bad reply


def test_second_invalid_reply_raises(monkeypatch):
    fake_llm(monkeypatch, ["oops", "still oops"])
    with pytest.raises(LLMUnavailable):
        answer.ask_llm_json([{"role": "user", "content": "q"}])


# --- answer_question: the threshold gate --------------------------------------

def test_low_similarity_skips_the_llm(monkeypatch):
    monkeypatch.setattr(answer, "hybrid_search", lambda conn, question, k: [chunk(1, 0.40), chunk(2, None)])
    monkeypatch.setattr(config, "MIN_DENSE_SIMILARITY", 0.55)
    calls = fake_llm(monkeypatch, [])
    result = answer.answer_question(None, "Who won the 1998 World Cup?")
    assert result["status"] == "insufficient"
    assert calls == []
