"""
Suggested Questions Service

suggest_questions(case_id) → {"questions": [str, ...], "source": "documents" | "default" | "none"}

Reads a sample of the case's documents and asks the LLM for the few questions
a lawyer would most likely ask about *these* documents, so the chat shows
relevant one-click questions instead of a fixed generic list.

Results are cached per case and invalidated automatically when the number of
indexed chunks changes (a document was added or removed).
"""

import logging
import threading

from langchain_core.messages import HumanMessage, SystemMessage

from llm import ask, get_llm, parse_json_response
from rag.vector_store import get_case_collection, get_case_context

logger = logging.getLogger("lexmind.suggestions")

MAX_QUESTIONS = 4
_MAX_LENGTH = 110   # characters — keeps chips to one line

# Used when the LLM is unavailable; they fit almost any set of case documents
DEFAULT_QUESTIONS = [
    "Summarise the key points of these documents.",
    "Who are the parties and what are their main obligations?",
    "What are the important dates and deadlines?",
    "What risks or unusual terms should I be aware of?",
]

_SYSTEM = f"""You help a lawyer get started with a set of case documents.
Suggest the {MAX_QUESTIONS} questions a lawyer would most likely ask about THESE documents.

Rules:
- Each question must be answerable from the documents shown.
- Be specific to the content (name the agreement, clause or party), not generic.
- Cover different topics (e.g. parties/obligations, money/liability, dates/term, risks/disputes).
- Each question under 90 characters, plain language, ending with "?".

Output ONLY a JSON array of strings."""

_cache: dict[str, tuple[int, list[str]]] = {}   # case_id → (chunk count, questions)
_lock = threading.Lock()


def _clean(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    questions: list[str] = []
    for item in raw:
        text = " ".join(str(item).split()).strip()
        if 10 <= len(text) <= _MAX_LENGTH and text not in questions:
            questions.append(text)
    return questions[:MAX_QUESTIONS]


def suggest_questions(case_id: str) -> dict:
    collection = get_case_collection(case_id)
    chunk_count = collection.count() if collection is not None else 0
    if chunk_count == 0:
        return {"questions": [], "source": "none"}

    with _lock:
        cached = _cache.get(case_id)
    if cached and cached[0] == chunk_count:
        return {"questions": cached[1], "source": "documents"}

    try:
        context = get_case_context(case_id, max_chars=12000)
        reply = ask(get_llm(0.3), [
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=f"Case documents:\n\n{context}"),
        ])
        questions = _clean(parse_json_response(reply))
    except Exception:
        logger.exception("Suggestion generation failed — using defaults")
        questions = []

    if len(questions) < 2:
        return {"questions": DEFAULT_QUESTIONS, "source": "default"}

    with _lock:
        _cache[case_id] = (chunk_count, questions)
    return {"questions": questions, "source": "documents"}
