"""
Hybrid retrieval: dense (ChromaDB) + sparse (BM25), fused with Reciprocal
Rank Fusion (RRF).

hybrid_retrieve(query, case_id, top_k=10, doc_ids=None) → list[dict]
invalidate_case(case_id)  — drop the cached BM25 index after ingest/delete

Each returned dict:
    {
        "text":        str,
        "doc_id":      str,
        "filename":    str,
        "page_number": int,
        "chunk_index": int,
        "score":       float,   # RRF score, higher is better
    }
"""

import logging
import re
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Optional, cast

from chromadb.api.types import Where
from rank_bm25 import BM25Okapi

from rag.embeddings import encode
from rag.vector_store import get_case_collection

logger = logging.getLogger("lexmind.retrieval")

_RRF_K = 60          # standard RRF damping constant
_POOL_FACTOR = 2     # each retriever contributes top_k * this candidates
_TOKEN = re.compile(r"\w+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


# ---------------------------------------------------------------------------
# BM25 index cache — one per case, rebuilt only when the case changes
# ---------------------------------------------------------------------------
@dataclass
class _SparseIndex:
    count: int                     # collection size when built
    bm25: BM25Okapi
    ids: list[str]
    texts: list[str]
    metas: list[Mapping[str, Any]]


_cache: dict[str, _SparseIndex] = {}
_cache_lock = threading.Lock()


def invalidate_case(case_id: str) -> None:
    """Forget the cached BM25 index for a case (call after ingest/delete)."""
    with _cache_lock:
        _cache.pop(case_id, None)


def _sparse_index(case_id: str, collection: Any, count: int) -> _SparseIndex:
    with _cache_lock:
        cached = _cache.get(case_id)
        # The count check also catches changes made by another process
        if cached is not None and cached.count == count:
            return cached

    data = collection.get(include=["documents", "metadatas"])
    texts: list[str] = data.get("documents") or []
    index = _SparseIndex(
        count=count,
        bm25=BM25Okapi([_tokenize(t) or [""] for t in texts]),
        ids=list(data.get("ids") or []),
        texts=texts,
        metas=list(data.get("metadatas") or []),
    )
    with _cache_lock:
        _cache[case_id] = index
    logger.debug("Built BM25 index for case %s (%d chunks)", case_id, count)
    return index


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _meta_to_dict(document: str, metadata: Mapping[str, Any]) -> dict:
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

def hybrid_retrieve(
    query: str,
    case_id: str,
    top_k: int = 10,
    doc_ids: Optional[list[str]] = None,
    mode: Literal["hybrid", "dense", "sparse"] = "hybrid",
) -> list[dict]:
    """
    Retrieve the top_k most relevant chunks from case_{case_id}.

    Dense (embedding) and sparse (BM25 keyword) rankings are each computed
    over a candidate pool, then fused with RRF: score = Σ 1 / (60 + rank).
    Chunks found by both retrievers rise to the top.

    doc_ids, if given, restricts results to those documents.
    mode "dense" / "sparse" uses one retriever only (for evaluation).
    Returns [] if the collection does not exist or contains no documents.
    """
    collection = get_case_collection(case_id)
    if collection is None:
        logger.warning("Collection case_%s does not exist — returning empty.", case_id)
        return []

    total = collection.count()
    if total == 0:
        return []

    pool = min(top_k * _POOL_FACTOR, total)
    allowed = set(doc_ids) if doc_ids else None
    chunks: dict[str, dict] = {}      # chunk id → chunk dict
    scores: dict[str, float] = {}     # chunk id → fused score

    def _add(chunk_id: str, rank: int, text: str, meta: Mapping[str, Any]) -> None:
        chunks.setdefault(chunk_id, _meta_to_dict(text, meta))
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (_RRF_K + rank)

    # ------------------------------------------------------------------
    # Step 1 — Dense retrieval via ChromaDB
    # ------------------------------------------------------------------
    dense_ids: list[str] = []
    if mode != "sparse":
        dense = collection.query(
            query_embeddings=[encode([query])[0]],
            n_results=pool,
            include=["documents", "metadatas"],
            where=cast(Where, {"doc_id": {"$in": sorted(allowed)}}) if allowed else None,
        )
        dense_ids   = (dense.get("ids") or [[]])[0]
        dense_texts = (dense.get("documents") or [[]])[0]
        dense_metas = (dense.get("metadatas") or [[]])[0]
        for rank, (cid, text, meta) in enumerate(zip(dense_ids, dense_texts, dense_metas), start=1):
            _add(cid, rank, text, meta)

    # ------------------------------------------------------------------
    # Step 2 — Sparse retrieval via cached BM25
    # ------------------------------------------------------------------
    query_tokens = _tokenize(query)
    if query_tokens and mode != "dense":
        index = _sparse_index(case_id, collection, total)
        bm25_scores = index.bm25.get_scores(query_tokens)
        order = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)
        rank = 0
        for i in order:
            if bm25_scores[i] <= 0 or rank >= pool:
                break
            if allowed and index.metas[i].get("doc_id") not in allowed:
                continue
            rank += 1
            _add(index.ids[i], rank, index.texts[i], index.metas[i])

    # ------------------------------------------------------------------
    # Step 3 — Fuse and deduplicate (by id, then by identical text)
    # ------------------------------------------------------------------
    ranked: list[dict] = []
    seen_text: set[str] = set()
    for cid in sorted(scores, key=lambda c: scores[c], reverse=True):
        chunk = chunks[cid]
        if chunk["text"] in seen_text:
            continue
        seen_text.add(chunk["text"])
        ranked.append({**chunk, "score": round(scores[cid], 6)})
        if len(ranked) >= top_k:
            break

    logger.debug(
        "hybrid_retrieve: dense=%d fused=%d case=%s",
        len(dense_ids), len(ranked), case_id,
    )
    return ranked
