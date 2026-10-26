"""API schemas for documents."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: Optional[str]
    filename: str
    file_type: Optional[str]
    page_count: Optional[int]
    status: Optional[str] = None       # pending | processing | ready | failed
    error: Optional[str] = None
    chunk_count: Optional[int] = None
    ingested_at: datetime


class UploadOut(BaseModel):
    doc_id: str
    status: str
