"""
Action Agent

Parses the user's intent (email | calendar | pdf_report), drafts a
preview of the action, and returns it for human confirmation.
Nothing is executed — all actions require an explicit confirm step.

run(query, case_id) → dict
"""

import logging
import os

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger("lexmind.action_agent")

from backend.config import GROQ_MODEL

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
# Per-action draft prompts
# ---------------------------------------------------------------------------
_DRAFT_PROMPTS = {
    "email": """You are a legal assistant drafting a professional email on behalf of the attorney.
Case ID: {case_id}
Request: {query}

Draft a complete, professional email including:
- Subject line
- Salutation
- Body (clear, concise, legally appropriate)
- Closing

Output the full email text only.""",

    "calendar": """You are a legal assistant creating a calendar event description.
Case ID: {case_id}
Request: {query}

Output a structured calendar event with:
- Title
- Date/Time (infer from request or mark as [TBD])
- Location or Meeting Link ([TBD] if not specified)
- Attendees ([TBD] if not specified)
- Description/Agenda

Output the event details only.""",

    "pdf_report": """You are a legal assistant outlining a PDF report structure.
Case ID: {case_id}
Request: {query}

Output a structured report outline with:
- Report Title
- Sections and subsections
- Key data points to include in each section
- Notes for the attorney

Output the report outline only.""",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run(query: str, case_id: str) -> dict:
    try:
        llm = ChatGroq(
            model=GROQ_MODEL,
            api_key=os.getenv("GROQ_API_KEY", ""),
            temperature=0.2,
        )

        # 1. Classify intent
        classify_response = llm.invoke([
            SystemMessage(content=_CLASSIFY_SYSTEM),
            HumanMessage(content=query),
        ])
        action_type = classify_response.content.strip().lower()

        # Normalise / guard against unexpected output
        if action_type not in _DRAFT_PROMPTS:
            action_type = "email"   # sensible default

        # 2. Draft the action preview
        draft_prompt = _DRAFT_PROMPTS[action_type].format(
            case_id=case_id,
            query=query,
        )
        draft_response = llm.invoke([
            HumanMessage(content=draft_prompt),
        ])
        preview: str = draft_response.content.strip()

        logger.info("action_agent drafted %s for case %s", action_type, case_id)
        return {
            "action_type": action_type,
            "preview": preview,
            "requires_confirmation": True,
            "agent": "action_agent",
        }

    except Exception as exc:
        logger.error("action_agent error: %s", exc, exc_info=True)
        return {"error": str(exc), "agent": "action_agent"}
