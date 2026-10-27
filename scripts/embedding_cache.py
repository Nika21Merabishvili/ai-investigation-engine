# scripts/embedding_cache.py
"""Embeddings saved on disk, keyed by the hash of the embedded text.

Lives in data/embeddings.npz: two numpy arrays saved together in one file,
`hashes` (row i's text hash) and `vectors` (row i's 384 numbers). (.npy holds one
array; .npz holds several named ones, which is what "keyed by hash" needs.)

Any text embedded once is never embedded again: rerunning a load, loading Neon
after the local database, and the chunking experiment all reuse these vectors.
"""
import os
from pathlib import Path
from typing import Callable

import numpy as np

from app.ingest import content_hash

DEFAULT_PATH = Path("data/embeddings.npz")


class EmbeddingCache:
    def __init__(self, path: str | Path = DEFAULT_PATH, save_every: int = 10_000):
        self.path = Path(path)
        self.save_every = save_every  # write to disk after this many new vectors (crash safety)
        self.unsaved = 0              # new vectors not on disk yet
        self._vectors: dict[str, np.ndarray] = {}
        if self.path.exists():
            with np.load(self.path) as data:
                hashes, vectors = data["hashes"], data["vectors"]
            if len(hashes) != len(vectors):
                raise ValueError(f"{self.path} is damaged (hash and vector counts differ); delete it")
            self._vectors = dict(zip(hashes.tolist(), vectors))

    def __len__(self) -> int:
        return len(self._vectors)

    def embed(self, texts: list[str], embed_fn: Callable[[list[str]], np.ndarray],
              batch_size: int = 256) -> np.ndarray:
        """Return one vector per text, in the same order.

        Only texts whose hash isn't cached go to embed_fn, in batches of batch_size;
        the same text twice in one call is embedded once.
        """
        hashes = [content_hash(t) for t in texts]
        missing = {}  # hash -> text, in first-seen order
        for h, t in zip(hashes, texts):
            if h not in self._vectors:
                missing.setdefault(h, t)

        todo = list(missing.items())
        for start in range(0, len(todo), batch_size):
            batch = todo[start:start + batch_size]
            vectors = embed_fn([t for _, t in batch])
            for (h, _), v in zip(batch, vectors):
                self._vectors[h] = v
            self.unsaved += len(batch)
            if self.unsaved >= self.save_every:
                self.save()

        if not hashes:
            return np.empty((0, 0), dtype=np.float32)
        return np.stack([self._vectors[h] for h in hashes])

    def save(self) -> None:
        """Rewrite the file. Writes a temporary file first, then renames it, so a crash
        mid-write never leaves a half-written cache behind."""
        if not self._vectors:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        hashes = list(self._vectors)
        tmp = self.path.with_name(self.path.stem + ".tmp.npz")
        np.savez(tmp, hashes=np.array(hashes), vectors=np.stack([self._vectors[h] for h in hashes]))
        os.replace(tmp, self.path)
        self.unsaved = 0
