"""eval/chunking_eval.py

Compare paragraph vs fixed chunking on the context paragraphs of the 200 retrieval questions.
LOCAL DATABASE ONLY: refuses to run against Neon.

Run from the repo root, Docker Postgres up:
    python -m eval.chunking_eval            # builds chunks_experiment if it is empty, then evaluates
    python -m eval.chunking_eval --rebuild  # rebuild after changing a chunker

Embeddings go through EmbeddingCache, but the cache is never saved here, so this is safe
to run while scripts.ingest_bulk uploads to Neon in another terminal.
"""
import json
import sys
from pathlib import Path

from pgvector import HalfVector

from app import db
from app.embed import embed_passages, embed_query
from app.ingest import fixed_chunks, paragraph_chunks
from eval.metrics import mrr, recall_at_k
from scripts.embedding_cache import EmbeddingCache

QUESTIONS_PATH = Path("eval/retrieval_questions.jsonl")
HOTPOT_PATH = Path("data/hotpot_paragraphs.jsonl")
K = 5
CANDIDATES = 30  # chunks fetched per question before collapsing them to distinct titles
STRATEGIES = {"paragraph": paragraph_chunks, "fixed": fixed_chunks}

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS chunks_experiment (
    id             BIGSERIAL PRIMARY KEY,
    paragraph_hash TEXT NOT NULL,
    title          TEXT NOT NULL,
    strategy       TEXT NOT NULL CHECK (strategy IN ('paragraph', 'fixed')),
    chunk_index    INT  NOT NULL,
    text           TEXT NOT NULL,
    embedding      halfvec(384) NOT NULL
)
"""


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def question_paragraphs(questions: list[dict]) -> list[dict]:
    """The paragraphs listed in the questions' paragraph_hashes, exactly as they were loaded."""
    wanted = {h for q in questions for h in q["paragraph_hashes"]}
    paragraphs = []
    with HOTPOT_PATH.open(encoding="utf-8") as f:
        for line in f:
            p = json.loads(line)
            if p["content_hash"] in wanted:
                paragraphs.append(p)
    if len(paragraphs) < len(wanted):
        print(f"Warning: {len(wanted) - len(paragraphs)} paragraph hashes not found in {HOTPOT_PATH}")
    return paragraphs


def build(conn, paragraphs: list[dict]) -> None:
    rows = []
    for p in paragraphs:
        for strategy, chunker in STRATEGIES.items():
            for i, chunk in enumerate(chunker(p["text"], p["title"])):
                rows.append((p["content_hash"], p["title"], strategy, i, chunk))

    # Paragraph chunks are the same texts ingest_bulk already embedded, so they come from
    # the cache; only the pieces of split paragraphs are new. The cache is not saved here.
    cache = EmbeddingCache()
    print(f"{len(rows):,} chunks from {len(paragraphs):,} paragraphs (embedding only the uncached ones) ...")
    vectors = cache.embed([row[4] for row in rows], embed_passages)

    with conn.cursor() as cur:
        cur.execute("TRUNCATE chunks_experiment")
        cur.executemany(
            "INSERT INTO chunks_experiment (paragraph_hash, title, strategy, chunk_index, text, embedding) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            [(*row, HalfVector(vector)) for row, vector in zip(rows, vectors)],
        )
    conn.commit()


def ranked_titles(cur, qvec: HalfVector, strategy: str) -> list[str]:
    """Top chunks for one strategy, collapsed to distinct titles in rank order.

    No index on this small table, so this is exact search: no ANN noise in the comparison.
    """
    cur.execute(
        "SELECT title FROM chunks_experiment WHERE strategy = %s "
        "ORDER BY embedding <=> %s LIMIT %s",
        (strategy, qvec, CANDIDATES),
    )
    # dict keeps insertion order, so each title stays at its first (best) position.
    return list(dict.fromkeys(title for (title,) in cur.fetchall()))


def main() -> None:
    questions = read_jsonl(QUESTIONS_PATH)
    with db.get_conn() as conn:
        host = conn.info.host or ""
        if "neon.tech" in host:
            sys.exit("Refusing to run: this experiment is local-only, and this connection is to Neon.")
        print(f"Database: {conn.info.dbname} on {host}")

        conn.execute(CREATE_TABLE)
        conn.commit()
        count = conn.execute("SELECT count(*) FROM chunks_experiment").fetchone()[0]
        if count == 0 or "--rebuild" in sys.argv:
            build(conn, question_paragraphs(questions))

        stats = {s: {"chunks": 0, "paragraphs": 0, "split": 0} for s in STRATEGIES}
        for strategy, n in conn.execute(
            "SELECT strategy, count(*) FROM chunks_experiment GROUP BY strategy, paragraph_hash"
        ).fetchall():
            stats[strategy]["chunks"] += n
            stats[strategy]["paragraphs"] += 1
            stats[strategy]["split"] += n > 1

        qvecs = [HalfVector(embed_query(q["question"])) for q in questions]

        print(f"\n| Strategy | Chunks | Paragraphs split | Recall@{K} | MRR |")
        print("| --- | --- | --- | --- | --- |")
        with conn.cursor() as cur:
            for strategy in STRATEGIES:
                recalls, rrs = [], []
                for q, qvec in zip(questions, qvecs):
                    ranked = ranked_titles(cur, qvec, strategy)
                    recalls.append(recall_at_k(ranked, q["gold_titles"], K))
                    rrs.append(mrr(ranked, q["gold_titles"]))
                s = stats[strategy]
                print(
                    f"| {strategy} | {s['chunks']:,} | {s['split']} of {s['paragraphs']} "
                    f"| {sum(recalls) / len(recalls):.3f} | {sum(rrs) / len(rrs):.3f} |"
                )


if __name__ == "__main__":
    main()
