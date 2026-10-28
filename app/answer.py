# app/answer.py
"""Simple mode: retrieve -> number the sources -> prompt -> validated, cited JSON answer.

answer_question() runs five steps:
1. hybrid_search() fetches the top 8 chunks.
2. Gate: if the best dense similarity among them is below MIN_DENSE_SIMILARITY,
   return "insufficient" without calling the LLM.
3. format_sources() numbers the chunks S1..S8 and keeps an S# -> chunk map.
4. ask_llm_json() sends the prompt and parses the reply, retrying once if it is unusable.
5. finalize() drops unknown S# ids, builds the citation objects and applies the status rules.
agent.py can reuse steps 3-5.
"""
import json
import re

import psycopg

from app import config
from app.llm import LLMUnavailable, chat_json
from app.search import hybrid_search

TOP_K = 8
STATUSES = {"answered", "partial", "insufficient"}
UNREADABLE_MESSAGE = "The AI service returned an answer we could not read. Please try again."

MARKER = re.compile(r"\[(S\d+)\]")                          # [S1]
MARKER_GROUP = re.compile(r"\[(S\d+(?:\s*,\s*S\d+)*)\]")    # [S1] or [S1, S3]

# Shared with agent.py, which puts its own intro in front.
ANSWER_RULES = """Rules:
1. Put source markers after every factual sentence of "answer", like [S1] or [S2][S5]. Only cite a source that supports the sentence.
2. If the sources do not answer the question, set "status" to "insufficient", leave "answer" empty, and say what is missing in "missing". Never guess.
3. If the sources answer only part of the question, set "status" to "partial", answer that part, and list the rest in "missing".
4. Check every source for conflicts BEFORE you answer. A conflict is either:
   - two sources giving different values for the same fact (a count, an amount, a time, a duration), or
   - a source stating an old value as if it were still current, while another source says it changed.
   Put every conflict that matters to the question in "conflicts", with each claim and its sources, and mention it in "answer".
5. Keep the answer short: at most 5 sentences.

Reply with one JSON object and nothing else, in exactly this shape, filling "conflicts" before "answer":
{
  "status": "answered" or "partial" or "insufficient",
  "conflicts": [{"topic": "what the sources disagree about", "positions": [{"claim": "...", "sources": ["S1"]}, {"claim": "...", "sources": ["S3"]}]}],
  "answer": "short answer with [S#] markers",
  "citations": ["S1", "S3"],
  "missing": ["what the sources do not say"]
}
Use empty lists when there are no conflicts or nothing is missing."""

SYSTEM_PROMPT = (
    "You answer questions using ONLY the numbered sources in the user's message. Ignore anything else you know.\n\n"
    + ANSWER_RULES
)


def insufficient(missing: list[str]) -> dict:
    """The one shape every "insufficient" answer has: no answer text, no citations, no conflicts."""
    return {"status": "insufficient", "answer": "", "citations": [], "conflicts": [], "missing": missing}


def format_sources(chunks: list[dict]) -> tuple[str, dict[str, dict]]:
    """Number the chunks S1, S2, ... for the prompt. Returns (prompt text, {"S1": chunk, ...}).

    Chunk texts already start with "Title: ...", so the model sees which document each comes from.
    """
    source_map = {f"S{i}": chunk for i, chunk in enumerate(chunks, start=1)}
    text = "\n\n".join(f"[{sid}] {chunk['text']}" for sid, chunk in source_map.items())
    return text, source_map


