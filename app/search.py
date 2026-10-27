# app/search.py
"""Dense search, keyword search, and hybrid search fused with RRF.

Every function takes an open connection, like ingest() does. The caller opens one and reuses it:

    with get_conn() as conn:
        results = hybrid_search(conn, "What caused the March payment incident?")
"""
import re

import psycopg
from pgvector import HalfVector
from psycopg.rows import dict_row

from app.embed import embed_query

RRF_K = 60
DENSE_WEIGHT = 1.0
KEYWORD_WEIGHT = 1.0
# HNSW returns at most hnsw.ef_search rows (default 40), so asking for more gains nothing.
CANDIDATES = 40


def _or_query(question: str) -> str:
    """'Who founded NovaPay?' -> 'who | founded | novapay' (input for to_tsquery)."""
    words = re.findall(r"[^\W_]+", question.lower())   # letters and digits only, so no tsquery syntax leaks in
    return " | ".join(dict.fromkeys(words))            # dict.fromkeys drops duplicates, keeps order


DENSE_SQL = """
WITH nearest AS (
    SELECT id, document_id, text, embedding <=> %(q)s::halfvec AS distance
    FROM chunks
    ORDER BY distance            -- must order by the raw distance, or the HNSW index is skipped
    LIMIT %(n)s
)
SELECT n.id AS chunk_id, n.document_id, d.title AS document_title, n.text,
       1 - n.distance AS score   -- cosine similarity, higher is better
FROM nearest n
JOIN documents d ON d.id = n.document_id
ORDER BY n.distance
"""

# 'english' must match the config of the generated tsv column in schema.sql.
KEYWORD_SQL = """
WITH q AS (SELECT to_tsquery('english', %(tsq)s) AS query),
matches AS (
    SELECT c.id, c.document_id, c.text, ts_rank(c.tsv, q.query) AS score
    FROM chunks c, q
    WHERE c.tsv @@ q.query       -- uses the GIN index
    ORDER BY score DESC, c.id
    LIMIT %(n)s
)
SELECT m.id AS chunk_id, m.document_id, d.title AS document_title, m.text, m.score
FROM matches m
JOIN documents d ON d.id = m.document_id
ORDER BY m.score DESC, m.id
"""


def dense_search(conn: psycopg.Connection, question: str, k: int = 8) -> list[dict]:
    """Top-k chunks by cosine similarity to the question embedding."""
    q = HalfVector(embed_query(question))   # same type ingest() stores, sent via register_vector
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(DENSE_SQL, {"q": q, "n": k})
        return cur.fetchall()


def keyword_search(conn: psycopg.Connection, question: str, k: int = 8) -> list[dict]:
    """Top-k chunks matching ANY word of the question, ranked by ts_rank."""
    tsq = _or_query(question)
    if not tsq:
        return []
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(KEYWORD_SQL, {"tsq": tsq, "n": k})
        return cur.fetchall()


def rrf(rankings: list[list[int]], weights: list[float] | None = None, k: int = RRF_K) -> list[tuple[int, float]]:
    """Weighted Reciprocal Rank Fusion. YOU WRITE THIS ONE.

    rankings: one list of chunk ids per retriever, best first.
    weights:  one weight per ranking; None means every weight is 1.0.
    returns:  (chunk_id, score) pairs, highest score first.
    score(id) = sum, over the rankings that contain id, of weight / (k + rank), where rank starts at 1.
    """
    if weights is None:
        weights = [1.0] * len(rankings)
    scores: dict[int, float] = {}
    for ranking, weight in zip(rankings, weights):
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0) + weight / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def hybrid_search(conn: psycopg.Connection, question: str, k: int = 8) -> list[dict]:
    """Fuse dense and keyword results with RRF; return the top k chunks with their document titles."""
    dense = dense_search(conn, question, CANDIDATES)
    keyword = keyword_search(conn, question, CANDIDATES)

    rows = {r["chunk_id"]: r for r in keyword + dense}      # every candidate's row, by chunk id
    dense_scores = {r["chunk_id"]: r["score"] for r in dense}

    fused = rrf(
        [[r["chunk_id"] for r in dense], [r["chunk_id"] for r in keyword]],
        weights=[DENSE_WEIGHT, KEYWORD_WEIGHT],
    )

    results = []
    for chunk_id, score in fused[:k]:
        row = rows[chunk_id]
        results.append({
            "chunk_id": chunk_id,
            "document_id": row["document_id"],
            "document_title": row["document_title"],
            "text": row["text"],
            "score": score,                              # RRF score
            "dense_score": dense_scores.get(chunk_id),   # None if only keyword found it; Day 3 threshold uses this
        })
    return results
