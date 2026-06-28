import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import UPLOADS_DIR
from models.database import Case, Document, get_db
from rag.ingestion import delete_document_chunks, ingest_document

logger = logging.getLogger("lexmind.documents")

router = APIRouter(tags=["documents"])

# ---------------------------------------------------------------------------
# Config from env
# ---------------------------------------------------------------------------
_MAX_MB = float(os.getenv("MAX_FILE_SIZE_MB", "50"))
_MAX_BYTES = int(_MAX_MB * 1024 * 1024)

_ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "image/jpeg": "jpeg",
    "image/png": "png",
    "image/tiff": "tiff",
    "image/webp": "webp",
}

_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp"}


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class DocumentOut(BaseModel):
    id: str
    case_id: Optional[str]
    filename: str
    file_type: Optional[str]
    page_count: Optional[int]
    ingested_at: datetime

    class Config:
        from_attributes = True


class UploadOut(BaseModel):
    doc_id: str
    status: str


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
    # Verify the case exists
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Validate extension
    suffix = Path(file.filename or "").suffix.lower()
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

    # Persist file to {PROJECT_ROOT}/uploads/{case_id}/
    upload_dir = UPLOADS_DIR / case_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / (file.filename or f"upload{suffix}")
    dest.write_bytes(contents)

    # Insert document row in SQLite (page_count filled after ingestion)
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        case_id=case_id,
        filename=file.filename or dest.name,
        file_type=file_type,
        page_count=None,
        ingested_at=datetime.utcnow(),
    )
    db.add(doc)
    db.commit()

    # Kick off ingestion in the background
    background_tasks.add_task(
        ingest_document,
        file_path=str(dest.resolve()),
        case_id=case_id,
        doc_id=doc_id,
    )

    logger.info("Upload accepted: doc_id=%s  file=%s  case=%s", doc_id, file.filename, case_id)
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

    # Remove file from disk
    file_path = UPLOADS_DIR / case_id / doc.filename
    if file_path.is_file():
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
