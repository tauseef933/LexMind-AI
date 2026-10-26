"""
Action Agent

Parses the user's intent (email | calendar | pdf_report) and drafts the
action as structured data plus a readable preview. Nothing is executed:
the user reviews the draft and acts on it from the UI (open in mail app,
download .ics, download PDF).

run(query, case_id) → {
    "action_type": "email" | "calendar" | "pdf_report",
    "action":      dict,   # structured fields, see _DRAFT_PROMPTS
    "preview":     str,    # markdown preview shown in chat
    "requires_confirmation": True,
    "agent": "action_agent",
}
"""

import logging
from datetime import date

from langchain_core.messages import HumanMessage, SystemMessage

from llm import ask, get_llm, parse_json_response
from rag.vector_store import get_case_context

logger = logging.getLogger("lexmind.action_agent")

# ---------------------------------------------------------------------------
# Intent classification prompt
# ---------------------------------------------------------------------------
_CLASSIFY_SYSTEM = """You classify a legal assistant action request into exactly
one of three categories: email | calendar | pdf_report

Output ONLY the category word, nothing else.

Examples:
"Send an email to the client about the hearing" → email
"Schedule a meeting with opposing counsel for next Tuesday" → calendar
"Generate a summary PDF of the Smith case" → pdf_report
"draft an email updating Alice about the settlement offer" → email
"add a court date to the calendar for March 15" → calendar
"create a PDF report of all billing disputes" → pdf_report
"""

# ---------------------------------------------------------------------------
# Per-action draft prompts — each asks for JSON only
# ---------------------------------------------------------------------------
_DRAFT_PROMPTS = {
    "email": """You are a legal assistant drafting a professional email on behalf of the attorney.
Request: {query}

Return ONLY JSON:
{{
  "to": "recipient email address if given in the request, else empty string",
  "subject": "subject line",
  "body": "full email text: salutation, clear and legally appropriate body, closing"
}}""",

    "calendar": """You are a legal assistant creating a calendar event.
Today's date is {today}.
Request: {query}

Return ONLY JSON:
{{
  "title": "event title",
  "start": "ISO 8601 local date-time like 2026-11-03T10:00, or null if the date is not given",
  "end": "ISO 8601 local date-time, or null (defaults to one hour after start)",
  "location": "location or meeting link, or empty string",
  "attendees": ["names or emails mentioned"],
  "description": "agenda / description"
}}""",

    "pdf_report": """You are a legal assistant writing a short report for the attorney.
Request: {query}

Case documents (cite as [Source: filename, Page N]):
{context}

Write the report from the case documents only. Return ONLY JSON:
{{
  "title": "report title",
  "sections": [
    {{"heading": "section heading", "content": "paragraphs; use lines starting with '- ' for lists"}}
  ]
}}""",
}


def _preview(action_type: str, action: dict) -> str:
    if action_type == "email":
        to = f"**To:** {action['to']}\n" if action.get("to") else ""
        return f"{to}**Subject:** {action.get('subject', '')}\n\n{action.get('body', '')}"
    if action_type == "calendar":
        when = action.get("start") or "date to be confirmed"
        lines = [f"**{action.get('title', 'Event')}**", f"**When:** {when}"]
        if action.get("location"):
            lines.append(f"**Where:** {action['location']}")
        if action.get("attendees"):
            lines.append(f"**Attendees:** {', '.join(action['attendees'])}")
        if action.get("description"):
            lines.append(f"\n{action['description']}")
        return "\n".join(lines)
    sections = "\n\n".join(
        f"**{s.get('heading', '')}**\n{s.get('content', '')}" for s in action.get("sections", [])
    )
    return f"### {action.get('title', 'Report')}\n\n{sections}"


def _normalise(action_type: str, raw: dict) -> dict:
    """Keep only expected keys with the right types, so the UI can rely on them."""
    if action_type == "email":
        return {k: str(raw.get(k) or "") for k in ("to", "subject", "body")}
    if action_type == "calendar":
        return {
            "title": str(raw.get("title") or "Event"),
            "start": raw.get("start") or None,
            "end": raw.get("end") or None,
            "location": str(raw.get("location") or ""),
            "attendees": [str(a) for a in raw.get("attendees") or []],
            "description": str(raw.get("description") or ""),
        }
    return {
        "title": str(raw.get("title") or "Case report"),
        "sections": [
            {"heading": str(s.get("heading") or ""), "content": str(s.get("content") or "")}
            for s in raw.get("sections") or []
            if isinstance(s, dict)
        ],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run(query: str, case_id: str) -> dict:
    try:
        llm = get_llm(0.2)

        # 1. Classify intent
        action_type = ask(llm, [
            SystemMessage(content=_CLASSIFY_SYSTEM),
            HumanMessage(content=query),
        ]).lower().strip(" .`'\"")

        # Normalise / guard against unexpected output
        if action_type not in _DRAFT_PROMPTS:
            action_type = "email"   # sensible default

        # 2. Draft the action as structured data
        context = get_case_context(case_id) if action_type == "pdf_report" else ""
        draft_prompt = _DRAFT_PROMPTS[action_type].format(
            query=query,
            today=date.today().isoformat(),
            context=context or "(no documents ingested)",
        )
        raw = parse_json_response(ask(llm, [HumanMessage(content=draft_prompt)]))
        action = _normalise(action_type, raw if isinstance(raw, dict) else {})

        logger.info("action_agent drafted %s for case %s", action_type, case_id)
        return {
            "action_type": action_type,
            "action": action,
            "preview": _preview(action_type, action),
            "requires_confirmation": True,
            "agent": "action_agent",
        }

    except Exception:
        logger.exception("action_agent error")
        return {"error": "Drafting the action failed.", "agent": "action_agent"}
