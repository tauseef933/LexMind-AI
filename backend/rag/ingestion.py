"""
Document ingestion pipeline.

Flow:
  1. Extract text page-by-page with PyMuPDF (fitz), or python-docx for .docx.
  2. Fall back to Tesseract OCR for any blank pages (scanned images).
  3. Split each page into chunks (chunk_size=500, overlap=50), so every
     chunk carries its exact page number for citations.
  4. Embed chunks via ONNX MiniLM (embeddings.encode).
  5. Upsert into ChromaDB collection "case_{case_id}".
"""

import logging
from pathlib import Path

import docx  # python-docx
import fitz  # PyMuPDF
from chromadb.api.types import Metadata
import pytesseract
from PIL import Image  # Pillow — bundled with pytesseract

from rag.embeddings import encode
from rag.retrieval import invalidate_case
from rag.text_splitter import split_text
from rag.vector_store import get_case_collection, get_or_create_case_collection

logger = logging.getLogger("lexmind.ingestion")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _extract_docx(file_path: str) -> list[tuple[int, str]]:
    """
    Word files have no fixed pages, so the whole document is page 1.
    Paragraphs and table rows are kept in document order.
    """
    document = docx.Document(file_path)
    lines: list[str] = []
    for block in document.element.body.iterchildren():
        tag = block.tag.rsplit("}", 1)[-1]
        if tag == "p":
            text = "".join(node.text or "" for node in block.iter() if node.tag.endswith("}t")).strip()
            if text:
                lines.append(text)
        elif tag == "tbl":
            for row in block.iter():
                if row.tag.endswith("}tr"):
                    cells = [
                        "".join(n.text or "" for n in cell.iter() if n.tag.endswith("}t")).strip()
                        for cell in row.iterchildren() if cell.tag.endswith("}tc")
                    ]
                    if any(cells):
                        lines.append(" | ".join(cells))
    text = "\n".join(lines)
    return [(1, f"[PAGE 1]\n{text}\n")] if text else [(1, "")]


def _extract_pages(file_path: str) -> list[tuple[int, str]]:
    """
    Return a list of (page_number, text) tuples (1-indexed).
    PDFs and images go through PyMuPDF; pages with no selectable text are
    OCR-ed via Tesseract. DOCX files are read with python-docx.
    """
    if Path(file_path).suffix.lower() == ".docx":
        return _extract_docx(file_path)

    doc = fitz.open(file_path)
    pages: list[tuple[int, str]] = []

    for page_num, page in enumerate(doc, start=1):
        text = page.get_text().strip()

        if not text:
            # Render page to image and run OCR
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            text = pytesseract.image_to_string(img).strip()

        formatted = f"[PAGE {page_num}]\n{text}\n" if text else ""
        pages.append((page_num, formatted))

    doc.close()
    return pages


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def ingest_document(
    file_path: str,
    case_id: str,
    doc_id: str,
    filename: str | None = None,
) -> dict:
    """
    Ingest a document into the vector store.

    Parameters
    ----------
    file_path : str   Absolute path to the saved file.
    case_id   : str   UUID of the owning case.
    doc_id    : str   UUID of the document record in SQLite.
    filename  : str   Original filename shown in citations (defaults to the
                      on-disk name).

    Returns
    -------
    {"chunks_stored": N, "page_count": P, "doc_id": doc_id}
    """
    filename = filename or Path(file_path).name
    logger.info("Ingesting doc_id=%s  file=%s  case=%s", doc_id, filename, case_id)

    # 1. Extract pages
    pages = _extract_pages(file_path)

    # 2–3. Split each page on its own so every chunk belongs to exactly one
    # page — citations then point at the right page in the viewer.
    chunks: list[str] = []
    chunk_pages: list[int] = []
    for page_num, page_text in pages:
        for chunk in split_text(page_text, chunk_size=500, chunk_overlap=50):
            chunks.append(chunk)
            chunk_pages.append(page_num)

    if not chunks:
        logger.warning("No text extracted from %s", filename)
        return {"chunks_stored": 0, "page_count": len(pages), "doc_id": doc_id}

    # 4. Embed all chunks in one batch
    embeddings = encode(chunks)

    # 5. Upsert into ChromaDB
    collection = get_or_create_case_collection(case_id)

    ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas: list[Metadata] = [
        {
            "doc_id": doc_id,
            "case_id": case_id,
            "chunk_index": i,
            "page_number": chunk_pages[i],
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

    invalidate_case(case_id)
    logger.info("Stored %d chunks for doc_id=%s", len(chunks), doc_id)
    return {"chunks_stored": len(chunks), "page_count": len(pages), "doc_id": doc_id}


def delete_document_chunks(case_id: str, doc_id: str) -> int:
    """Remove all ChromaDB chunks for a document. Returns count deleted."""
    collection = get_case_collection(case_id)
    if collection is None:
        return 0

    results = collection.get(where={"doc_id": doc_id}, include=[])
    ids = results.get("ids") or []
    if ids:
        collection.delete(ids=ids)
        invalidate_case(case_id)
        logger.info("Deleted %d chunks for doc_id=%s", len(ids), doc_id)
    return len(ids)
