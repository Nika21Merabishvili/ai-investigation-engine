# app/ingest.py
"""Document ingestion. For now: text normalization and the content hash used for dedup.
Loaders, chunkers and ingest() are added here on Day 2."""
import hashlib


def normalize_text(text: str) -> str:
    """Collapse every run of whitespace (spaces, tabs, newlines) to one space and trim the ends."""
    return " ".join(text.split())


def content_hash(text: str) -> str:
    """SHA-256 of the normalized text, as 64 hex characters. Same hash = duplicate document."""
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()
