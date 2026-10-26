"""The demo seed script creates a ready-to-use case and is idempotent."""

import pytest

from models.database import Billing, Case, Document, SessionLocal

pytestmark = pytest.mark.slow


def test_seed_demo_creates_ready_case(client):
    from scripts import seed_demo

    case_id = seed_demo.seed(reset=True)
    assert seed_demo.seed(reset=False) == case_id  # second run is a no-op

    db = SessionLocal()
    try:
        assert db.query(Case).filter(Case.name == seed_demo.DEMO_NAME).count() == 1
        docs = db.query(Document).filter(Document.case_id == case_id).all()
        assert {d.filename for d in docs} == {"Northwind-Quillon-NDA.pdf", "Northwind-Harbor-MSA.pdf"}
        assert all(d.status == "ready" and d.chunk_count for d in docs)
        assert db.query(Billing).filter(Billing.case_id == case_id, Billing.dispute_flag.is_(True)).count() == 1
    finally:
        db.close()

    # Seeded files are served to the viewer
    assert client.get(f"/uploads/{case_id}/Northwind-Quillon-NDA.pdf").status_code == 200

    new_id = seed_demo.seed(reset=True)
    assert new_id != case_id
    assert client.get(f"/cases/{case_id}").status_code == 404