def parse_reply(text: str) -> dict:
    """Turn the model's reply into a dict, or raise ValueError saying what is wrong with it."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("the reply contains no JSON object")
    data = json.loads(text[start:end + 1])  # skips code fences or a sentence around the object; JSONDecodeError is a ValueError
    if not isinstance(data, dict):
        raise ValueError("the reply is not a JSON object")
    if data.get("status") not in STATUSES:
        raise ValueError(f'"status" must be one of {sorted(STATUSES)}')
    if not isinstance(data.get("answer", ""), str):
        raise ValueError('"answer" must be a string')
    for key in ("citations", "conflicts", "missing"):
        if not isinstance(data.get(key, []), list):
            raise ValueError(f'"{key}" must be a list')
    return data


def ask_llm_json(messages: list[dict]) -> dict:
    """Call the LLM and parse its reply. One retry, telling the model what was wrong."""
    reply = chat_json(messages)
    try:
        return parse_reply(reply)
    except ValueError as error:
        problem = str(error)

    # One retry: show the model its own reply and what was wrong with it.
    retry = [
        *messages,
        {"role": "assistant", "content": reply},
        {"role": "user", "content": f"Your reply was not usable ({problem}). Reply again with only the JSON object in the required shape."},
    ]
    reply = chat_json(retry)
    try:
        return parse_reply(reply)
    except ValueError as error:
        raise LLMUnavailable(UNREADABLE_MESSAGE) from error


def _valid_ids(ids: object, source_map: dict[str, dict]) -> list[str]:
    """Keep the ids that are strings and exist in source_map, without duplicates, in order."""
    if not isinstance(ids, list):
        return []
    return [i for i in dict.fromkeys(i for i in ids if isinstance(i, str)) if i in source_map]


def _clean_markers(answer: str, source_map: dict[str, dict]) -> str:
    """Remove markers of unknown sources and rewrite [S1, S3] as [S1][S3]."""
    def keep_valid(match: re.Match) -> str:
        ids = [i.strip() for i in match.group(1).split(",")]
        return "".join(f"[{i}]" for i in ids if i in source_map)
    return MARKER_GROUP.sub(keep_valid, answer)


def _clean_conflicts(conflicts: list, source_map: dict[str, dict]) -> list[dict]:
    """Keep each position that has a claim and at least one valid source; keep conflicts with 2+ positions."""
    cleaned = []
    for conflict in conflicts:
        if not isinstance(conflict, dict) or not isinstance(conflict.get("positions"), list):
            continue
        positions = []
        for position in conflict["positions"]:
            if not isinstance(position, dict) or not isinstance(position.get("claim"), str):
                continue
            sources = _valid_ids(position.get("sources"), source_map)
            if sources:
                positions.append({"claim": position["claim"], "sources": sources})
        if len(positions) >= 2:
            cleaned.append({"topic": str(conflict.get("topic", "")), "positions": positions})
    return cleaned


def finalize(data: dict, source_map: dict[str, dict]) -> dict:
    """Validate the parsed reply against the real sources and build the answer JSON of the API."""
    missing = [m for m in data.get("missing", []) if isinstance(m, str) and m.strip()]
    if data["status"] == "insufficient":
        return insufficient(missing or ["The sources do not answer the question."])

    answer = _clean_markers(data.get("answer", ""), source_map)
    in_answer = MARKER.findall(answer)  # only valid ids are left after cleaning
    if not in_answer:
        # An answer with no valid citation is unsupported, so it is withheld (decision D5).
        return insufficient(missing + ["The answer cited no valid source, so it was withheld."])

    conflicts = _clean_conflicts(data.get("conflicts", []), source_map)
    cited = set(in_answer) | set(_valid_ids(data.get("citations"), source_map))
    cited |= {sid for conflict in conflicts for position in conflict["positions"] for sid in position["sources"]}

    citations = [
        {
            "id": sid,
            "document_title": source_map[sid]["document_title"],
            "chunk_id": source_map[sid]["chunk_id"],
            "text": source_map[sid]["text"],
        }
        for sid in sorted(cited, key=lambda s: int(s[1:]))  # S2 before S10
    ]
    return {"status": data["status"], "answer": answer, "citations": citations, "conflicts": conflicts, "missing": missing}


def answer_question(conn: psycopg.Connection, question: str) -> dict:
    """Simple mode: answer one question from the top chunks, with citations."""
    chunks = hybrid_search(conn, question, k=TOP_K)
    best = max((c["dense_score"] for c in chunks if c["dense_score"] is not None), default=0.0)
    if not chunks or best < config.MIN_DENSE_SIMILARITY:
        return insufficient(["No document is close enough to the question."])

    sources, source_map = format_sources(chunks)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Sources:\n\n{sources}\n\nQuestion: {question}"},
    ]
    return finalize(ask_llm_json(messages), source_map)