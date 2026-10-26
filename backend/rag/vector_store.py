"""
Single shared ChromaDB client — one PersistentClient per process.

get_client()                → chromadb client
get_case_collection(case_id) → existing collection for the case, or None
get_or_create_case_collection(case_id) → collection (created if missing)
get_case_chunks(case_id)     → every chunk of the case in reading order
format_chunks(chunks)        → chunks as prompt text with [Source: …] tags
get_case_context(case_id, max_chars) → reading-order context within a size budget
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


def get_case_chunks(case_id: str) -> list[dict]:
    """
    Every chunk of the case in reading order (document, page, position).
    Each dict: text, doc_id, filename, page_number, chunk_index.
    """
    collection = get_case_collection(case_id)
    if collection is None:
        return []
    try:
        results = collection.get(include=["documents", "metadatas"])
    except Exception as exc:
        logger.warning("ChromaDB fetch failed: %s", exc)
        return []
    chunks = [
        {
            "text": text,
            "doc_id": str(meta.get("doc_id") or ""),
            "filename": str(meta.get("filename") or "unknown"),
            "page_number": int(str(meta.get("page_number") or 1)),
            "chunk_index": int(str(meta.get("chunk_index") or 0)),
        }
        for text, meta in zip(results.get("documents") or [], results.get("metadatas") or [])
    ]
    chunks.sort(key=lambda c: (str(c["filename"]).lower(), c["page_number"], c["chunk_index"]))
    return chunks


def format_chunks(chunks: list[dict]) -> str:
    """Prompt-ready text: each chunk prefixed with its citation tag."""
    return "\n\n".join(f"[Source: {c['filename']}, Page {c['page_number']}]\n{c['text']}" for c in chunks)


def context_chars() -> int:
    """Character budget for full-document prompts (≈ 4 characters per token)."""
    return int(os.getenv("DOC_CONTEXT_CHARS", "24000"))


def get_case_context(case_id: str, max_chars: Optional[int] = None) -> str:
    """
    The case's documents in reading order as one prompt-ready string.

    If everything fits in max_chars it is returned whole. Otherwise passages
    are sampled evenly across ALL documents and pages (instead of only the
    first ones), and a note tells the model the text is incomplete.
    Returns "" if the case has no chunks.
    """
    chunks = get_case_chunks(case_id)
    if not chunks:
        return ""
    budget = max_chars or context_chars()
    full = format_chunks(chunks)
    if len(full) <= budget:
        return full

    # Even sampling: shrink the step until the selection fits the budget
    average = len(full) / len(chunks)
    keep = max(1, int(budget / average))
    while keep > 1:
        step = len(chunks) / keep
        sample = [chunks[int(i * step)] for i in range(keep)]
        text = format_chunks(sample)
        if len(text) <= budget:
            break
        keep -= 1
    else:
        sample = chunks[:1]
        text = format_chunks(sample)[:budget]

    return (
        f"[Note: these are {len(sample)} of {len(chunks)} passages, sampled evenly across all "
        "documents. The text is incomplete — do not conclude that something is missing from the documents.]\n\n"
        + text
    )
