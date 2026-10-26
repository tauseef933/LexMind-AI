"""Alembic migrations: fresh install, upgrading a pre-migration DB, round trip."""

import sqlite3

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from config import BACKEND_ROOT


def _config(db_path) -> Config:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    return cfg


def test_fresh_database_upgrade_and_round_trip(tmp_path):
    db = tmp_path / "fresh.db"
    cfg = _config(db)
    command.upgrade(cfg, "head")

    insp = inspect(create_engine(f"sqlite:///{db.as_posix()}"))
    assert {"cases", "documents", "messages", "billing"} <= set(insp.get_table_names())
    assert {"status", "error", "chunk_count"} <= {c["name"] for c in insp.get_columns("documents")}

    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


def test_pre_migration_database_keeps_data(tmp_path, monkeypatch):
    """A DB created by the old create_all() is stamped and upgraded in place."""
    db = tmp_path / "legacy.db"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE cases (id TEXT PRIMARY KEY, name TEXT NOT NULL, client TEXT, court TEXT,
            hearing_date DATE, status TEXT, created_at DATETIME, updated_at DATETIME);
        CREATE TABLE documents (id TEXT PRIMARY KEY, case_id TEXT, filename TEXT NOT NULL,
            file_type TEXT, page_count INTEGER, ingested_at DATETIME);
        CREATE TABLE messages (id TEXT PRIMARY KEY, case_id TEXT, role TEXT, content TEXT,
            agent_trace TEXT, sources TEXT, created_at DATETIME);
        CREATE TABLE billing (id TEXT PRIMARY KEY, case_id TEXT, invoice_number TEXT, amount FLOAT,
            hours FLOAT, invoice_date DATE, dispute_flag BOOLEAN, dispute_reason TEXT, status TEXT);
        INSERT INTO cases (id, name) VALUES ('c1', 'Old case');
        INSERT INTO documents (id, case_id, filename) VALUES ('d1', 'c1', 'old.pdf');
    """)
    con.commit()
    con.close()

    from models import database

    monkeypatch.setattr(database, "DATABASE_URL", f"sqlite:///{db.as_posix()}")
    monkeypatch.setattr(database, "engine", create_engine(f"sqlite:///{db.as_posix()}"))
    database.init_db()
    database.init_db()  # idempotent

    con = sqlite3.connect(db)
    assert con.execute("SELECT name FROM cases").fetchall() == [("Old case",)]
    assert con.execute("SELECT filename, status FROM documents").fetchall() == [("old.pdf", "ready")]
    assert con.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0002"
