"""
Risk Detector Service

detect_risks(case_id) → dict

Uses the exact RISK_PROMPT from spec to identify risks across all
case documents.
"""

import json
import logging
import os

import chromadb
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger("lexmind.risk_detector")

from backend.config import GROQ_MODEL
_CHROMA_PATH = os.getenv("CHROMA_PERSIST_PATH", "./chroma_db")

# ---------------------------------------------------------------------------
# Exact RISK_PROMPT from spec
# ---------------------------------------------------------------------------
RISK_PROMPT = """
You are a senior litigation analyst. Review the provided case documents
and identify ALL risks, weaknesses, and vulnerabilities in the case.

Case documents:
{case_context}

For each risk found, output:
{{
  "risks": [
    {{
      "severity": "HIGH | MEDIUM | LOW",
      "category": "evidence | procedural | legal | witness | timeline",
      "description": "Clear description of the risk",
      "source": "Document name + page where this was identified",
      "recommendation": "What the lawyer should do about this"
    }}
  ]
}}

Output ONLY valid JSON. No markdown, no prose outside the JSON.
"""


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


def detect_risks(case_id: str) -> dict:
    context = _get_case_context(case_id)
    if not context:
        return {"risks": [], "message": "No documents ingested for this case yet."}

    try:
        llm = ChatGroq(
            model=GROQ_MODEL,
            api_key=os.getenv("GROQ_API_KEY", ""),
            temperature=0,
        )
        filled = RISK_PROMPT.format(case_context=context)
        response = llm.invoke([
            SystemMessage(content="You are a litigation risk analyst. Output ONLY valid JSON."),
            HumanMessage(content=filled),
        ])
        raw = response.content.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        return json.loads(raw)

    except Exception as exc:
        logger.error("detect_risks error: %s", exc, exc_info=True)
        return {"error": str(exc), "risks": []}
