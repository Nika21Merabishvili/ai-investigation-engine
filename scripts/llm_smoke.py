# scripts/llm_smoke.py
"""One real call to Gemini: checks the key, the model ID and JSON mode.

Run from the repo root:  python -m scripts.llm_smoke
"""
import json
import time

from app import config
from app.llm import chat_json

messages = [
    {"role": "system", "content": 'Reply with a JSON object only, shaped like {"ok": true, "greeting": "..."}.'},
    {"role": "user", "content": "Greet a developer who is testing their app, in one short sentence."},
]

start = time.perf_counter()
reply = chat_json(messages)
elapsed = time.perf_counter() - start

print(f"model:   {config.GEMINI_MODEL}")
print(f"seconds: {elapsed:.1f}")
print(f"raw:     {reply}")
print(f"parsed:  {json.loads(reply)}")
