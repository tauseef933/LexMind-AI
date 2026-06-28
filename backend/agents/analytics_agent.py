"""
Analytics Agent

Converts natural-language queries into safe SELECT SQL, executes against
the SQLite database, and returns results + a plain-English summary.

run(query, case_id) → dict
"""

import logging
import os
import re

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import text

from models.database import engine

logger = logging.getLogger("lexmind.analytics_agent")

from config import GROQ_MODEL

# ---------------------------------------------------------------------------
# Few-shot system prompt
# ---------------------------------------------------------------------------
_SYSTEM = """You are a SQL expert for a legal case management SQLite database.
Convert the user's natural language question into a valid SQLite SELECT statement.
Output ONLY the raw SQL — no markdown, no explanation, no code fences.

Schema:
  cases(id, name, client, court, hearing_date, status, created_at, updated_at)
  documents(id, case_id, filename, file_type, page_count, ingested_at)
  messages(id, case_id, role, content, agent_trace, sources, created_at)
  billing(id, case_id, invoice_number, amount, hours, invoice_date,
          dispute_flag, dispute_reason, status)

Examples:
Q: How much has been billed for case 'Smith v Jones'?
A: SELECT SUM(b.amount) AS total_billed FROM billing b JOIN cases c ON c.id = b.case_id WHERE c.name = 'Smith v Jones';

Q: List all disputed invoices
A: SELECT * FROM billing WHERE dispute_flag = 1;

Q: How many documents are in each case?
A: SELECT c.name, COUNT(d.id) AS doc_count FROM cases c LEFT JOIN documents d ON d.case_id = c.id GROUP BY c.id;
"""

_SUMMARY_SYSTEM = """You are a legal financial analyst. Given a SQL query and its results,
write a brief, plain-English summary (2-4 sentences) suitable for a lawyer."""


def _is_safe_sql(sql: str) -> bool:
    """Allow only SELECT statements; reject anything that mutates data."""
    clean = sql.strip().lstrip(";").strip().upper()
    if not clean.startswith("SELECT"):
        return False
    forbidden = re.compile(
        r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|REPLACE|TRUNCATE|ATTACH|DETACH)\b"
    )
    return not forbidden.search(clean)


def _rows_to_dicts(result) -> list[dict]:
    keys = list(result.keys())
    return [dict(zip(keys, row)) for row in result.fetchall()]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run(query: str, case_id: str) -> dict:
    try:
        llm = ChatGroq(
            model=GROQ_MODEL,
            api_key=os.getenv("GROQ_API_KEY", ""),
            temperature=0,
        )

        # 1. Translate NL → SQL
        sql_response = llm.invoke([
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=f"case_id context (use when filtering by case): {case_id}\n\nQuestion: {query}"),
        ])
        raw_sql = sql_response.content.strip()

        # Strip any accidental markdown fences
        raw_sql = re.sub(r"^```[a-z]*\n?", "", raw_sql, flags=re.IGNORECASE)
        raw_sql = raw_sql.rstrip("`").strip().rstrip(";")

        if not _is_safe_sql(raw_sql):
            return {
                "error": f"Generated SQL is not a safe SELECT statement: {raw_sql!r}",
                "agent": "analytics_agent",
            }

        # 2. Execute against SQLite
        with engine.connect() as conn:
            result = conn.execute(text(raw_sql))
            rows = _rows_to_dicts(result)

        # 3. Summarise in plain English
        summary_response = llm.invoke([
            SystemMessage(content=_SUMMARY_SYSTEM),
            HumanMessage(content=f"SQL: {raw_sql}\n\nResults: {rows}\n\nOriginal question: {query}"),
        ])
        answer: str = summary_response.content.strip()

        logger.info("analytics_agent executed SQL for case %s, rows=%d", case_id, len(rows))
        return {
            "answer": answer,
            "data": rows,
            "sql": raw_sql,
            "agent": "analytics_agent",
        }

    except Exception as exc:
        logger.error("analytics_agent error: %s", exc, exc_info=True)
        return {"error": str(exc), "agent": "analytics_agent"}
