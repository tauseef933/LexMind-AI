"""
Case Summary Service

generate_summary(case_id) → dict

Queries ChromaDB for all document chunks in the case, then prompts
Groq to extract structured case intelligence.
"""

import logging
import os

import chromadb
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger("lexmind.case_summary")

from config import GROQ_MODEL
_CHROMA_PATH = os.getenv("CHROMA_PERSIST_PATH", "./chroma_db")

_SYSTEM = """You are a senior legal analyst. Based on the case documents provided,
extract and structure the following information as valid JSON only (no markdown, no prose):

{
  "parties": ["list of all parties mentioned"],
  "charges_or_claims": ["list of charges, claims, or causes of action"],
  "key_dates": [{"date": "YYYY-MM-DD or description", "event": "what happened"}],
  "evidence": ["summary of key evidence items"],
  "open_issues": ["unresolved legal or factual issues"],
  "summary": "2-3 sentence plain-English summary of the case"
}

If a field cannot be determined from the documents, use an empty list or empty string."""


def _get_case_context(case_id: str, max_chunks: int = 30) -> str:
    """Pull up to max_chunks documents from ChromaDB for the case."""
    try:
        client = chromadb.PersistentClient(path=_CHROMA_PATH)
        collections = [c.name for c in client.list_collections()]
        if f"case_{case_id}" not in collections:
            return ""
        collection = client.get_collection(f"case_{case_id}")
        if collection.count() == 0:
            return ""
        results = collection.get(
            include=["documents", "metadatas"],
            limit=max_chunks,
        )
        texts = results.get("documents") or []
        metas = results.get("metadatas") or []
        parts = []
        for text, meta in zip(texts, metas):
            fn = meta.get("filename", "unknown")
            pg = meta.get("page_number", "?")
            parts.append(f"[{fn}, p{pg}]\n{text}")
        return "\n\n".join(parts)
    except Exception as exc:
        logger.warning("ChromaDB fetch failed: %s", exc)
        return ""


def generate_summary(case_id: str) -> dict:
    context = _get_case_context(case_id)
    if not context:
        return {
            "parties": [],
            "charges_or_claims": [],
            "key_dates": [],
            "evidence": [],
            "open_issues": [],
            "summary": "No documents have been ingested for this case yet.",
        }

    try:
        llm = ChatGroq(
            model=GROQ_MODEL,
            api_key=os.getenv("GROQ_API_KEY", ""),
            temperature=0,
        )
        response = llm.invoke([
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=f"Case documents:\n\n{context}"),
        ])
        raw = response.content.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        import json
        return json.loads(raw)

    except Exception as exc:
        logger.error("generate_summary error: %s", exc, exc_info=True)
        return {"error": str(exc)}
