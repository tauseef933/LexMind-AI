"""
Single shared ChromaDB client — one PersistentClient per process.

get_client()                → chromadb client
get_case_collection(case_id) → existing collection for the case, or None
get_or_create_case_collection(case_id) → collection (created if missing)
get_case_context(case_id, max_chunks)  → chunks joined into prompt context
"""

import logging
import os
from functools import lru_cache
from typing import Optional

import chromadb

import config  # noqa: F401 — normalises CHROMA_PERSIST_PATH before we read it

logger = logging.getLogger("lexmind.vector_store")


def collection_name(case_id: str) -> str:
    return f"case_{case_id}"


@lru_cache(maxsize=1)
def get_client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=os.getenv("CHROMA_PERSIST_PATH", "./chroma_db"))


def get_case_collection(case_id: str) -> Optional[chromadb.Collection]:
    try:
        return get_client().get_collection(collection_name(case_id))
    except Exception:
        return None


def get_or_create_case_collection(case_id: str) -> chromadb.Collection:
    return get_client().get_or_create_collection(
        name=collection_name(case_id),
        metadata={"hnsw:space": "cosine"},
    )


def get_case_context(case_id: str, max_chunks: int = 40) -> str:
    """
    Up to max_chunks chunks of the case as one prompt-ready string, each
    prefixed with "[filename, pN]". Returns "" if the case has no chunks.
    """
    collection = get_case_collection(case_id)
    if collection is None:
        return ""
    try:
        results = collection.get(include=["documents", "metadatas"], limit=max_chunks)
    except Exception as exc:
        logger.warning("ChromaDB fetch failed: %s", exc)
        return ""
    texts = results.get("documents") or []
    metas = results.get("metadatas") or []
    return "\n\n".join(
        f"[{meta.get('filename', 'unknown')}, p{meta.get('page_number', '?')}]\n{text}"
        for text, meta in zip(texts, metas)
    )
