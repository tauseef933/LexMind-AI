"""
Case Summary Service

generate_summary(case_id) → dict

Queries ChromaDB for all document chunks in the case, then prompts
Groq to extract structured case intelligence.
"""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from llm import ask, get_llm, parse_json_response
from rag.vector_store import get_case_context

logger = logging.getLogger("lexmind.case_summary")

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


def generate_summary(case_id: str) -> dict:
    context = get_case_context(case_id)
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
        response = ask(get_llm(0), [
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=f"Case documents:\n\n{context}"),
        ])
        return parse_json_response(response)

    except Exception:
        logger.exception("generate_summary error")
        return {"error": "Summary generation failed."}
