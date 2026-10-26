"""
Seed a demo case so the app has something to explore right away.

Creates "Northwind Analytics — Supplier Contracts (demo)" with:
  - two synthetic contracts (NDA + master services agreement), fully ingested
  - a few invoices, one disputed, for the billing agent

Uses the same database / vector store / uploads settings as the app.
Run from backend/ (or inside the container):

    python -m scripts.seed_demo            # skip if the demo case exists
    python -m scripts.seed_demo --reset    # delete and recreate it
"""

import argparse
import contextlib
import sys
import uuid
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402,F401 — load .env and resolve paths

from eval.corpus import DOCUMENTS, build_pdf  # noqa: E402
from models.database import Billing, Case, Document, Message, SessionLocal, init_db, utcnow  # noqa: E402
from rag.ingestion import ingest_document  # noqa: E402
from rag.vector_store import collection_name, get_client  # noqa: E402
from storage import stored_path  # noqa: E402

DEMO_NAME = "Northwind Analytics — Supplier Contracts (demo)"

INVOICES = [
    ("HFL-2025-07", 42_000, 0.0, date(2025, 7, 1), False, None, "paid"),
    ("HFL-2025-08", 42_000, 0.0, date(2025, 8, 1), False, None, "paid"),
    ("HFL-2025-09", 46_200, 0.0, date(2025, 9, 1), True,
     "Billed 10% above the agreed monthly fee without a signed statement of work", "disputed"),
    ("LEGAL-0112", 7_850, 23.5, date(2025, 9, 15), False, None, "pending"),
]


def _delete_existing(db) -> None:
    for case in db.query(Case).filter(Case.name == DEMO_NAME).all():
        for model in (Document, Message, Billing):
            db.query(model).filter(model.case_id == case.id).delete()
        with contextlib.suppress(Exception):  # no collection if nothing was ingested
            get_client().delete_collection(collection_name(case.id))
        db.delete(case)
    db.commit()


def seed(reset: bool) -> str:
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(Case).filter(Case.name == DEMO_NAME).first()
        if existing and not reset:
            print(f"Demo case already exists ({existing.id}). Use --reset to recreate it.")
            return existing.id
        _delete_existing(db)

        case_id = str(uuid.uuid4())
        db.add(Case(
            id=case_id,
            name=DEMO_NAME,
            client="Northwind Analytics Ltd.",
            court="ICDR New York (arbitration)",
            hearing_date=date(2026, 3, 16),
            status="active",
        ))
        for number, amount, hours, day, disputed, reason, status in INVOICES:
            db.add(Billing(case_id=case_id, invoice_number=number, amount=amount, hours=hours or None,
                           invoice_date=day, dispute_flag=disputed, dispute_reason=reason, status=status))
        db.commit()

        for filename, pages in DOCUMENTS.items():
            doc_id = str(uuid.uuid4())
            path = stored_path(case_id, doc_id, ".pdf")
            path.parent.mkdir(parents=True, exist_ok=True)
            build_pdf(path, pages)
            result = ingest_document(str(path), case_id, doc_id, filename=filename)
            db.add(Document(
                id=doc_id, case_id=case_id, filename=filename, file_type="pdf",
                page_count=result["page_count"], chunk_count=result["chunks_stored"],
                status="ready", ingested_at=utcnow(),
            ))
            print(f"  ingested {filename}: {result['page_count']} pages, {result['chunks_stored']} chunks")
        db.commit()

        print(f"Created demo case {case_id}")
        print("Try asking: 'What is the liability cap in each contract?' or "
              "'Which invoice is disputed and why?' or 'Schedule a prep meeting on 2 March 2026 at 10am'.")
        return case_id
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed a demo case.")
    parser.add_argument("--reset", action="store_true", help="delete and recreate the demo case")
    seed(parser.parse_args().reset)
