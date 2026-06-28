"""
Hearing Prep Service

prepare_hearing(case_id, hearing_date) → dict

Aggregates case summary, open risks, document list, and a Groq-generated
argument strategy into a structured prep sheet.
"""

import json
import logging
import os

import chromadb
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from backend.models.database import Document, SessionLocal
from backend.services.case_summary import generate_summary
from backend.services.risk_detector import detect_risks

logger = logging.getLogger("lexmind.hearing_prep")

from backend.config import GROQ_MODEL
_CHROMA_PATH = os.getenv("CHROMA_PERSIST_PATH", "./chroma_db")

_STRATEGY_SYSTEM = """You are a senior trial attorney preparing for a court hearing.
Given the case summary, risks, and document list, produce a hearing preparation
plan as valid JSON only (no markdown):

{
  "key_arguments": ["list of strongest arguments to make"],
  "anticipated_objections": ["objections opposing counsel may raise"],
  "witness_considerations": ["key points about witnesses"],
  "document_priorities": ["which documents to reference first and why"],
  "procedural_checklist": ["procedural steps to complete before hearing"],
  "opening_statement_outline": "brief outline for opening statement"
}"""


def _get_document_list(case_id: str) -> list[dict]:
    db: Session = SessionLocal()
    try:
        docs = db.query(Document).filter(Document.case_id == case_id).all()
        return [
            {
                "filename": d.filename,
                "file_type": d.file_type,
                "page_count": d.page_count,
            }
            for d in docs
        ]
    finally:
        db.close()


def prepare_hearing(case_id: str, hearing_date: str) -> dict:
    # 1. Pull existing intelligence in parallel-ish (sequential is fine here)
    summary = generate_summary(case_id)
    risks_data = detect_risks(case_id)
    document_list = _get_document_list(case_id)

    risks = risks_data.get("risks", [])
    high_risks = [r for r in risks if r.get("severity") == "HIGH"]

    # 2. Build strategy with Groq
    strategy: dict = {}
    try:
        llm = ChatGroq(
            model=GROQ_MODEL,
            api_key=os.getenv("GROQ_API_KEY", ""),
            temperature=0.1,
        )
        context_payload = json.dumps({
            "hearing_date": hearing_date,
            "case_summary": summary,
            "high_risks": high_risks,
            "document_count": len(document_list),
            "documents": document_list[:15],  # cap to avoid token overflow
        }, indent=2)

        response = llm.invoke([
            SystemMessage(content=_STRATEGY_SYSTEM),
            HumanMessage(content=f"Case context:\n{context_payload}"),
        ])
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        strategy = json.loads(raw.strip())

    except Exception as exc:
        logger.error("Hearing strategy generation failed: %s", exc, exc_info=True)
        strategy = {"error": str(exc)}

    return {
        "hearing_date": hearing_date,
        "case_id": case_id,
        "summary": summary,
        "risks": risks,
        "high_risk_count": len(high_risks),
        "documents": document_list,
        "strategy": strategy,
    }
