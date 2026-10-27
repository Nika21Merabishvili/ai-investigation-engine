# scripts/check_chunks.py
"""Quick look at how paragraph_chunks splits real files.

Run from the repo root:
    python -m scripts.check_chunks <file.md> <file.docx> <file.pdf>
"""
import sys

from app.ingest import load_file, paragraph_chunks

for path in sys.argv[1:]:
    doc = load_file(path)
    chunks = paragraph_chunks(doc.text, doc.title)
    sizes = [len(chunk.split("\n", 1)[1].split()) for chunk in chunks]
    print(f"\n=== {path}  ({doc.file_format}, title: {doc.title!r})")
    print(f"{len(chunks)} chunks, body words per chunk: {sizes}")
    print("--- first chunk:")
    print(chunks[0] if chunks else "(none)")
