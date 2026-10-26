"""
Analytics Agent

Maps a natural-language billing question onto one of a fixed set of
parameterised, read-only SQL queries (always scoped to the active case),
executes it, and returns results + a plain-English summary.

The LLM only picks a query name — it never writes SQL — so document text or
user input cannot inject SQL or read other cases' data.

run(query, case_id) → dict
"""

import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import text

from llm import ask, get_llm
from models.database import engine

logger = logging.getLogger("lexmind.analytics_agent")

# ---------------------------------------------------------------------------
# Allowed queries — every one is filtered by :case_id
# ---------------------------------------------------------------------------
QUERIES: dict[str, tuple[str, str]] = {
    "billing_totals": (
        "Total amount billed, total hours and invoice count",
        "SELECT COUNT(*) AS invoice_count, COALESCE(SUM(amount), 0) AS total_amount, "
        "COALESCE(SUM(hours), 0) AS total_hours FROM billing WHERE case_id = :case_id",
    ),
    "list_invoices": (
        "All invoices for the case, newest first",
        "SELECT invoice_number, amount, hours, invoice_date, status, dispute_flag "
        "FROM billing WHERE case_id = :case_id ORDER BY invoice_date DESC",
    ),
    "disputed_invoices": (
        "Invoices that are disputed, with the dispute reason",
        "SELECT invoice_number, amount, invoice_date, dispute_reason FROM billing "
        "WHERE case_id = :case_id AND dispute_flag = 1 ORDER BY invoice_date DESC",
    ),
    "totals_by_status": (
        "Amount and invoice count grouped by payment status (paid, pending, overdue …)",
        "SELECT status, COUNT(*) AS invoice_count, COALESCE(SUM(amount), 0) AS total_amount "
        "FROM billing WHERE case_id = :case_id GROUP BY status",
    ),
    "monthly_billing": (
        "Amount and hours billed per month",
        "SELECT strftime('%Y-%m', invoice_date) AS month, COALESCE(SUM(amount), 0) AS total_amount, "
        "COALESCE(SUM(hours), 0) AS total_hours FROM billing WHERE case_id = :case_id "
        "GROUP BY month ORDER BY month",
    ),
}

_DEFAULT_QUERY = "billing_totals"

_SELECT_SYSTEM = "You route billing questions for a legal case to a predefined report.\n" \
    "Reply with ONLY the report name, nothing else.\n\nReports:\n" + "\n".join(
        f"- {name}: {desc}" for name, (desc, _) in QUERIES.items()
    )

_SUMMARY_SYSTEM = """You are a legal financial analyst. Given a billing report and its results,
write a brief, plain-English summary (2-4 sentences) suitable for a lawyer.
If there are no rows, say no billing records exist for this case."""


def _rows_to_dicts(result) -> list[dict]:
    keys = list(result.keys())
    return [dict(zip(keys, row)) for row in result.fetchall()]


def _pick_query(llm: BaseChatModel, query: str) -> str:
    response = ask(llm, [
        SystemMessage(content=_SELECT_SYSTEM),
        HumanMessage(content=query),
    ])
    name = response.strip().strip("`'\" .").lower()
    return name if name in QUERIES else _DEFAULT_QUERY


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run(query: str, case_id: str) -> dict:
    try:
        llm = get_llm(0)

        # 1. Pick a predefined report
        report = _pick_query(llm, query)
        sql = QUERIES[report][1]

        # 2. Execute with case_id bound as a parameter
        with engine.connect() as conn:
            rows = _rows_to_dicts(conn.execute(text(sql), {"case_id": case_id}))

        # 3. Summarise in plain English
        summary_response = ask(llm, [
            SystemMessage(content=_SUMMARY_SYSTEM),
            HumanMessage(content=f"Report: {QUERIES[report][0]}\n\nResults: {rows}\n\nOriginal question: {query}"),
        ])
        answer: str = summary_response.strip()

        logger.info("analytics_agent ran %s for case %s, rows=%d", report, case_id, len(rows))
        return {
            "answer": answer,
            "data": rows,
            "sql": sql,
            "report": report,
            "agent": "analytics_agent",
        }

    except Exception:
        logger.exception("analytics_agent error")
        return {"error": "Billing analysis failed.", "agent": "analytics_agent"}
