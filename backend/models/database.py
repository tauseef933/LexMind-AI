import os
import uuid
from datetime import datetime

import config  # noqa: F401 — load .env before reading DATABASE_URL

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./lexmind.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # required for SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Table: cases
# ---------------------------------------------------------------------------
class Case(Base):
    __tablename__ = "cases"

    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(Text, nullable=False)
    client = Column(Text)
    court = Column(Text)
    hearing_date = Column(Date)
    status = Column(Text, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# Table: documents
# ---------------------------------------------------------------------------
class Document(Base):
    __tablename__ = "documents"

    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(Text, ForeignKey("cases.id"))
    filename = Column(Text, nullable=False)
    file_type = Column(Text)
    page_count = Column(Integer)
    ingested_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Table: messages
# ---------------------------------------------------------------------------
class Message(Base):
    __tablename__ = "messages"

    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(Text, ForeignKey("cases.id"))
    role = Column(Text)
    content = Column(Text)
    agent_trace = Column(Text)   # JSON string
    sources = Column(Text)       # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Table: billing
# ---------------------------------------------------------------------------
class Billing(Base):
    __tablename__ = "billing"

    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(Text, ForeignKey("cases.id"))
    invoice_number = Column(Text)
    amount = Column(Float)
    hours = Column(Float)
    invoice_date = Column(Date)
    dispute_flag = Column(Boolean, default=False)
    dispute_reason = Column(Text)
    status = Column(Text, default="paid")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_db():
    """FastAPI dependency — yields a database session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables if they do not already exist."""
    Base.metadata.create_all(bind=engine)


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
