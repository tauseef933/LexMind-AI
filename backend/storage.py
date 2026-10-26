"""
Upload storage helpers.

Files are stored as  uploads/{case_id}/{doc_id}{suffix}  so that user-supplied
filenames never touch the filesystem path. The original filename lives only in
the documents table.
"""

from pathlib import Path
from typing import Optional
from uuid import UUID

from config import UPLOADS_DIR


def is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except (ValueError, TypeError):
        return False
    return True


def _inside_uploads(path: Path) -> bool:
    try:
        path.resolve().relative_to(UPLOADS_DIR.resolve())
    except ValueError:
        return False
    return True


def stored_path(case_id: str, doc_id: str, suffix: str) -> Path:
    """Path a new upload is written to. Both ids must be UUIDs."""
    if not (is_uuid(case_id) and is_uuid(doc_id)):
        raise ValueError("case_id and doc_id must be UUIDs")
    return UPLOADS_DIR / case_id / f"{doc_id}{suffix.lower()}"


def resolve_stored_file(doc) -> Optional[Path]:
    """
    Return the on-disk file for a Document row, or None.

    Falls back to the legacy layout (uploads/{case_id}/{original filename})
    for documents uploaded before ids were used as filenames.
    """
    if not doc.case_id or not is_uuid(doc.case_id):
        return None
    suffix = Path(doc.filename).suffix.lower()
    candidates = [
        UPLOADS_DIR / doc.case_id / f"{doc.id}{suffix}",
        UPLOADS_DIR / doc.case_id / Path(doc.filename).name,
    ]
    for path in candidates:
        if _inside_uploads(path) and path.is_file():
            return path
    return None
