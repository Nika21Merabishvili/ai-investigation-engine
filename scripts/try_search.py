# scripts/try_search.py
"""Show dense, keyword and hybrid results side by side for one question (database from .env).

Run: python -m scripts.try_search "What caused the March payment incident?"
"""
import sys
import time

from app.db import get_conn
from app.search import dense_search, hybrid_search, keyword_search


def show(name: str, search, conn, question: str, k: int) -> None:
    start = time.perf_counter()
    rows = search(conn, question, k)
    ms = (time.perf_counter() - start) * 1000
    print(f"\n== {name}: {len(rows)} results in {ms:.0f} ms")
    for i, r in enumerate(rows, start=1):
        body = r["text"].split("\n", 1)[-1]          # drop the "Title: ..." line
        dense = f"  dense={r['dense_score']:.3f}" if r.get("dense_score") is not None else ""
        print(f"{i:>2}. [{r['chunk_id']}] {r['document_title']}  score={r['score']:.4f}{dense}")
        print(f"     {body[:90]!r}")


def main() -> None:
    question = " ".join(sys.argv[1:]) or "What caused the March payment incident?"
    print("Question:", question)
    with get_conn() as conn:
        show("dense", dense_search, conn, question, 5)
        show("keyword", keyword_search, conn, question, 5)
        show("hybrid (RRF)", hybrid_search, conn, question, 8)


if __name__ == "__main__":
    main()
