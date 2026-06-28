"""
Timeline Builder Service

build_timeline(case_id) → list[dict]

Prompts Groq to extract every date-event pair from case documents,
returns them sorted chronologically.
"""

import json
import logging
import os

import chromadb
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger("lexmind.timeline_builder")

from config import GROQ_MODEL
_CHROMA_PATH = os.getenv("CHROMA_PERSIST_PATH", "./chroma_db")

_SYSTEM = """You are a legal timeline analyst. Extract every date and associated
event from the provided case documents.

Output ONLY valid JSON in this exact structure (no markdown, no prose):
{
  "events": [
    {
      "date": "YYYY-MM-DD or best approximation (e.g. 'March 2022')",
      "event": "clear description of what happened",
      "source": "filename and page number"
    }
  ]
}

Rules:
- Include ALL dates found: filing dates, hearing dates, contract dates,
  incident dates, correspondence dates, deadline dates.
- If exact date is unclear use the most precise approximation possible.
- Sort events chronologically (earliest first).
- If no dates are found, return {"events": []}."""


def _get_case_context(case_id: str, max_chunks: int = 40) -> str:
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


def build_timeline(case_id: str) -> list[dict]:
    context = _get_case_context(case_id)
    if not context:
        return []

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

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        parsed = json.loads(raw)
        events: list[dict] = parsed.get("events", [])

        # Ensure required keys exist on every event
        cleaned = []
        for ev in events:
            cleaned.append({
                "date":   ev.get("date", "Unknown"),
                "event":  ev.get("event", ""),
                "source": ev.get("source", ""),
            })

        return cleaned

    except Exception as exc:
        logger.error("build_timeline error: %s", exc, exc_info=True)
        return []
