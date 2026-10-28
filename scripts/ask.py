# scripts/ask.py
"""Ask one question in simple mode and print the answer JSON.

Run from the repo root:  python -m scripts.ask "What caused the March payment incident?"
"""
import json
import sys
import time

from app.answer import answer_question
from app.db import get_conn

question = " ".join(sys.argv[1:])
if not question:
    sys.exit('Usage: python -m scripts.ask "your question"')

start = time.perf_counter()
with get_conn() as conn:
    result = answer_question(conn, question)
print(json.dumps(result, indent=2, ensure_ascii=False, default=str))  # default=str: in case ids are UUIDs
print(f"\n{time.perf_counter() - start:.1f} s", file=sys.stderr)
