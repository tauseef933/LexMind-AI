"""
Embedding helper — loads the SentenceTransformer model once at import time
so every call reuses the same in-memory model.
"""

from sentence_transformers import SentenceTransformer

_MODEL_NAME = "all-MiniLM-L6-v2"

# Loaded once; subsequent imports receive the cached module object.
_model = SentenceTransformer(_MODEL_NAME)


def encode(texts: list[str]) -> list[list[float]]:
    """Return a list of embedding vectors, one per input text."""
    vectors = _model.encode(texts, convert_to_numpy=True)
    return [v.tolist() for v in vectors]
