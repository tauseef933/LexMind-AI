"""
Document ingestion pipeline.

Flow:
  1. Extract text page-by-page with PyMuPDF (fitz).
  2. Fall back to Tesseract OCR for any blank pages (scanned images).
  3. Split text into chunks with RecursiveCharacterTextSplitter
     (chunk_size=500, overlap=50).
  4. Embed chunks with SentenceTransformer via embeddings.encode().
  5. Upsert into ChromaDB collection "case_{case_id}".
"""

import logging
import os
from pathlib import Path

import chromadb
import fitz  # PyMuPDF
import pytesseract
from langchain_text_splitters import RecursiveCharacterTextSplitter
from PIL import Image  # Pillow — bundled with pytesseract

from backend.rag.embeddings import encode

logger = logging.getLogger("lexmind.ingestion")

# ---------------------------------------------------------------------------
# ChromaDB client — persistent storage at CHROMA_PERSIST_PATH
# ---------------------------------------------------------------------------
_CHROMA_PATH = os.getenv("CHROMA_PERSIST_PATH", "./chroma_db")
_chroma_client = chromadb.PersistentClient(path=_CHROMA_PATH)

# ---------------------------------------------------------------------------
# Text splitter — shared across calls
# ---------------------------------------------------------------------------
_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    length_function=len,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _extract_pages(file_path: str) -> list[tuple[int, str]]:
    """
    Return a list of (page_number, text) tuples (1-indexed).
    Pages with no selectable text are OCR-ed via Tesseract.
    """
    doc = fitz.open(file_path)
    pages: list[tuple[int, str]] = []

    for page_num, page in enumerate(doc, start=1):
        text = page.get_text().strip()

        if not text:
            # Render page to image and run OCR
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(img).strip()

        formatted = f"[PAGE {page_num}]\n{text}\n" if text else ""
        pages.append((page_num, formatted))

    doc.close()
    return pages


def _get_or_create_collection(case_id: str) -> chromadb.Collection:
    collection_name = f"case_{case_id}"
    return _chroma_client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def ingest_document(
    file_path: str,
    case_id: str,
    doc_id: str,
) -> dict:
    """
    Ingest a document into the vector store.

    Parameters
    ----------
    file_path : str   Absolute path to the saved file.
    case_id   : str   UUID of the owning case.
    doc_id    : str   UUID of the document record in SQLite.

    Returns
    -------
    {"chunks_stored": N, "doc_id": doc_id}
    """
    filename = Path(file_path).name
    logger.info("Ingesting doc_id=%s  file=%s  case=%s", doc_id, filename, case_id)

    # 1. Extract pages
    pages = _extract_pages(file_path)

    # 2. Build full text with page markers, track page per character range
    all_text = ""
    page_boundaries: list[tuple[int, int, int]] = []  # (start_char, end_char, page_num)
    for page_num, page_text in pages:
        start = len(all_text)
        all_text += page_text
        end = len(all_text)
        page_boundaries.append((start, end, page_num))

    # 3. Split into chunks
    chunks = _splitter.split_text(all_text)
    if not chunks:
        logger.warning("No text extracted from %s", filename)
        return {"chunks_stored": 0, "doc_id": doc_id}

    # Helper: find which page a chunk's starting character falls on
    def _page_for_offset(offset: int) -> int:
        for start, end, page_num in page_boundaries:
            if start <= offset < end:
                return page_num
        return 1

    # Reconstruct chunk start offsets (approximate via cumulative search)
    chunk_offsets: list[int] = []
    cursor = 0
    for chunk in chunks:
        idx = all_text.find(chunk[:50], cursor)  # anchor on first 50 chars
        if idx == -1:
            idx = cursor
        chunk_offsets.append(idx)
        cursor = idx + len(chunk)

    # 4. Embed all chunks in one batch
    embeddings = encode(chunks)

    # 5. Upsert into ChromaDB
    collection = _get_or_create_collection(case_id)

    ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "doc_id": doc_id,
            "case_id": case_id,
            "chunk_index": i,
            "page_number": _page_for_offset(chunk_offsets[i]),
            "filename": filename,
        }
        for i in range(len(chunks))
    ]

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )

    logger.info("Stored %d chunks for doc_id=%s", len(chunks), doc_id)
    return {"chunks_stored": len(chunks), "doc_id": doc_id}


def delete_document_chunks(case_id: str, doc_id: str) -> int:
    """Remove all ChromaDB chunks for a document. Returns count deleted."""
    try:
        collection = _chroma_client.get_collection(f"case_{case_id}")
    except Exception:
        return 0

    results = collection.get(where={"doc_id": doc_id}, include=[])
    ids = results.get("ids") or []
    if ids:
        collection.delete(ids=ids)
        logger.info("Deleted %d chunks for doc_id=%s", len(ids), doc_id)
    return len(ids)
