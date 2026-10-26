"""Broad questions read the whole document set; focused ones use retrieval."""

import re

import pytest

from agents import document_agent
from rag import vector_store


def _chunk(filename: str, page: int, text: str, index: int = 0) -> dict:
    return {"text": text, "doc_id": filename, "filename": filename, "page_number": page, "chunk_index": index}


CORPUS = [
    _chunk("nda.pdf", 1, "Parties: Northwind and Quillon."),
    _chunk("nda.pdf", 3, "Confidentiality survives for five years."),
    _chunk("nda.pdf", 5, "Governing law: State of New York."),
    _chunk("msa.pdf", 1, "Monthly fee USD 42,000."),
    _chunk("msa.pdf", 4, "Governing law: State of California."),
]


@pytest.mark.parametrize("question", [
    "Summarize this case",
    "Give me an overview of the documents",
    "Are there any procedural gaps or missing documentation?",
    "Is there a governing law clause?",
    "Does the NDA contain an arbitration clause?",
    "Compare the liability caps in both agreements",
    "What is the liability cap in each contract?",
    "List all deadlines",
    "What risks should I be aware of?",
])
def test_broad_questions(question):
    assert document_agent.classify_scope(question) == "broad"


@pytest.mark.parametrize("question", [
    "What is the monthly fee?",
    "Who signed for Quillon?",
    "How many days to return documents?",
    "Which state's law governs the NDA?",
])
def test_focused_questions(question):
    assert document_agent.classify_scope(question) == "focused"


@pytest.fixture
def corpus(monkeypatch):
    monkeypatch.setattr(document_agent, "get_case_chunks", lambda case_id: list(CORPUS))


def test_broad_question_sees_every_page(corpus, fake_llm):
    fake_llm.responder = lambda p: (
        "Both agreements specify governing law [Source: nda.pdf, Page 5] [Source: msa.pdf, Page 4]."
    )
    tokens: list[str] = []
    result = document_agent.run("Is there a governing law clause?", "case", on_token=tokens.append)

    prompt = fake_llm.calls[0]
    assert "COMPLETE text" in prompt
    assert all(c["text"] in prompt for c in CORPUS), "every page must be in the prompt"
    assert "nda.pdf: 3 pages; msa.pdf: 2 pages" in prompt
    assert result["mode"] == "full"
    assert {(s["filename"], s["page_number"]) for s in result["sources"]} == {("nda.pdf", 5), ("msa.pdf", 4)}
    assert "".join(tokens) == result["answer"], "broad answers still stream"


def test_large_case_uses_map_reduce_over_every_page(corpus, fake_llm, monkeypatch):
    monkeypatch.setenv("DOC_CONTEXT_CHARS", "120")  # force several parts

    def responder(prompt: str) -> str:
        if "This is PART" in prompt:
            pages = re.findall(r"\[Source: [^\]]+\]", prompt)
            return "- notes " + " ".join(pages)
        return "Governing law is New York [Source: nda.pdf, Page 5]."

    fake_llm.responder = responder
    result = document_agent.run("Are there any missing clauses?", "case")

    map_calls = [c for c in fake_llm.calls if "This is PART" in c]
    reduce_calls = [c for c in fake_llm.calls if "extracted from ALL" in c]
    assert len(map_calls) > 1 and len(reduce_calls) == 1
    for chunk in CORPUS:
        assert sum(chunk["text"] in c for c in map_calls) == 1, "each page read in exactly one part"
    assert "Part 1:" in reduce_calls[0] and "notes" in reduce_calls[0]
    assert result["mode"] == "map_reduce"
    assert [(s["filename"], s["page_number"]) for s in result["sources"]] == [("nda.pdf", 5)]


def test_focused_answers_do_not_claim_absence(fake_llm, monkeypatch):
    monkeypatch.setattr(document_agent, "hybrid_retrieve", lambda *a, **k: [CORPUS[3]])
    monkeypatch.setattr(document_agent, "rerank", lambda q, c, top_n: c)
    result = document_agent.run("What is the monthly fee?", "case")

    prompt = fake_llm.calls[0]
    assert "never claim the documents lack it" in prompt
    assert "COMPLETE text" not in prompt
    assert result["mode"] == "focused"


def test_no_documents(fake_llm, monkeypatch):
    monkeypatch.setattr(document_agent, "get_case_chunks", lambda case_id: [])
    assert document_agent.run("Summarise", "case")["answer"].startswith("No documents")
    assert fake_llm.calls == []


def test_lookalike_hyphens_in_citations_are_normalised(fake_llm, monkeypatch):
    # Some models write U+2011 (non-breaking hyphen) and U+00A0 inside filenames
    fake_llm.responder = lambda p: "Fee USD\u00a042,000 [Source: msa\u2011file.pdf, Page 1]."
    chunks = [_chunk("msa-file.pdf", 1, "Monthly fee USD 42,000.")]
    tokens: list[str] = []
    monkeypatch.setattr(document_agent, "get_case_chunks", lambda case_id: chunks)
    result = document_agent.run("Summarise the fees", "case", on_token=tokens.append)

    assert result["answer"] == "Fee USD 42,000 [Source: msa-file.pdf, Page 1]."
    assert "".join(tokens) == result["answer"]
    assert [s["filename"] for s in result["sources"]] == ["msa-file.pdf"]
    # en/em dashes in prose are left alone
    assert document_agent.normalize_typography("a – b — c") == "a – b — c"


def test_cjk_bracket_citations_are_recognised(fake_llm, monkeypatch):
    # gpt-oss style citations: \u3010Source: file, Page N\u3011
    fake_llm.responder = lambda p: "Governed by New York law \u3010Source: nda.pdf, Page 5\u3011."
    monkeypatch.setattr(document_agent, "get_case_chunks", lambda case_id: list(CORPUS))
    result = document_agent.run("Is there a governing law clause?", "case")

    assert result["answer"] == "Governed by New York law [Source: nda.pdf, Page 5]."
    assert [(s["filename"], s["page_number"]) for s in result["sources"]] == [("nda.pdf", 5)]


def test_verify_sources_one_per_page():
    chunks = [_chunk("nda.pdf", 5, "a", 0), _chunk("nda.pdf", 5, "b", 1), _chunk("nda.pdf", 3, "c")]
    cited = document_agent._verify_sources("[Source: NDA.pdf, Page 5] and [Source: other.pdf, Page 1]", chunks)
    assert cited == [chunks[0]]


def test_case_context_samples_across_all_documents(monkeypatch):
    many = [_chunk("a.pdf", p, "x" * 200) for p in range(1, 41)] + \
           [_chunk("z.pdf", p, "y" * 200) for p in range(1, 41)]
    monkeypatch.setattr(vector_store, "get_case_chunks", lambda case_id: many)

    text = vector_store.get_case_context("case", max_chars=3000)
    assert "a.pdf" in text and "z.pdf" in text, "later documents must not be cut off"
    assert "do not conclude that something is missing" in text
    assert len(text) < 3000 + 300

    small = many[:2]
    monkeypatch.setattr(vector_store, "get_case_chunks", lambda case_id: small)
    whole = vector_store.get_case_context("case", max_chars=3000)
    assert "Note:" not in whole and whole.count("[Source:") == 2
