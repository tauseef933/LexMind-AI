"""
Document Agent

Uses hybrid RAG retrieval + Cohere reranking + Groq LLM to answer
questions grounded strictly in case documents.

run(query, case_id) → dict
"""

import logging
import os
import re

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from rag.retrieval import hybrid_retrieve
from rag.reranker import rerank

logger = logging.getLogger("lexmind.document_agent")

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

from config import GROQ_MODEL


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

def run(query: str, case_id: str) -> dict:
    try:
        # 1. Hybrid retrieval
        candidates = hybrid_retrieve(query, case_id, top_k=10)
        if not candidates:
            return {
                "answer": "No documents have been ingested for this case yet.",
                "sources": [],
                "agent": "document_agent",
            }

        # 2. Rerank → top 3
        top_chunks = rerank(query, candidates, top_n=3)

        # 3. Build context and fill prompt
        context = _build_context(top_chunks)
        filled_prompt = RAG_PROMPT.format(
            retrieved_chunks=context,
            query=query,
            filename="{filename}",   # keep placeholders literal — they appear in the rules text
            page="{page}",
        )

        # 4. Call Groq
        llm = ChatGroq(
            model=GROQ_MODEL,
            api_key=os.getenv("GROQ_API_KEY", ""),
            temperature=0,
        )
        messages = [
            SystemMessage(content="You are a precise legal document analyst."),
            HumanMessage(content=filled_prompt),
        ]
        response = llm.invoke(messages)
        answer: str = response.content

        # 5. Hallucination guard — verify citations exist in retrieved chunks
        verified_sources = _verify_sources(answer, top_chunks)

        logger.info("document_agent answered query for case %s, sources=%d", case_id, len(verified_sources))
        return {
            "answer": answer,
            "sources": verified_sources,
            "agent": "document_agent",
        }

    except Exception as exc:
        logger.error("document_agent error: %s", exc, exc_info=True)
        return {"error": str(exc), "agent": "document_agent"}
