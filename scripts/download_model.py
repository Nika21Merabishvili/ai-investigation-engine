# scripts/download_model.py
"""Download the embedding model into models/ so the Docker image ships with it.
Run from the repo root: python -m scripts.download_model"""
from fastembed import TextEmbedding

from app import config

if __name__ == "__main__":
    TextEmbedding(model_name=config.EMBED_MODEL, cache_dir=config.MODEL_CACHE_DIR)
    print(f"{config.EMBED_MODEL} ready in {config.MODEL_CACHE_DIR}/")