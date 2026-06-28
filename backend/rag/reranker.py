"""
Cohere reranker.

rerank(query, candidates, top_n=3) → list[dict]

Takes the merged candidates from hybrid_retrieve and returns the top_n
most relevant ones reordered by Cohere's relevance score.
Falls back to candidates[:top_n] if Cohere is unavailable or errors.
"""

import logging
import os

import cohere

logger = logging.getLogger("lexmind.reranker")

_COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")

# Client is created lazily so missing key doesn't crash import.
_client: cohere.Client | None = None


def _get_client() -> cohere.Client | None:
    global _client
    if _client is None and _COHERE_API_KEY:
        _client = cohere.Client(api_key=_COHERE_API_KEY)
    return _client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def rerank(query: str, candidates: list[dict], top_n: int = 3) -> list[dict]:
    """
    Rerank *candidates* using Cohere's rerank endpoint.

    Parameters
    ----------
    query      : The user query string.
    candidates : List of dicts with at least a "text" key.
    top_n      : How many top candidates to return.

    Returns
    -------
    Up to *top_n* candidates sorted by Cohere relevance, highest first.
    Falls back to candidates[:top_n] on any error.
    """
    if not candidates:
        return []

    effective_n = min(top_n, len(candidates))

    client = _get_client()
    if client is None:
        logger.warning("COHERE_API_KEY not set — skipping rerank, returning top %d.", effective_n)
        return candidates[:effective_n]

    texts = [c["text"] for c in candidates]

    try:
        response = client.rerank(
            model="rerank-english-v3.0",
            query=query,
            documents=texts,
            top_n=effective_n,
        )

        reranked = [candidates[r.index] for r in response.results]

        logger.debug("Cohere rerank returned %d results.", len(reranked))
        return reranked

    except Exception as exc:
        logger.warning("Cohere rerank failed (%s) — falling back to first %d candidates.", exc, effective_n)
        return candidates[:effective_n]
