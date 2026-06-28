"""
Research Agent

Searches the web for legal precedents via Serper API, then passes the
top-3 snippets as context to Groq for a synthesised legal research answer.

run(query, case_id) → dict
"""

import logging
import os

import requests
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger("lexmind.research_agent")

from config import GROQ_MODEL
_SERPER_URL = "https://google.serper.dev/search"

_SYSTEM = """You are a senior legal researcher. Using the provided search results,
answer the question with relevant case law, statutes, or legal precedents.
Cite the sources by their titles or URLs where possible.
If the results are insufficient, clearly state that."""


def _serper_search(query: str) -> list[dict]:
    """
    Query Serper API and return up to 5 organic result dicts with
    keys: title, snippet, link.
    Returns [] on failure.
    """
    api_key = os.getenv("SERPER_API_KEY", "")
    if not api_key:
        logger.warning("SERPER_API_KEY not set — web search skipped.")
        return []

    try:
        response = requests.post(
            _SERPER_URL,
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query + " legal precedent case law", "num": 5},
            timeout=10,
        )
        response.raise_for_status()
        organic = response.json().get("organic", [])
        return [
            {
                "title":   r.get("title", ""),
                "snippet": r.get("snippet", ""),
                "link":    r.get("link", ""),
            }
            for r in organic[:5]
        ]
    except Exception as exc:
        logger.warning("Serper search failed: %s", exc)
        return []


def _build_context(results: list[dict]) -> str:
    parts = []
    for i, r in enumerate(results[:3], start=1):
        parts.append(
            f"[Result {i}]\nTitle: {r['title']}\nURL: {r['link']}\nSnippet: {r['snippet']}"
        )
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run(query: str, case_id: str) -> dict:
    try:
        # 1. Web search
        results = _serper_search(query)
        source_urls = [r["link"] for r in results if r.get("link")]

        if not results:
            context = "No web search results available."
        else:
            context = _build_context(results)

        # 2. Synthesise with Groq
        llm = ChatGroq(
            model=GROQ_MODEL,
            api_key=os.getenv("GROQ_API_KEY", ""),
            temperature=0.1,
        )

        prompt = (
            f"Legal research question: {query}\n\n"
            f"Case context (ID): {case_id}\n\n"
            f"Web search results:\n{context}"
        )

        response = llm.invoke([
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=prompt),
        ])
        answer: str = response.content

        logger.info("research_agent answered query for case %s, sources=%d", case_id, len(source_urls))
        return {
            "answer": answer,
            "sources": source_urls,
            "agent": "research_agent",
        }

    except Exception as exc:
        logger.error("research_agent error: %s", exc, exc_info=True)
        return {"error": str(exc), "agent": "research_agent"}
