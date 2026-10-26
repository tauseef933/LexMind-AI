"""
Timeline Builder Service

build_timeline(case_id) → list[dict]

Prompts Groq to extract every date-event pair from case documents,
returns them sorted chronologically.
"""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from llm import ask, get_llm, parse_json_response
from rag.vector_store import get_case_context

logger = logging.getLogger("lexmind.timeline_builder")

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


def build_timeline(case_id: str) -> list[dict]:
    context = get_case_context(case_id)
    if not context:
        return []

    try:
        response = ask(get_llm(0), [
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=f"Case documents:\n\n{context}"),
        ])
        parsed = parse_json_response(response)
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

    except Exception:
        logger.exception("build_timeline error")
        return []
