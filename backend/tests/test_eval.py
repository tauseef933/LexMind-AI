"""Retrieval quality gate: fails if a change makes hybrid search worse on the golden set."""

import pytest

pytestmark = pytest.mark.slow


def test_hybrid_retrieval_quality(monkeypatch):
    from eval import run_eval
    from rag import reranker

    monkeypatch.setattr(reranker, "_COHERE_API_KEY", "")
    summary = run_eval.evaluate(use_rerank=False, with_llm=False)["summary"]
    hybrid = summary["retrieval"]["hybrid"]

    # Baseline when written: hit@1 0.75, hit@3 1.00, MRR 0.87
    assert hybrid["hit@3"] >= 0.95
    assert hybrid["mrr"] >= 0.80
    # Fusion should never be worse than either retriever on its own
    assert hybrid["mrr"] >= summary["retrieval"]["dense"]["mrr"]
    assert hybrid["mrr"] >= summary["retrieval"]["sparse"]["mrr"]
