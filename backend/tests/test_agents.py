"""Agent-level behaviour: analytics scoping, action drafts, citation guard, services."""

import json

from agents import action_agent, analytics_agent, document_agent
from models.database import Billing, SessionLocal


def test_analytics_only_reads_the_active_case(case_id, client, fake_llm):
    other = client.post("/cases", json={"name": "Other"}).json()["id"]
    db = SessionLocal()
    db.add_all([
        Billing(case_id=case_id, invoice_number="MINE-1", amount=100),
        Billing(case_id=other, invoice_number="THEIRS-1", amount=999),
    ])
    db.commit()
    db.close()

    fake_llm.responder = lambda p: "list_invoices" if "route billing" in p else "Summary."
    result = analytics_agent.run("show invoices; DROP TABLE billing; also other cases", case_id)

    assert [r["invoice_number"] for r in result["data"]] == ["MINE-1"]
    assert result["report"] == "list_invoices"


def test_analytics_unknown_report_falls_back_to_totals(case_id, fake_llm):
    fake_llm.responder = lambda p: "SELECT * FROM messages" if "route billing" in p else "Summary."
    result = analytics_agent.run("anything", case_id)
    assert result["report"] == "billing_totals"
    assert "SELECT * FROM messages" not in result["sql"]


def test_every_analytics_query_is_case_scoped():
    for name, (_, sql) in analytics_agent.QUERIES.items():
        assert "case_id = :case_id" in sql, name


def test_calendar_action_is_structured(case_id, fake_llm):
    fake_llm.responder = lambda p: "calendar" if "classify" in p else (
        '```json\n{"title": "Prep", "start": "2026-11-03T10:00", "attendees": ["Alice", 7], '
        '"description": "Agenda", "unexpected": "dropped"}\n```'
    )
    result = action_agent.run("schedule prep on Nov 3 at 10", case_id)

    assert result["action_type"] == "calendar"
    assert result["action"] == {
        "title": "Prep", "start": "2026-11-03T10:00", "end": None, "location": "",
        "attendees": ["Alice", "7"], "description": "Agenda",
    }
    assert result["requires_confirmation"] is True
    assert "2026-11-03T10:00" in result["preview"]


def test_unknown_action_type_defaults_to_email(case_id, fake_llm):
    fake_llm.responder = lambda p: "teleport" if "classify" in p else json.dumps(
        {"to": "a@b.c", "subject": "Hi", "body": "Hello"})
    result = action_agent.run("do something", case_id)
    assert result["action_type"] == "email"
    assert result["action"] == {"to": "a@b.c", "subject": "Hi", "body": "Hello"}


def test_action_agent_failure_is_reported_not_raised(case_id, fake_llm):
    def boom(prompt):
        raise RuntimeError("down")

    fake_llm.responder = boom
    assert action_agent.run("email the client", case_id) == {
        "error": "Drafting the action failed.", "agent": "action_agent"}


def test_verify_sources_keeps_only_cited_chunks():
    chunks = [
        {"filename": "NDA.pdf", "page_number": 2},
        {"filename": "nda.pdf", "page_number": 3},
        {"filename": "memo.docx", "page_number": 1},
    ]
    answer = "Term [Source: nda.pdf, Page 2] and [source: MEMO.docx, page 1]."
    assert document_agent._verify_sources(answer, chunks) == [chunks[0], chunks[2]]


def test_services_fail_gracefully(case_id, fake_llm, monkeypatch):
    from services import case_summary, risk_detector, timeline_builder

    for mod in (case_summary, risk_detector, timeline_builder):
        monkeypatch.setattr(mod, "get_case_context", lambda case_id, **k: "context")

    def boom(prompt):
        raise RuntimeError("groq down")

    fake_llm.responder = boom
    assert risk_detector.detect_risks(case_id) == {"error": "Risk analysis failed.", "risks": []}
    assert case_summary.generate_summary(case_id) == {"error": "Summary generation failed."}
    assert timeline_builder.build_timeline(case_id) == []


def test_services_with_no_documents_skip_the_llm(case_id, fake_llm):
    from services import risk_detector

    assert risk_detector.detect_risks(case_id)["risks"] == []
    assert fake_llm.calls == []
