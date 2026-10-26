"""
Risk Detector Service

detect_risks(case_id) → dict

Uses the exact RISK_PROMPT from spec to identify risks across all
case documents.
"""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from llm import ask, get_llm, parse_json_response
from rag.vector_store import get_case_context

logger = logging.getLogger("lexmind.risk_detector")

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


def detect_risks(case_id: str) -> dict:
    context = get_case_context(case_id)
    if not context:
        return {"risks": [], "message": "No documents ingested for this case yet."}

    try:
        filled = RISK_PROMPT.format(case_context=context)
        response = ask(get_llm(0), [
            SystemMessage(content="You are a litigation risk analyst. Output ONLY valid JSON."),
            HumanMessage(content=filled),
        ])
        return parse_json_response(response)

    except Exception:
        logger.exception("detect_risks error")
        return {"error": "Risk analysis failed.", "risks": []}
