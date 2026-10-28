# app/agent.py
"""Agent mode: the model searches as often as it needs (within MAX_ROUNDS), then answers.

One round is one model call. In each round the model either asks for searches (tool calls),
which we run with hybrid_search and send back as tool messages, or it answers in JSON.
The last round adds a "no more searches" message and tool_choice="none". If the final reply
is still unusable (no JSON, or tool calls instead of an answer), a fallback asks once more in
simple mode over all the evidence, through ask_llm_json() with its one retry. So the worst case
is MAX_ROUNDS + 2 calls. Every chunk seen in any round goes into one Evidence registry, labelled
S1, S2, ... across rounds, so all of them are citable; finalize() from answer.py then checks
the citations against that registry.

run_agent() returns (answer, trace). The API returns only the answer; the eval uses the trace,
including trace["fallback"], which says whether the fallback ran.

Run from the repo root:  python -m app.agent "Which magazine was started first, Arthur's Magazine or First for Women?"
"""
import json

import psycopg

from app.answer import (ANSWER_RULES, SYSTEM_PROMPT, ask_llm_json, finalize, format_sources, insufficient,
                        parse_reply)
from app.llm import chat_with_tools
from app.search import hybrid_search

MAX_ROUNDS = 3
SEARCH_K = 5  # smaller than simple mode's 8, because the model may search several times

SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": "Search the document collection. Returns passages labelled [S#] that you can cite. "
                       "Search again with a different, more specific query to follow up on something you found.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Short, keyword-rich search query"}},
            "required": ["query"],
        },
    },
}

AGENT_PROMPT = """You answer questions using ONLY the passages that the search_documents tool returns. Ignore anything else you know.

Searching:
- Search before answering. Every passage comes labelled [S#]; those labels are your sources.
- For questions with several parts, search for each part. Use names you find in one result to write the next query.
- Cite only [S#] labels you have seen in search results.
- Once the passages answer the question, stop searching and reply with the JSON object below.

""" + ANSWER_RULES

FINAL_ROUND_MESSAGE = "No more searches are possible. Answer now from the passages above, as the JSON object."


class Evidence:
    """Every chunk retrieved during one run, labelled S1, S2, ... in the order first seen."""

    def __init__(self) -> None:
        self.by_label: dict[str, dict] = {}   # "S3" -> chunk; the source map finalize() needs
        self.label_of: dict = {}              # chunk_id -> "S3"

    def add(self, chunks: list[dict]) -> list[str]:
        """Register the chunks and return their labels. A chunk seen before keeps its old label."""
        labels = []
        for chunk in chunks:
            label = self.label_of.get(chunk["chunk_id"])
            if label is None:
                label = f"S{len(self.by_label) + 1}"
                self.label_of[chunk["chunk_id"]] = label
                self.by_label[label] = chunk
            labels.append(label)
        return labels


def format_results(labels: list[str], evidence: Evidence) -> str:
    """Tool result text: '[S6] Title: ...' blocks. Chunk texts already start with their title line."""
    if not labels:
        return "No results."
    return "\n\n".join(f"[{label}] {evidence.by_label[label]['text']}" for label in labels)


def _run_tool_call(call, conn, search_fn, evidence: Evidence, trace: dict) -> str:
    """Run one tool call and return the tool message text. Bad calls get an error text, never an exception,
    so the model can correct itself in the next round."""
    if call.function.name != SEARCH_TOOL["function"]["name"]:
        return f'Error: unknown tool "{call.function.name}". The only tool is search_documents.'
    try:
        args = json.loads(call.function.arguments or "{}")
    except json.JSONDecodeError:
        args = None
    query = args.get("query") if isinstance(args, dict) else None
    if not isinstance(query, str) or not query.strip():
        return 'Error: call search_documents with arguments like {"query": "short search query"}.'

    query = query.strip()
    if query.lower() in (search["query"].lower() for search in trace["searches"]):
        return "You already ran this search; its results are above. Try a different query or answer."

    chunks = search_fn(conn, query, k=SEARCH_K)
    labels = evidence.add(chunks)
    trace["searches"].append({
        "query": query,
        "chunk_ids": [c["chunk_id"] for c in chunks],
        "document_titles": [c["document_title"] for c in chunks],
    })
    return format_results(labels, evidence)


def run_agent(conn: psycopg.Connection, question: str,
              chat_fn=chat_with_tools, search_fn=hybrid_search) -> tuple[dict, dict]:
    """Answer one question in agent mode. Returns (answer JSON as in simple mode, trace).

    chat_fn and search_fn are parameters so tests can run the loop without Gemini or a database.
    """
    evidence = Evidence()
    trace: dict = {"rounds": 0, "searches": [], "fallback": False}
    messages = [
        {"role": "system", "content": AGENT_PROMPT},
        {"role": "user", "content": f"Question: {question}"},
    ]

    for round_no in range(1, MAX_ROUNDS + 1):
        last = round_no == MAX_ROUNDS
        if last:
            messages.append({"role": "user", "content": FINAL_ROUND_MESSAGE})
        msg = chat_fn(messages, [SEARCH_TOOL], "none" if last else "auto")
        trace["rounds"] = round_no
        if not msg.tool_calls or last:
            break  # the model is answering (or, on the last round, ignored tool_choice="none")
        messages.append(msg.model_dump(exclude_none=True))  # as returned: keeps Gemini's thought signatures
        for call in msg.tool_calls:  # every call needs its own tool message with the matching id
            content = _run_tool_call(call, conn, search_fn, evidence, trace)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": content})

    if not evidence.by_label:
        return insufficient(["The searches found no passages for this question."]), trace

    try:
        data = parse_reply(msg.content or "")  # content is None if the last round still asked for tools
    except ValueError:
        trace["fallback"] = True  # costs 1-2 extra LLM calls; the eval reports how often this happens
        data = ask_llm_json(_fallback_messages(question, evidence))
    return finalize(data, evidence.by_label), trace


def _fallback_messages(question: str, evidence: Evidence) -> list[dict]:
    """Simple-mode prompt over everything the loop retrieved, for when the agent's own reply is unusable.

    format_sources() numbers from S1 in order, which matches the registry's labels exactly,
    because the registry hands out S1, S2, ... in insertion order.
    """
    sources, _ = format_sources(list(evidence.by_label.values()))
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Sources:\n\n{sources}\n\nQuestion: {question}"},
    ]


if __name__ == "__main__":
    import sys
    import time

    from app.db import get_conn

    question = " ".join(sys.argv[1:])
    if not question:
        sys.exit('Usage: python -m app.agent "your question"')

    start = time.perf_counter()
    with get_conn() as conn:
        result, trace = run_agent(conn, question)
    for search in trace["searches"]:
        print(f"search: {search['query']!r} -> {search['document_titles']}", file=sys.stderr)
    print(json.dumps({"answer": result, "trace": trace}, indent=2, ensure_ascii=False, default=str))
    print(f"\n{trace['rounds']} rounds, {time.perf_counter() - start:.1f} s", file=sys.stderr)
