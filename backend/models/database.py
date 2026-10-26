import os
import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Optional

import config  # noqa: F401 — load .env before reading DATABASE_URL

from sqlalchemy import ForeignKey, Text, create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./lexmind.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # required for SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    type_annotation_map = {str: Text}


def utcnow() -> datetime:
    """Current UTC time as a naive datetime (SQLite stores no timezone)."""
    return datetime.now(UTC).replace(tzinfo=None)


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Table: cases
# ---------------------------------------------------------------------------
class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    name: Mapped[str]
    client: Mapped[Optional[str]]
    court: Mapped[Optional[str]]
    hearing_date: Mapped[Optional[date]]
    status: Mapped[Optional[str]] = mapped_column(default="active")
    created_at: Mapped[Optional[datetime]] = mapped_column(default=utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(default=utcnow, onupdate=utcnow)


# ---------------------------------------------------------------------------
# Table: documents
# ---------------------------------------------------------------------------
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    case_id: Mapped[Optional[str]] = mapped_column(ForeignKey("cases.id"), index=True)
    filename: Mapped[str]
    file_type: Mapped[Optional[str]]
    page_count: Mapped[Optional[int]]
    # pending | processing | ready | failed  (pre-existing rows default to ready)
    status: Mapped[str] = mapped_column(default="pending", server_default="ready")
    error: Mapped[Optional[str]]
    chunk_count: Mapped[Optional[int]]
    ingested_at: Mapped[Optional[datetime]] = mapped_column(default=utcnow)


# ---------------------------------------------------------------------------
# Table: messages
# ---------------------------------------------------------------------------
class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    case_id: Mapped[Optional[str]] = mapped_column(ForeignKey("cases.id"), index=True)
    role: Mapped[Optional[str]]
    content: Mapped[Optional[str]]
    agent_trace: Mapped[Optional[str]]   # JSON string
    sources: Mapped[Optional[str]]       # JSON string
    created_at: Mapped[Optional[datetime]] = mapped_column(default=utcnow)


# ---------------------------------------------------------------------------
# Table: billing
# ---------------------------------------------------------------------------
class Billing(Base):
    __tablename__ = "billing"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    case_id: Mapped[Optional[str]] = mapped_column(ForeignKey("cases.id"), index=True)
    invoice_number: Mapped[Optional[str]]
    amount: Mapped[Optional[float]]
    hours: Mapped[Optional[float]]
    invoice_date: Mapped[Optional[date]]
    dispute_flag: Mapped[Optional[bool]] = mapped_column(default=False)
    dispute_reason: Mapped[Optional[str]]
    status: Mapped[Optional[str]] = mapped_column(default="paid")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_db() -> Iterator[Session]:
    """FastAPI dependency — yields a database session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_BASELINE_REVISION = "0001"


def init_db() -> None:
    """Bring the database schema up to date by running Alembic migrations."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(config.BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

    # Databases created before migrations existed (via create_all) already
    # have the baseline tables — mark them as such instead of re-creating.
    insp = inspect(engine)
    if insp.has_table("cases") and not insp.has_table("alembic_version"):
        command.stamp(cfg, _BASELINE_REVISION)

    command.upgrade(cfg, "head")


# ---------------------------------------------------------------------------
# Allow running this file directly from any working directory:
#   python "d:\LexMind AI\lexmind-ai\backend\models\database.py"
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Put the backend/ directory on sys.path so sibling packages resolve.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    init_db()
    print("DB created OK")
