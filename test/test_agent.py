# tests/test_agent.py
"""The agent loop with a fake model and a fake search: no Gemini, no database."""
import json
from types import SimpleNamespace

from app import agent


def chunk(n):
    return {"chunk_id": n, "document_title": f"Doc {n}", "text": f"Title: Doc {n}\nFact {n}.", "dense_score": 0.8}


def call(call_id, query=None, name="search_documents", arguments=None):
    if arguments is None:
        arguments = json.dumps({"query": query})
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


class FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, exclude_none=False):
        return {"role": "assistant", "tool_calls": [c.id for c in self.tool_calls or []]}


class FakeChat:
    """Plays back assistant messages and records what each round was sent."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.sent = []          # a copy of the messages list, per round
        self.tool_choices = []

    def __call__(self, messages, tools, tool_choice):
        self.sent.append(list(messages))
        self.tool_choices.append(tool_choice)
        return self.replies.pop(0)


def fake_search(results):
    """Search that answers from a {query: chunks} dict and records the queries."""
    queries = []

    def search(conn, query, k):
        queries.append(query)
        return results.get(query, [])
    search.queries = queries
    return search


def answer_json(answer, citations):
    return json.dumps({"status": "answered", "answer": answer, "citations": citations, "conflicts": [], "missing": []})


# --- Evidence and format_results ----------------------------------------------

def test_evidence_keeps_labels_across_rounds():
    evidence = agent.Evidence()
    assert evidence.add([chunk(1), chunk(2)]) == ["S1", "S2"]
    assert evidence.add([chunk(2), chunk(3)]) == ["S2", "S3"]
    assert evidence.by_label["S3"]["chunk_id"] == 3


def test_format_results():
    evidence = agent.Evidence()
    labels = evidence.add([chunk(1), chunk(2)])
    assert agent.format_results(labels, evidence) == "[S1] Title: Doc 1\nFact 1.\n\n[S2] Title: Doc 2\nFact 2."
    assert agent.format_results([], evidence) == "No results."


# --- the loop -----------------------------------------------------------------

def test_two_searches_then_answer():
    chat = FakeChat([
        FakeMessage(tool_calls=[call("call_1", "Arthur's Magazine")]),
        FakeMessage(tool_calls=[call("call_2", "First for Women")]),
        FakeMessage(content=answer_json("Arthur's came first [S1]. First for Women is newer [S3].", ["S1", "S3"])),
    ])
    search = fake_search({"Arthur's Magazine": [chunk(1), chunk(2)], "First for Women": [chunk(2), chunk(3)]})

    result, trace = agent.run_agent(None, "Which came first?", chat_fn=chat, search_fn=search)

    assert chat.tool_choices == ["auto", "auto", "none"]
    second_tool_message = chat.sent[2][-2]  # the last message is the final-round nudge
    assert second_tool_message == {"role": "tool", "tool_call_id": "call_2",
                                   "content": "[S2] Title: Doc 2\nFact 2.\n\n[S3] Title: Doc 3\nFact 3."}
    assert result["status"] == "answered"
    assert [c["chunk_id"] for c in result["citations"]] == [1, 3]
    assert [s["query"] for s in trace["searches"]] == ["Arthur's Magazine", "First for Women"]
    assert trace["searches"][1]["chunk_ids"] == [2, 3]
    assert trace["rounds"] == 3
    assert trace["fallback"] is False


def test_several_calls_in_one_round_each_get_a_tool_message():
    chat = FakeChat([
        FakeMessage(tool_calls=[call("a", "one"), call("b", "two")]),
        FakeMessage(content=answer_json("Fact [S1][S2].", ["S1", "S2"])),
    ])
    search = fake_search({"one": [chunk(1)], "two": [chunk(2)]})
    agent.run_agent(None, "q", chat_fn=chat, search_fn=search)
    tool_messages = [m for m in chat.sent[1] if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_messages] == ["a", "b"]


def test_bad_calls_get_error_text_instead_of_crashing():
    chat = FakeChat([
        FakeMessage(tool_calls=[
            call("bad_json", arguments="{not json"),
            call("empty", query="  "),
            call("unknown", query="x", name="delete_everything"),
            call("good", query="real"),
        ]),
        FakeMessage(content=answer_json("Fact [S1].", ["S1"])),
    ])
    search = fake_search({"real": [chunk(1)]})
    result, trace = agent.run_agent(None, "q", chat_fn=chat, search_fn=search)
    contents = {m["tool_call_id"]: m["content"] for m in chat.sent[1] if m["role"] == "tool"}
    assert all(contents[i].startswith("Error") for i in ["bad_json", "empty", "unknown"])
    assert search.queries == ["real"]
    assert result["status"] == "answered"


def test_repeated_query_is_not_searched_again():
    chat = FakeChat([
        FakeMessage(tool_calls=[call("1", "same")]),
        FakeMessage(tool_calls=[call("2", "Same ")]),
        FakeMessage(content=answer_json("Fact [S1].", ["S1"])),
    ])
    search = fake_search({"same": [chunk(1)]})
    agent.run_agent(None, "q", chat_fn=chat, search_fn=search)
    assert search.queries == ["same"]


def test_answer_without_searching_is_insufficient():
    chat = FakeChat([FakeMessage(content=answer_json("I know this one [S1].", ["S1"]))])
    result, trace = agent.run_agent(None, "q", chat_fn=chat, search_fn=fake_search({}))
    assert result["status"] == "insufficient"
    assert trace["searches"] == []


def test_unknown_labels_are_dropped():
    chat = FakeChat([
        FakeMessage(tool_calls=[call("1", "q")]),
        FakeMessage(content=answer_json("Fact [S1]. Made up [S9].", ["S1", "S9"])),
    ])
    result, _ = agent.run_agent(None, "q", chat_fn=chat, search_fn=fake_search({"q": [chunk(1)]}))
    assert [c["id"] for c in result["citations"]] == ["S1"]
    assert "[S9]" not in result["answer"]


def test_last_round_still_asking_for_tools_falls_back(monkeypatch):
    chat = FakeChat([FakeMessage(tool_calls=[call(str(i), f"q{i}")]) for i in range(agent.MAX_ROUNDS)])
    search = fake_search({"q0": [chunk(1)], "q1": [chunk(2)]})
    fallback_calls = []

    def fake_ask(messages):
        fallback_calls.append(messages)
        return {"status": "answered", "answer": "Fact [S2].", "citations": ["S2"], "conflicts": [], "missing": []}
    monkeypatch.setattr(agent, "ask_llm_json", fake_ask)

    result, trace = agent.run_agent(None, "q", chat_fn=chat, search_fn=search)

    assert search.queries == ["q0", "q1"]  # the last round's tool calls are not run
    assert "[S2] Title: Doc 2" in fallback_calls[0][1]["content"]
    assert [c["chunk_id"] for c in result["citations"]] == [2]
    assert trace["fallback"] is True
