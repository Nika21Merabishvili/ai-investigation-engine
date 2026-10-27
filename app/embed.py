# app/embed.py
"""fastembed wrapper: the one place where text becomes a 384-number vector.

embed_passages() is for chunks, embed_query() for questions. The model loads once,
on first use, from config.MODEL_CACHE_DIR (baked into the Docker image by
scripts/download_model.py, so the live app never downloads it).
"""
from functools import lru_cache

import numpy as np
from fastembed import TextEmbedding

from app import config

DIM = 384         # bge-small-en-v1.5 output size; must match halfvec(384) in schema.sql
BATCH_SIZE = 256  # texts per model run

# BGE v1.5 was trained with this instruction in front of short search queries.
# Passages get no prefix. fastembed 0.9 does not add it by itself, so we do.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


@lru_cache(maxsize=1)
def _model() -> TextEmbedding:
    """Load the model on first use and keep it (loading takes a second or two)."""
    return TextEmbedding(model_name=config.EMBED_MODEL, cache_dir=config.MODEL_CACHE_DIR)


def embed_passages(texts: list[str]) -> np.ndarray:
    """Embed chunk texts. Returns float32, shape (len(texts), 384), one unit-length row per text."""
    if not texts:
        return np.empty((0, DIM), dtype=np.float32)
    vectors = np.array(list(_model().passage_embed(texts, batch_size=BATCH_SIZE)), dtype=np.float32)
    if vectors.shape[1] != DIM:
        raise ValueError(f"{config.EMBED_MODEL} returns {vectors.shape[1]} numbers, schema expects {DIM}")
    return vectors


def embed_query(question: str) -> np.ndarray:
    """Embed one search question. Returns float32, shape (384,)."""
    return np.array(next(iter(_model().query_embed(QUERY_PREFIX + question))), dtype=np.float32)
