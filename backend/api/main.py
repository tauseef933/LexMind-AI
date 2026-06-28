import config  # noqa: F401 — load .env before anything reads env vars

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from api.middleware import (
    APIKeyMiddleware,
    LoggingMiddleware,
    get_allowed_origins,
)
from api.routes import analytics, cases, chat, documents
from config import UPLOADS_DIR, auth_enabled, get_secret_key
from models.database import init_db

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("lexmind")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="LexMind AI",
    description="Multi-Agent RAG System for Legal Professionals",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# Middleware  (order matters — added last executes first)
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(LoggingMiddleware)

if auth_enabled():
    app.add_middleware(APIKeyMiddleware, secret_key=get_secret_key())
    logger.info("API key auth enabled.")
else:
    logger.info("API key auth disabled (local dev).")

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
async def serve_upload(case_id: str, filename: str):
    file_path = UPLOADS_DIR / case_id / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    suffix = file_path.suffix.lower()
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
# Startup
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def on_startup() -> None:
    logger.info("Initialising database …")
    init_db()
    logger.info("LexMind AI ready.")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok"}
