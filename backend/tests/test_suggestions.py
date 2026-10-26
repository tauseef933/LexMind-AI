"""Case-specific suggested questions."""

import json

import pytest

from services import suggestions


class _Collection:
    def __init__(self, count: int) -> None:
        self._count = count

    def count(self) -> int:
        return self._count


@pytest.fixture
def docs(monkeypatch):
    """Pretend the case has `state["chunks"]` indexed chunks."""
    state = {"chunks": 5}
    monkeypatch.setattr(suggestions, "get_case_collection", lambda case_id: _Collection(state["chunks"]))
    monkeypatch.setattr(suggestions, "get_case_context", lambda case_id, **k: "NDA between Acme and Beta")
    suggestions._cache.clear()
    return state


def test_no_documents_means_no_suggestions(client, case_id, fake_llm):
    r = client.get(f"/cases/{case_id}/suggestions")
    assert r.json() == {"questions": [], "source": "none"}
    assert fake_llm.calls == []


def test_questions_come_from_the_documents_and_are_cleaned(client, case_id, fake_llm, docs):
    fake_llm.responder = lambda p: json.dumps([
        "How long does the Acme NDA confidentiality last?",
        "How long does the Acme NDA confidentiality last?",   # duplicate
        "Short?",                                               # too short
        "Who   are the\nparties?",                              # whitespace normalised
        "What is the liability cap?",
        "x" * 200,                                              # too long
        "Which law governs the NDA?",
        "Extra fifth question beyond the limit?",
    ])
    body = client.get(f"/cases/{case_id}/suggestions").json()
    assert body["source"] == "documents"
    assert body["questions"] == [
        "How long does the Acme NDA confidentiality last?",
        "Who are the parties?",
        "What is the liability cap?",
        "Which law governs the NDA?",
    ]


def test_cached_until_documents_change(client, case_id, fake_llm, docs):
    fake_llm.responder = lambda p: json.dumps(["First question here?", "Second question here?"])
    client.get(f"/cases/{case_id}/suggestions")
    client.get(f"/cases/{case_id}/suggestions")
    assert len(fake_llm.calls) == 1

    docs["chunks"] = 9  # a document was added
    client.get(f"/cases/{case_id}/suggestions")
    assert len(fake_llm.calls) == 2


def test_falls_back_to_defaults_when_llm_fails(client, case_id, fake_llm, docs):
    def boom(prompt):
        raise RuntimeError("down")

    fake_llm.responder = boom
    body = client.get(f"/cases/{case_id}/suggestions").json()
    assert body == {"questions": suggestions.DEFAULT_QUESTIONS, "source": "default"}


def test_unknown_case_is_404(client):
    assert client.get("/cases/00000000-0000-0000-0000-000000000000/suggestions").status_code == 404
