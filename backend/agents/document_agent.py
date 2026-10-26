"""
Document Agent

Answers questions grounded strictly in the case documents, choosing how much
of the documents to read based on the kind of question:

  focused  "What is the liability cap?"  → hybrid retrieval + rerank, top passages
  broad    "Summarise…", "What is missing?", "Is there a … clause?", "Compare…"
           → the COMPLETE text, page by page, so the answer can't miss a
             section that retrieval didn't surface
             · fits in DOC_CONTEXT_CHARS → one call over the full text
             · too large               → map-reduce: notes per part, then answer

run(query, case_id, on_token=None) → dict
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Literal, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from llm import TokenCallback, ask, ask_streaming, get_llm
from rag.reranker import rerank
from rag.retrieval import hybrid_retrieve
from rag.vector_store import context_chars, format_chunks, get_case_chunks

logger = logging.getLogger("lexmind.document_agent")

_CANDIDATES = 20      # chunks pulled by hybrid retrieval
_CONTEXT_CHUNKS = 5   # chunks kept after reranking and sent to the LLM
_MAP_WORKERS = 2      # parallel map calls (kept low for API rate limits)

Scope = Literal["focused", "broad"]

# Questions that need the whole document set rather than the best few passages
_BROAD_PATTERNS = [
    r"\bsummar(y|ies|ise|ize|ising|izing)\b", r"\boverview\b", r"\boutline\b",
    r"\b(key|main) (points|terms|provisions|issues)\b", r"\boverall\b",
    r"\b(whole|entire|full) (document|contract|agreement|case|file)s?\b",
    r"\bmissing\b", r"\babsent\b", r"\black(s|ing)?\b", r"\bomi(t|ts|tted|ssion|ssions)\b",
    r"\bgaps?\b", r"\bnot (included|covered|mentioned|addressed|specified)\b",
    r"^\s*(is|are) there\b", r"\bdoes (the|this|it|either|any|each)\b.*\b(contain|include|have|mention|address|cover|specify)\b",
    r"\bcompar(e|es|ing|ison)\b", r"\bdifferences?\b", r"\bversus\b", r"\bvs\.?\b",
    r"\b(each|every|both|all( the)?) (contracts?|documents?|agreements?|files?)\b",
    r"\blist (all|every)\b", r"\ball (the )?(clauses|obligations|dates|deadlines|parties|terms)\b",
    r"\b(risks|red flags|weakness(es)?)\b",
]
_BROAD = re.compile("|".join(_BROAD_PATTERNS), re.IGNORECASE)

_CITATION_RULES = """Citation format: [Source: {filename}, Page {page}]

Rules:
1. Never state facts that are not in the text provided
2. Every factual claim needs a [Source: ...] citation
3. Use precise legal language
4. Structure the response with clear headings if listing multiple points"""

# Focused mode: only a few retrieved passages are visible
RAG_PROMPT = """
You are a legal document analyst. Answer the question using ONLY the
provided excerpts. Every factual claim MUST include a citation.

Excerpts retrieved from the case documents:
{retrieved_chunks}

Question: {query}

""" + _CITATION_RULES + """
5. You only see a few excerpts. If they don't contain the answer, say it was
   not found in the retrieved excerpts — never claim the documents lack it
"""

# Broad mode, everything fits: the model sees every page
FULL_PROMPT = """
You are a legal document analyst. Below is the COMPLETE text of every document
in this case ({coverage}), in reading order. Answer the question using ONLY
this text. Every factual claim MUST include a citation.

Case documents:
{documents}

Question: {query}

""" + _CITATION_RULES + """
5. Because you have the complete text, you may say something is absent — but
   only after checking every document, and name the documents you checked
"""

MAP_PROMPT = """
You are helping answer a question about a set of legal documents that is too
long to read at once. This is PART {part} of {parts}.

Question: {query}

From this part only, write concise bullet notes of every fact relevant to the
question, each with its citation [Source: filename, Page N]. Also list the
clause or section headings that appear in this part, so later steps know what
the documents contain. If nothing is relevant, write "Nothing relevant in this part."

Text of part {part}:
{documents}
"""

REDUCE_PROMPT = """
You are a legal document analyst. The notes below were extracted from ALL
{parts} parts of the case documents, which together cover every page
({coverage}). Answer the question using ONLY these notes, keeping their
citations. Every factual claim MUST include a citation.

Notes:
{notes}

Question: {query}

""" + _CITATION_RULES + """
5. The notes cover every page. You may say something is absent only if no
   note mentions it, and name the documents that were checked
