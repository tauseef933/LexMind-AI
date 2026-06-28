"""
Hybrid retrieval: dense (ChromaDB) + sparse (BM25) → merged + deduplicated.

hybrid_retrieve(query, case_id, top_k=10) → list[dict]

Each returned dict:
    {
        "text":        str,
        "doc_id":      str,
        "filename":    str,
        "page_number": int,
        "chunk_index": int,
    }
"""

import logging
import os

import chromadb
from rank_bm25 import BM25Okapi

from rag.embeddings import encode

logger = logging.getLogger("lexmind.retrieval")

_CHROMA_PATH = os.getenv("CHROMA_PERSIST_PATH", "./chroma_db")
_chroma_client = chromadb.PersistentClient(path=_CHROMA_PATH)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _collection_exists(case_id: str) -> bool:
    try:
        existing = [c.name for c in _chroma_client.list_collections()]
        return f"case_{case_id}" in existing
    except Exception:
        return False


def _meta_to_dict(document: str, metadata: dict) -> dict:
    return {
        "text":        document,
        "doc_id":      metadata.get("doc_id", ""),
        "filename":    metadata.get("filename", ""),
        "page_number": int(metadata.get("page_number", 1)),
        "chunk_index": int(metadata.get("chunk_index", 0)),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def hybrid_retrieve(query: str, case_id: str, top_k: int = 10) -> list[dict]:
    """
    Retrieve the top_k most relevant chunks from case_{case_id} using
    a hybrid dense + sparse approach, then deduplicate.

    Returns [] if the collection does not exist or contains no documents.
    """
    if not _collection_exists(case_id):
        logger.warning("Collection case_%s does not exist — returning empty.", case_id)
        return []

    collection = _chroma_client.get_collection(f"case_{case_id}")

    # Guard: empty collection
    total_docs = collection.count()
    if total_docs == 0:
        return []

    effective_k = min(top_k, total_docs)

    # ------------------------------------------------------------------
    # Step 1 — Dense retrieval via ChromaDB
    # ------------------------------------------------------------------
    query_vector = encode([query])[0]

    dense_results = collection.query(
        query_embeddings=[query_vector],
        n_results=effective_k,
        include=["documents", "metadatas", "distances"],
    )

    dense_chunks: list[dict] = []
    docs_list      = dense_results.get("documents", [[]])[0]
    metas_list     = dense_results.get("metadatas", [[]])[0]

    for doc_text, meta in zip(docs_list, metas_list):
        dense_chunks.append(_meta_to_dict(doc_text, meta))

    # ------------------------------------------------------------------
    # Step 2 — Sparse retrieval via BM25
    # ------------------------------------------------------------------
    all_results = collection.get(include=["documents", "metadatas"])

    all_texts  = all_results.get("documents") or []
    all_metas  = all_results.get("metadatas") or []

    tokenized_corpus = [t.lower().split() for t in all_texts]
    bm25 = BM25Okapi(tokenized_corpus)

    query_tokens = query.lower().split()
    scores       = bm25.get_scores(query_tokens)

    # Take top_k indices sorted by BM25 score descending
    ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:effective_k]

    sparse_chunks: list[dict] = [
        _meta_to_dict(all_texts[i], all_metas[i])
        for i in ranked_indices
        if scores[i] > 0  # skip zero-score results
    ]

    # ------------------------------------------------------------------
    # Step 3 — Merge and deduplicate by chunk text
    # ------------------------------------------------------------------
    seen:   set[str]  = set()
    merged: list[dict] = []

    for chunk in dense_chunks + sparse_chunks:
        key = chunk["text"]
        if key not in seen:
            seen.add(key)
            merged.append(chunk)

    logger.debug(
        "hybrid_retrieve: dense=%d sparse=%d merged=%d  case=%s",
        len(dense_chunks), len(sparse_chunks), len(merged), case_id,
    )

    return merged
