"""
Document Agent

Uses hybrid RAG retrieval + Cohere reranking + Groq LLM to answer
questions grounded strictly in case documents.

run(query, case_id) → dict
"""

import logging
import re
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from llm import TokenCallback, ask_streaming, get_llm
from rag.retrieval import hybrid_retrieve
from rag.reranker import rerank

logger = logging.getLogger("lexmind.document_agent")

_CANDIDATES = 20      # chunks pulled by hybrid retrieval
_CONTEXT_CHUNKS = 5   # chunks kept after reranking and sent to the LLM

# ---------------------------------------------------------------------------
# Exact RAG prompt from spec
# ---------------------------------------------------------------------------
RAG_PROMPT = """
You are a legal document analyst. Answer the question using ONLY the
provided context. Every factual claim MUST include a citation.

Citation format: [Source: {filename}, Page {page}]

Context from case documents:
{retrieved_chunks}

Question: {query}

Rules:
1. Never state facts not in the context
2. Every claim needs a [Source: ...] citation
3. If the context doesn't contain the answer, say so clearly
4. Use precise legal language
5. Structure the response with clear headings if listing multiple points
"""


def _build_context(chunks: list[dict]) -> str:
    lines = []
    for c in chunks:
        lines.append(
            f"[Source: {c['filename']}, Page {c['page_number']}]\n{c['text']}"
        )
    return "\n\n".join(lines)


def _verify_sources(answer: str, chunks: list[dict]) -> list[dict]:
    """
    Return only the source dicts whose [Source: filename, Page N] reference
    actually appears in the LLM answer.
    """
    cited = []
    pattern = re.compile(r"\[Source:\s*(.+?),\s*Page\s*(\d+)\]", re.IGNORECASE)
    mentions = pattern.findall(answer)
    mentioned_keys = {(fn.strip().lower(), int(pg)) for fn, pg in mentions}

    for c in chunks:
        key = (c["filename"].lower(), c["page_number"])
        if key in mentioned_keys:
            cited.append(c)

    return cited


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run(query: str, case_id: str, on_token: Optional[TokenCallback] = None) -> dict:
    try:
        # 1. Hybrid retrieval (wide net), then 2. rerank down to the best few
        candidates = hybrid_retrieve(query, case_id, top_k=_CANDIDATES)
        if not candidates:
            return {
                "answer": "No documents have been ingested for this case yet.",
                "sources": [],
                "agent": "document_agent",
            }

        top_chunks = rerank(query, candidates, top_n=_CONTEXT_CHUNKS)

        # 3. Build context and fill prompt
        context = _build_context(top_chunks)
        filled_prompt = RAG_PROMPT.format(
            retrieved_chunks=context,
            query=query,
            filename="{filename}",   # keep placeholders literal — they appear in the rules text
            page="{page}",
        )

        # 4. Call Groq (streams tokens to on_token when given)
        messages = [
            SystemMessage(content="You are a precise legal document analyst."),
            HumanMessage(content=filled_prompt),
        ]
        answer = ask_streaming(get_llm(0), messages, on_token)

        # 5. Hallucination guard — verify citations exist in retrieved chunks
        verified_sources = _verify_sources(answer, top_chunks)

        logger.info("document_agent answered query for case %s, sources=%d", case_id, len(verified_sources))
        return {
            "answer": answer,
            "sources": verified_sources,
            "agent": "document_agent",
        }

    except Exception:
        logger.exception("document_agent error")
        return {"error": "Document analysis failed.", "agent": "document_agent"}
