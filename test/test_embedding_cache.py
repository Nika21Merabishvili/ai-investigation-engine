# tests/test_embedding_cache.py
import numpy as np

from scripts.embedding_cache import EmbeddingCache


def fake_embed(calls: list):
    """Stands in for the model: records what it was asked, returns [len(text), 1, 0] per text."""
    def embed(texts: list[str]) -> np.ndarray:
        calls.append(list(texts))
        return np.array([[len(t), 1.0, 0.0] for t in texts], dtype=np.float32)
    return embed


def test_cached_texts_are_not_embedded_again_after_reload(tmp_path):
    calls = []
    cache = EmbeddingCache(tmp_path / "emb.npz")
    first = cache.embed(["a", "bb"], fake_embed(calls))
    cache.save()

    reloaded = EmbeddingCache(tmp_path / "emb.npz")  # fresh object, reads the file
    second = reloaded.embed(["bb", "ccc", "a"], fake_embed(calls))

    assert calls == [["a", "bb"], ["ccc"]]  # only the new text reached the model
    assert np.array_equal(second[0], first[1]) and np.array_equal(second[2], first[0])  # order kept
    assert len(reloaded) == 3


def test_batches_and_duplicates(tmp_path):
    calls = []
    vectors = EmbeddingCache(tmp_path / "emb.npz").embed(
        ["x", "y", "x", "z", "w", "v"], fake_embed(calls), batch_size=2
    )
    assert [len(c) for c in calls] == [2, 2, 1]  # 5 distinct texts in batches of 2
    assert vectors.shape == (6, 3)  # still one row per input text


def test_saves_on_its_own_every_save_every_vectors(tmp_path):
    path = tmp_path / "emb.npz"
    cache = EmbeddingCache(path, save_every=2)
    cache.embed(["a", "b", "c"], fake_embed([]), batch_size=2)
    assert path.exists() and cache.unsaved == 1  # saved after the first batch; "c" still pending
