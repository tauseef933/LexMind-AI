import logging
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from models.database import Case, Document, SessionLocal, get_db, utcnow
from models.document import DocumentOut, UploadOut
from rag.ingestion import delete_document_chunks, ingest_document
from storage import is_uuid, resolve_stored_file, stored_path

logger = logging.getLogger("lexmind.documents")

router = APIRouter(tags=["documents"])

# ---------------------------------------------------------------------------
# Config from env
# ---------------------------------------------------------------------------
_MAX_MB = float(os.getenv("MAX_FILE_SIZE_MB", "50"))
_MAX_BYTES = int(_MAX_MB * 1024 * 1024)

_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp"}


# ---------------------------------------------------------------------------
# Background ingestion — records progress on the document row
# ---------------------------------------------------------------------------
def _set_document_fields(doc_id: str, **fields: Any) -> None:
    db = SessionLocal()
    try:
        doc = db.get(Document, doc_id)
        if doc is None:  # deleted while ingesting
            return
        for name, value in fields.items():
            setattr(doc, name, value)
        db.commit()
    finally:
        db.close()


def _run_ingestion(file_path: str, case_id: str, doc_id: str, filename: str) -> None:
    _set_document_fields(doc_id, status="processing")
    try:
        result = ingest_document(file_path=file_path, case_id=case_id, doc_id=doc_id, filename=filename)
    except Exception:
        logger.exception("Ingestion failed for doc_id=%s", doc_id)
        _set_document_fields(doc_id, status="failed", error="Could not read this document.")
        return

    if result["chunks_stored"] == 0:
        _set_document_fields(
            doc_id,
            status="failed",
            error="No text could be extracted from this document.",
            page_count=result.get("page_count"),
            chunk_count=0,
        )
    else:
        _set_document_fields(
            doc_id,
            status="ready",
            error=None,
            page_count=result.get("page_count"),
            chunk_count=result["chunks_stored"],
        )


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/documents
# ---------------------------------------------------------------------------
@router.get("/cases/{case_id}/documents", response_model=list[DocumentOut])
def list_documents(case_id: str, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return (
        db.query(Document)
        .filter(Document.case_id == case_id)
        .order_by(Document.ingested_at.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# POST /upload
# ---------------------------------------------------------------------------
@router.post("/upload", response_model=UploadOut, status_code=202)
async def upload_document(
    case_id: str,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # Verify the case exists (ids are UUIDs — reject anything else early)
    case = db.query(Case).filter(Case.id == case_id).first() if is_uuid(case_id) else None
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Keep only the final path component of the client-supplied name
    original_name = Path((file.filename or "").replace("\\", "/")).name

    # Validate extension
    suffix = Path(original_name).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"File type '{suffix}' not allowed. Allowed: {sorted(_ALLOWED_EXTENSIONS)}",
        )

    # Read into memory to check size
    contents = await file.read()
    if len(contents) > _MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum allowed size of {_MAX_MB} MB",
        )

    # Determine stored file type
    file_type = suffix.lstrip(".")

    # Persist file to {PROJECT_ROOT}/uploads/{case_id}/{doc_id}{suffix}
    doc_id = str(uuid.uuid4())
    dest = stored_path(case_id, doc_id, suffix)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(contents)

    # Insert document row in SQLite (page_count filled after ingestion)
    doc = Document(
        id=doc_id,
        case_id=case_id,
        filename=original_name or f"upload{suffix}",
        file_type=file_type,
        page_count=None,
        status="pending",
        ingested_at=utcnow(),
    )
    db.add(doc)
    db.commit()

    # Kick off ingestion in the background
    background_tasks.add_task(
        _run_ingestion,
        file_path=str(dest.resolve()),
        case_id=case_id,
        doc_id=doc_id,
        filename=doc.filename,
    )

    logger.info("Upload accepted: doc_id=%s  file=%s  case=%s", doc_id, doc.filename, case_id)
    return UploadOut(doc_id=doc_id, status="ingestion_started")


# ---------------------------------------------------------------------------
# DELETE /cases/{case_id}/documents/{doc_id}
# ---------------------------------------------------------------------------
@router.delete("/cases/{case_id}/documents/{doc_id}", status_code=200)
def delete_document(case_id: str, doc_id: str, db: Session = Depends(get_db)):
    doc = (
        db.query(Document)
        .filter(Document.id == doc_id, Document.case_id == case_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove file from disk. Legacy uploads were stored under their original
    # name, so keep the file if another document of this case still uses it.
    file_path = resolve_stored_file(doc)
    if file_path is not None:
        shared = file_path.stem != doc.id and (
            db.query(Document)
            .filter(
                Document.case_id == case_id,
                Document.filename == doc.filename,
                Document.id != doc.id,
            )
            .first()
            is not None
        )
        if not shared:
            file_path.unlink()

    # Remove vector chunks
    chunks_deleted = delete_document_chunks(case_id, doc_id)

    db.delete(doc)
    db.commit()

    logger.info(
        "Deleted doc_id=%s  file=%s  case=%s  chunks=%d",
        doc_id, doc.filename, case_id, chunks_deleted,
    )
    return {"doc_id": doc_id, "status": "deleted", "chunks_removed": chunks_deleted}
