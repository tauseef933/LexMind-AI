"""Pure helpers: JSON parsing, text splitting, PDF rendering, request IDs, API key guard."""

import fitz
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware import APIKeyMiddleware
from llm import get_llm, parse_json_response
from rag.text_splitter import split_text
from services.report_pdf import render_report_pdf


@pytest.mark.parametrize("raw, expected", [
    ('{"a": 1}', {"a": 1}),
    ('```json\n{"a": 1}\n```', {"a": 1}),
    ('Sure! Here you go: {"risks": []} Hope it helps.', {"risks": []}),
    ("[1, 2]", [1, 2]),
])
def test_parse_json_response(raw, expected):
    assert parse_json_response(raw) == expected


def test_parse_json_response_rejects_prose():
    with pytest.raises(ValueError):
        parse_json_response("no json here")


def test_llm_clients_are_cached_per_temperature():
    assert get_llm(0) is get_llm(0)
    assert get_llm(0) is not get_llm(0.2)


def test_split_text_short_and_empty():
    assert split_text("") == []
    assert split_text("short text") == ["short text"]


def test_split_text_respects_size_and_overlaps():
    text = " ".join(f"word{i}" for i in range(400))
    chunks = split_text(text, chunk_size=200, chunk_overlap=30)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)
    assert chunks[0][-10:].split()[-1] in chunks[1], "consecutive chunks should overlap"
    # Nothing is lost
    for i in (0, 199, 399):
        assert any(f"word{i}" in c for c in chunks)


def test_report_pdf_renders_and_escapes():
    pdf = render_report_pdf("Q3 <Risks> & Notes", "Smith v Jones", [
        {"heading": "Summary", "content": "First para.\n\n- point one\n- point two"},
    ])
    doc = fitz.open(stream=pdf, filetype="pdf")
    text = doc[0].get_text()
    assert "Q3 <Risks> & Notes" in text
    assert "Smith v Jones" in text and "point two" in text


def test_report_pdf_long_content_spans_pages():
    pdf = render_report_pdf("Long", "Case", [{"heading": "S", "content": "Line of text.\n" * 400}])
    assert fitz.open(stream=pdf, filetype="pdf").page_count > 1


def test_report_endpoint(client, case_id):
    r = client.post(f"/cases/{case_id}/reports/pdf", json={
        "title": "Risk report", "sections": [{"heading": "A", "content": "B"}]})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert 'filename="Risk-report.pdf"' in r.headers["content-disposition"]
    assert client.post(f"/cases/{case_id}/reports/pdf", json={"title": ""}).status_code == 422


def test_request_id_header(client):
    r = client.get("/health")
    assert len(r.headers["X-Request-ID"]) == 16
    assert client.get("/health", headers={"X-Request-ID": "trace-abc"}).headers["X-Request-ID"] == "trace-abc"
    # Junk IDs are replaced, not echoed back
    assert client.get("/health", headers={"X-Request-ID": "bad id\n"}).headers["X-Request-ID"] != "bad id\n"


def test_json_log_lines_carry_request_id_and_extras():
    import json
    import logging

    from logging_setup import JsonFormatter, request_id_var

    token = request_id_var.set("req-123")
    try:
        record = logging.LogRecord("lexmind", logging.INFO, __file__, 1, "GET %s", ("/health",), None)
        record.request_id = request_id_var.get()
        record.duration_ms = 4.2
        line = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)

    assert line["message"] == "GET /health"
    assert line["request_id"] == "req-123"
    assert line["duration_ms"] == 4.2
    assert line["level"] == "INFO"


def _guarded_app():
    app = FastAPI()
    app.add_middleware(APIKeyMiddleware, secret_key="s3cret")

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/cases")
    def cases():
        return []

    return TestClient(app)


def test_api_key_guard():
    c = _guarded_app()
    assert c.get("/health").status_code == 200
    assert c.get("/cases").status_code == 401
    assert c.get("/cases", headers={"X-API-Key": "wrong"}).status_code == 401
    assert c.get("/cases", headers={"X-API-Key": "s3cret"}).status_code == 200
    assert c.options("/cases").status_code != 401
