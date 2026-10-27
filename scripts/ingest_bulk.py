# scripts/ingest_bulk.py
"""Load the seed corpus with embeddings: the NovaPay files and the HotpotQA paragraphs.

Run from the repo root, Docker Postgres up:
    python -m scripts.ingest_bulk company               # the 20 files in data/company/
    python -m scripts.ingest_bulk hotpot --limit 1000   # quick check on 1,000 paragraphs
    python -m scripts.ingest_bulk hotpot                # the rest (skips what's already loaded)
    python -m scripts.ingest_bulk all .env.neon         # later: same rows into Neon, from the cache

Safe to stop (Ctrl+C) and rerun: documents already in the database are skipped,
and every embedding is kept in data/embeddings.npz, so nothing is embedded twice.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from uuid import uuid4

parser = argparse.ArgumentParser(description="Load company files and HotpotQA paragraphs.")
parser.add_argument("what", choices=["company", "hotpot", "all"])
parser.add_argument("env_file", nargs="?", help="default .env (local); .env.neon for Neon")
parser.add_argument("--limit", type=int, help="load at most this many new HotpotQA paragraphs")
args = parser.parse_args()

# config.py reads ENV_FILE at import time, so it must be set before importing app.
if args.env_file:
    if not Path(args.env_file).is_file():
        sys.exit(f"Env file not found: {args.env_file}")
    os.environ["ENV_FILE"] = args.env_file

from pgvector import HalfVector  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402

from app import db  # noqa: E402
from app.embed import embed_passages  # noqa: E402
from app.ingest import SUPPORTED_FORMATS, content_hash, ingest, load_file  # noqa: E402
from scripts.embedding_cache import EmbeddingCache  # noqa: E402

COMPANY_DIR = Path("data/company")
HOTPOT_PATH = Path("data/hotpot_paragraphs.jsonl")
INSERT_BATCH = 1024  # paragraphs per database commit (4 embedding batches of 256)

INSERT_DOCUMENT = """
    INSERT INTO documents (id, source, external_id, title, file_format, content_hash, is_protected, metadata)
    VALUES (%s, 'hotpotqa', %s, %s, 'txt', %s, true, %s)"""
INSERT_CHUNK = """
    INSERT INTO chunks (document_id, chunk_index, strategy, text, text_hash, embedding)
    VALUES (%s, 0, 'paragraph', %s, %s, %s)"""


def load_company(conn, cache: EmbeddingCache) -> None:
    """One file at a time through ingest(): the same path an uploaded file takes."""
    files = sorted(p for p in COMPANY_DIR.glob("*") if p.suffix.lower() in SUPPORTED_FORMATS)
    if not files:
        sys.exit(f"No documents in {COMPANY_DIR}/ (run python -m scripts.build_company_docs)")
    print(f"Company: {len(files)} files")
    for path in files:
        status, _, n_chunks = ingest(conn, load_file(path), source="company", protected=True,
                                     embed=lambda texts: cache.embed(texts, embed_passages))
        print(f"  {status:<9} {n_chunks:>2} chunks  {path.name}")


def load_hotpot(conn, cache: EmbeddingCache, limit: int | None) -> None:
    """Every paragraph is one document with one chunk; rows go in with executemany."""
    if not HOTPOT_PATH.exists():
        sys.exit(f"{HOTPOT_PATH} not found (run python -m scripts.build_hotpot)")
    loaded = {row[0] for row in conn.execute("SELECT content_hash FROM documents")}
    conn.commit()  # end the read; from here on, each commit saves one batch

    todo = []
    with HOTPOT_PATH.open(encoding="utf-8") as f:
        for line in f:
            p = json.loads(line)
            digest = content_hash(p["text"])
            if digest not in loaded:
                todo.append((digest, p))
    if limit is not None:
        todo = todo[:limit]
    print(f"HotpotQA: {len(todo):,} paragraphs to load ({len(loaded):,} documents already in the database)")

    started = time.perf_counter()
    for start in range(0, len(todo), INSERT_BATCH):
        batch = todo[start:start + INSERT_BATCH]
        texts = [f"Title: {p['title']}\n{p['text']}" for _, p in batch]  # same format as the chunkers
        vectors = cache.embed(texts, embed_passages)  # only uncached texts are embedded

        documents, chunks = [], []
        for (digest, p), text, vector in zip(batch, texts, vectors):
            doc_id = uuid4()  # made here, so the chunk rows can point at it without a RETURNING
            documents.append((doc_id, digest, p["title"], digest, Jsonb({"split": p["split"]})))
            chunks.append((doc_id, text, content_hash(text), HalfVector(vector)))
        with conn.cursor() as cur:
            cur.executemany(INSERT_DOCUMENT, documents)
            cur.executemany(INSERT_CHUNK, chunks)
        conn.commit()

        done = start + len(batch)
        rate = done / (time.perf_counter() - started)
        print(f"  {done:>7,} / {len(todo):,}  ({rate:,.0f}/s, about {(len(todo) - done) / rate / 60:.0f} min left)")


def main() -> None:
    cache = EmbeddingCache()
    try:
        with db.get_conn() as conn:
            print(f"Database: {conn.info.dbname} on {conn.info.host} | cached embeddings: {len(cache):,}")
            if args.what in ("company", "all"):
                load_company(conn, cache)
            if args.what in ("hotpot", "all"):
                load_hotpot(conn, cache, args.limit)
            rows = conn.execute(
                "SELECT d.source, count(DISTINCT d.id), count(c.id) FROM documents d "
                "LEFT JOIN chunks c ON c.document_id = d.id GROUP BY d.source ORDER BY d.source"
            ).fetchall()
    finally:
        cache.save()  # also on Ctrl+C or an error: vectors already computed are kept
    for source, n_docs, n_chunks in rows:
        print(f"{source:<9} {n_docs:>7,} documents  {n_chunks:>7,} chunks")
    print(f"Cache: {len(cache):,} embeddings in {cache.path}")


if __name__ == "__main__":
    main()
