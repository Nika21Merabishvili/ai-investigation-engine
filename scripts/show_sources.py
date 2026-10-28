# scripts/show_sources.py
"""Show the chunks hybrid search sends to the LLM for a question, numbered like the prompt (no LLM call).

Run from the repo root:  python -m scripts.show_sources "When did the 18 March incident start?"
Tells a retrieval miss (the right document is not in the list) from a model miss (it is, but was ignored).
"""
import sys

from app.answer import TOP_K
from app.db import get_conn
from app.search import hybrid_search

question = " ".join(sys.argv[1:])
if not question:
    sys.exit('Usage: python -m scripts.show_sources "your question"')

with get_conn() as conn:
    chunks = hybrid_search(conn, question, k=TOP_K)

print(f"{'S#':<4} {'dense':>6} {'rrf':>7}  document")
for i, chunk in enumerate(chunks, start=1):
    dense = f"{chunk['dense_score']:.3f}" if chunk["dense_score"] is not None else "-"
    print(f"S{i:<3} {dense:>6} {chunk['score']:.4f}  {chunk['document_title'][:60]}")