"""


# Look-alike characters some models emit inside filenames ("Northwind\u2011NDA.pdf"
# with U+2011), which would break citation matching and file links.
_LOOKALIKES = str.maketrans({
    "\u2010": "-",  # hyphen
    "\u2011": "-",  # non-breaking hyphen
    "\u2212": "-",  # minus sign
    "\u00a0": " ",  # no-break space
    "\u202f": " ",  # narrow no-break space
    "\u3010": "[",  # CJK lenticular brackets, used by some models around citations
    "\u3011": "]",
    "\uff3b": "[",  # fullwidth square brackets
    "\uff3d": "]",
})


def normalize_typography(text: str) -> str:
    """Replace look-alike hyphens/spaces with plain ASCII (en/em dashes are kept)."""
    return text.translate(_LOOKALIKES)


def _normalized_stream(on_token: Optional[TokenCallback]) -> Optional[TokenCallback]:
    if on_token is None:
        return None
    return lambda token: on_token(normalize_typography(token))


def classify_scope(query: str) -> Scope:
    """Broad questions need the whole document set; others use retrieval."""
    return "broad" if _BROAD.search(query) else "focused"


def _fill(template: str, **values: object) -> str:
    # Citation placeholders stay literal — they appear in the rules text
    return template.format(filename="{filename}", page="{page}", **values)


def _coverage(chunks: list[dict]) -> str:
    pages: dict[str, set[int]] = {}
    for c in chunks:
        pages.setdefault(c["filename"], set()).add(c["page_number"])
    return "; ".join(
        f"{name}: {len(nums)} page{'s' if len(nums) != 1 else ''}" for name, nums in pages.items()
    )


def _windows(chunks: list[dict], budget: int) -> list[list[dict]]:
    """Split chunks (in reading order) into consecutive groups that fit the budget."""
    groups: list[list[dict]] = [[]]
    size = 0
    for chunk in chunks:
        cost = len(chunk["text"]) + len(chunk["filename"]) + 30
        if groups[-1] and size + cost > budget:
            groups.append([])
            size = 0
        groups[-1].append(chunk)
        size += cost
    return groups


def _verify_sources(answer: str, chunks: list[dict]) -> list[dict]:
    """
    Return one source dict per [Source: filename, Page N] reference that
    actually appears in the answer AND exists in the chunks it was given.
    """
    pattern = re.compile(r"\[Source:\s*(.+?),\s*Page\s*(\d+)\]", re.IGNORECASE)
    mentioned = {
        (fn.strip().lower(), int(pg))
        for fn, pg in pattern.findall(normalize_typography(answer))
    }

    cited: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for c in chunks:
        key = (normalize_typography(c["filename"]).lower(), c["page_number"])
        if key in mentioned and key not in seen:
            seen.add(key)
            cited.append(c)
    return cited


def _no_documents() -> dict:
    return {
        "answer": "No documents have been ingested for this case yet.",
        "sources": [],
        "agent": "document_agent",
    }


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

def _answer_focused(query: str, case_id: str, on_token: Optional[TokenCallback]) -> Optional[dict]:
    candidates = hybrid_retrieve(query, case_id, top_k=_CANDIDATES)
    if not candidates:
        return None
    top_chunks = rerank(query, candidates, top_n=_CONTEXT_CHUNKS)
    prompt = _fill(RAG_PROMPT, retrieved_chunks=format_chunks(top_chunks), query=query)
    answer = ask_streaming(get_llm(0), [
        SystemMessage(content="You are a precise legal document analyst."),
        HumanMessage(content=prompt),
    ], on_token)
    return {"answer": answer, "sources": _verify_sources(answer, top_chunks), "mode": "focused"}


def _answer_broad(query: str, case_id: str, on_token: Optional[TokenCallback]) -> Optional[dict]:
    chunks = get_case_chunks(case_id)
    if not chunks:
        return None
    budget = context_chars()
    coverage = _coverage(chunks)
    llm = get_llm(0)
    system = SystemMessage(content="You are a precise legal document analyst.")

    full_text = format_chunks(chunks)
    if len(full_text) <= budget:
        prompt = _fill(FULL_PROMPT, coverage=coverage, documents=full_text, query=query)
        answer = ask_streaming(llm, [system, HumanMessage(content=prompt)], on_token)
        return {"answer": answer, "sources": _verify_sources(answer, chunks), "mode": "full"}

    # Map: notes from each part, in parallel but gently (API rate limits)
    windows = _windows(chunks, budget)

    def _notes(index: int) -> str:
        prompt = MAP_PROMPT.format(
            part=index + 1, parts=len(windows), query=query, documents=format_chunks(windows[index])
        )
        return ask(llm, [system, HumanMessage(content=prompt)])

    with ThreadPoolExecutor(max_workers=_MAP_WORKERS) as pool:
        notes = list(pool.map(_notes, range(len(windows))))

    joined = "\n\n".join(f"Part {i + 1}:\n{n}" for i, n in enumerate(notes))
    if len(joined) > budget:
        joined = joined[:budget] + "\n[Notes truncated]"

    # Reduce: one streamed answer over all the notes
    prompt = _fill(REDUCE_PROMPT, parts=len(windows), coverage=coverage, notes=joined, query=query)
    answer = ask_streaming(llm, [system, HumanMessage(content=prompt)], on_token)
    logger.info("document_agent map-reduce over %d parts for case %s", len(windows), case_id)
    return {"answer": answer, "sources": _verify_sources(answer, chunks), "mode": "map_reduce"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run(query: str, case_id: str, on_token: Optional[TokenCallback] = None) -> dict:
    try:
        scope = classify_scope(query)
        stream = _normalized_stream(on_token)
        if scope == "broad":
            result = _answer_broad(query, case_id, stream)
        else:
            result = _answer_focused(query, case_id, stream)
        if result is None:
            return _no_documents()
        # Same normalisation as the streamed tokens, so saved text == shown text
        result["answer"] = normalize_typography(result["answer"])

        logger.info(
            "document_agent answered (%s) for case %s, sources=%d",
            result["mode"], case_id, len(result["sources"]),
        )
        return {**result, "agent": "document_agent"}

    except Exception:
        logger.exception("document_agent error")
        return {"error": "Document analysis failed.", "agent": "document_agent"}
