"""Chat streaming endpoint: event order, persistence, memory, multi-agent output."""

import asyncio
import json
import time

import httpx
from conftest import sse_events

from api.main import app
from api.routes import chat as chat_route


def _chat(client, case_id, text="What does the NDA say?"):
    r = client.post("/chat", json={"content": text, "case_id": case_id})
    assert r.status_code == 200
    return sse_events(r.text)


def test_unknown_case_is_404(client):
    r = client.post("/chat", json={"content": "hi", "case_id": "00000000-0000-0000-0000-000000000000"})
    assert r.status_code == 404


def test_event_sequence_and_persistence(client, case_id, fake_llm, monkeypatch):
    from agents import document_agent

    chunk = {"text": "Term is five years.", "doc_id": "d1", "filename": "nda.pdf",
             "page_number": 2, "chunk_index": 0}
    monkeypatch.setattr(document_agent, "hybrid_retrieve", lambda *a, **k: [chunk])
    monkeypatch.setattr(document_agent, "rerank", lambda q, c, top_n: c)
    fake_llm.responder = lambda p: (
        json.dumps({"subtasks": [{"agent": "document_agent", "query": "q", "priority": 1}]})
        if "routing orchestrator" in p else "It lasts five years [Source: nda.pdf, Page 2]."
    )

    events = _chat(client, case_id)
    types = [e["type"] for e in events]
    steps = [(e["step"]["agent"], e["step"]["status"]) for e in events if e["type"] == "agent_trace"]

    assert steps[0] == ("orchestrator", "routing")
    assert ("document_agent", "running") in steps and ("document_agent", "done") in steps
    assert types.index("token") < types.index("done") and types[-1] == "done"

    streamed = "".join(e["content"] for e in events if e["type"] == "token")
    assert streamed == "It lasts five years [Source: nda.pdf, Page 2]."
    assert len([e for e in events if e["type"] == "token"]) > 1, "answer should arrive in several tokens"

    done = events[-1]
    assert done["sources"] and done["sources"][0]["page_number"] == 2

    messages = client.get(f"/cases/{case_id}/messages").json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["content"] == streamed


def test_uncited_chunks_are_not_returned_as_sources(client, case_id, fake_llm, monkeypatch):
    from agents import document_agent

    chunk = {"text": "x", "doc_id": "d", "filename": "a.pdf", "page_number": 1, "chunk_index": 0}
    monkeypatch.setattr(document_agent, "hybrid_retrieve", lambda *a, **k: [chunk])
    monkeypatch.setattr(document_agent, "rerank", lambda q, c, top_n: c)
    fake_llm.responder = lambda p: (
        json.dumps({"subtasks": [{"agent": "document_agent", "priority": 1}]})
        if "routing orchestrator" in p else "No citation here [Source: other.pdf, Page 9]."
    )
    assert _chat(client, case_id)[-1]["sources"] == []


def test_follow_up_is_rewritten_with_history(client, case_id, fake_llm):
    _chat(client, case_id, "Who are the parties?")
    fake_llm.calls.clear()
    _chat(client, case_id, "and their addresses?")

    rewrite = [c for c in fake_llm.calls if "rewrite follow-up" in c]
    assert rewrite and "Who are the parties?" in rewrite[0]
    routing = [c for c in fake_llm.calls if "routing orchestrator" in c]
    assert "standalone question" in routing[0]


def test_first_message_skips_rewrite(client, case_id, fake_llm):
    _chat(client, case_id)
    assert not [c for c in fake_llm.calls if "rewrite follow-up" in c]


def test_multi_agent_answer_streams_document_section_first(client, case_id, fake_llm):
    fake_llm.responder = lambda p: (
        json.dumps({"subtasks": [
            {"agent": "analytics_agent", "query": "billing", "priority": 1},
            {"agent": "document_agent", "query": "facts", "priority": 2},
        ]})
        if "routing orchestrator" in p else "billing_totals" if "route billing" in p else "Answer text."
    )
    events = _chat(client, case_id)
    text = "".join(e["content"] for e in events if e["type"] == "token")

    assert text.startswith("## Document Analysis")
    assert text.index("## Document Analysis") < text.index("## Analytics & Billing")
    assert client.get(f"/cases/{case_id}/messages").json()[-1]["content"] == text


def test_routing_failure_falls_back_to_document_agent(client, case_id, fake_llm):
    fake_llm.responder = lambda p: "not json at all" if "routing orchestrator" in p else "ok"
    steps = [e["step"]["agent"] for e in _chat(client, case_id) if e["type"] == "agent_trace"]
    assert "document_agent" in steps


def test_orchestrator_crash_returns_friendly_error(client, case_id, monkeypatch):
    def broken(**kwargs):
        raise RuntimeError("internal detail")
        yield  # pragma: no cover

    monkeypatch.setattr(chat_route, "stream_events", broken)
    events = _chat(client, case_id)
    assert events[-1]["type"] == "error"
    assert "internal detail" not in events[-1]["content"]


def test_chat_does_not_block_other_requests(client, case_id, monkeypatch):
    def slow_events(**kwargs):
        time.sleep(1.5)
        yield {"type": "final", "response": "done", "agent_trace": [], "sources": [], "actions": []}

    monkeypatch.setattr(chat_route, "stream_events", slow_events)

    async def scenario():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            start = time.perf_counter()

            async def health():
                await asyncio.sleep(0.2)
                await ac.get("/health")
                return time.perf_counter() - start

            _, health_time = await asyncio.gather(
                ac.post("/chat", json={"content": "hi", "case_id": case_id}), health()
            )
            return health_time

    assert asyncio.run(scenario()) < 1.0
