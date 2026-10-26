import config  # noqa: F401 — load .env before anything reads env vars

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.middleware import (
    APIKeyMiddleware,
    LoggingMiddleware,
    get_allowed_origins,
)
from api.rate_limit import RateLimitMiddleware
from api.routes import analytics, cases, chat, documents
from config import auth_enabled, get_secret_key
from logging_setup import configure_logging
from models.database import Document, get_db, init_db
from storage import resolve_stored_file

# ---------------------------------------------------------------------------
# Logging (LOG_FORMAT=json for structured logs; every line carries a request ID)
# ---------------------------------------------------------------------------
configure_logging()
logger = logging.getLogger("lexmind")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Initialising database …")
    init_db()
    logger.info("LexMind AI ready.")
    yield


app = FastAPI(
    title="LexMind AI",
    description="Multi-Agent RAG System for Legal Professionals",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware  (added last = outermost). Request flow:
#   LoggingMiddleware → CORSMiddleware → APIKeyMiddleware → RateLimitMiddleware → routes
# CORS wraps auth and rate limiting so 401/429 responses still carry CORS
# headers for the browser.
# ---------------------------------------------------------------------------
app.add_middleware(RateLimitMiddleware)

if auth_enabled():
    app.add_middleware(APIKeyMiddleware, secret_key=get_secret_key())
    logger.info("API key auth enabled.")
else:
    logger.info("API key auth disabled (local dev).")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Content-Disposition"],
)

app.add_middleware(LoggingMiddleware)

# ---------------------------------------------------------------------------
# File serving — uploaded documents for the document viewer
# ---------------------------------------------------------------------------
_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}


@app.get("/uploads/{case_id}/{filename}", tags=["uploads"])
def serve_upload(case_id: str, filename: str, db: Session = Depends(get_db)):
    # Only serve files that belong to a known document of this case.
    doc = (
        db.query(Document)
        .filter(Document.case_id == case_id, Document.filename == filename)
        .order_by(Document.ingested_at.desc())
        .first()
    )
    file_path = resolve_stored_file(doc) if doc else None
    if file_path is None:
        raise HTTPException(status_code=404, detail="File not found")
    suffix = Path(filename).suffix.lower()
    media_type = _MIME_TYPES.get(suffix, "application/octet-stream")
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
        content_disposition_type="inline",
    )

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(chat.router)
app.include_router(cases.router)
app.include_router(documents.router)
app.include_router(analytics.router)

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok"}
