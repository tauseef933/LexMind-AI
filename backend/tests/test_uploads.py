"""Upload storage, path-traversal protection, file serving and ingestion status."""

import uuid

import pytest

import storage


def _upload(client, case_id, name="a.pdf", data=b"%PDF-1.4 test"):
    return client.post(f"/upload?case_id={case_id}", files={"file": (name, data, "application/pdf")})


def test_upload_stores_file_under_doc_id(client, case_id, no_ingest):
    r = _upload(client, case_id, name="../../evil.pdf")
    assert r.status_code == 202
    doc_id = r.json()["doc_id"]

    stored = storage.UPLOADS_DIR / case_id / f"{doc_id}.pdf"
    assert stored.is_file()
    assert not (storage.UPLOADS_DIR.parent / "evil.pdf").exists()
    # The original (sanitised) name is what users see
    docs = client.get(f"/cases/{case_id}/documents").json()
    assert docs[0]["filename"] == "evil.pdf"


def test_windows_style_traversal_name_is_flattened(client, case_id, no_ingest):
    _upload(client, case_id, name="..\\..\\boot.pdf")
    assert client.get(f"/cases/{case_id}/documents").json()[0]["filename"] == "boot.pdf"


@pytest.mark.parametrize("bad_case", ["../x", "not-a-uuid", str(uuid.uuid4())])
def test_upload_to_unknown_or_invalid_case_is_404(client, bad_case, no_ingest):
    assert _upload(client, bad_case).status_code == 404


def test_disallowed_extension_rejected(client, case_id):
    r = client.post(f"/upload?case_id={case_id}", files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 415


def test_serving_only_returns_files_of_that_case(client, case_id, no_ingest):
    _upload(client, case_id, name="mine.pdf")
    other = client.post("/cases", json={"name": "Other"}).json()["id"]

    assert client.get(f"/uploads/{case_id}/mine.pdf").status_code == 200
    for path in [
        f"/uploads/{other}/mine.pdf",
        f"/uploads/{case_id}/..%2Ftest.db",
        "/uploads/..%2F..%2F/test.db",
        "/uploads/%2E%2E/test.db",
    ]:
        assert client.get(path).status_code == 404, path


def test_delete_removes_file(client, case_id, no_ingest):
    doc_id = _upload(client, case_id).json()["doc_id"]
    assert client.delete(f"/cases/{case_id}/documents/{doc_id}").status_code == 200
    assert not list((storage.UPLOADS_DIR / case_id).glob("*.pdf"))


def test_successful_ingestion_marks_document_ready(client, case_id, no_ingest):
    _upload(client, case_id)
    doc = client.get(f"/cases/{case_id}/documents").json()[0]
    assert (doc["status"], doc["page_count"], doc["chunk_count"]) == ("ready", 2, 3)
    assert no_ingest[0]["filename"] == "a.pdf"


def test_failed_ingestion_hides_internal_error(client, case_id, monkeypatch):
    from api.routes import documents

    def boom(**kwargs):
        raise RuntimeError("secret stack detail")

    monkeypatch.setattr(documents, "ingest_document", boom)
    _upload(client, case_id)
    doc = client.get(f"/cases/{case_id}/documents").json()[0]
    assert doc["status"] == "failed"
    assert "secret" not in doc["error"]


def test_document_with_no_text_is_failed(client, case_id, monkeypatch):
    from api.routes import documents

    monkeypatch.setattr(
        documents, "ingest_document",
        lambda **k: {"chunks_stored": 0, "page_count": 1, "doc_id": k["doc_id"]},
    )
    _upload(client, case_id)
    doc = client.get(f"/cases/{case_id}/documents").json()[0]
    assert doc["status"] == "failed"
    assert "No text" in doc["error"]
