"""
Embedding helper — ONNX MiniLM (same model as all-MiniLM-L6-v2).

Uses Chroma's ONNXRuntime path instead of sentence-transformers/torch so the
backend can start on Windows machines where Smart App Control blocks PyTorch.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from functools import lru_cache

logger = logging.getLogger("lexmind.embeddings")


@lru_cache(maxsize=1)
def _encoder():
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

    logger.info("Loading ONNX MiniLM embedding model …")
    return ONNXMiniLM_L6_V2()


def encode(texts: list[str]) -> list[Sequence[float]]:
    """Return a list of embedding vectors, one per input text."""
    if not texts:
        return []
    vectors = _encoder()(texts)
    return [list(map(float, v)) for v in vectors]
