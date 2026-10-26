"""Initial schema: cases, documents, messages, billing

Revision ID: 0001
Revises:
Create Date: 2026-10-26
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cases",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("client", sa.Text()),
        sa.Column("court", sa.Text()),
        sa.Column("hearing_date", sa.Date()),
        sa.Column("status", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("case_id", sa.Text(), sa.ForeignKey("cases.id")),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("file_type", sa.Text()),
        sa.Column("page_count", sa.Integer()),
        sa.Column("ingested_at", sa.DateTime()),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("case_id", sa.Text(), sa.ForeignKey("cases.id")),
        sa.Column("role", sa.Text()),
        sa.Column("content", sa.Text()),
        sa.Column("agent_trace", sa.Text()),
        sa.Column("sources", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "billing",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("case_id", sa.Text(), sa.ForeignKey("cases.id")),
        sa.Column("invoice_number", sa.Text()),
        sa.Column("amount", sa.Float()),
        sa.Column("hours", sa.Float()),
        sa.Column("invoice_date", sa.Date()),
        sa.Column("dispute_flag", sa.Boolean()),
        sa.Column("dispute_reason", sa.Text()),
        sa.Column("status", sa.Text()),
    )


def downgrade() -> None:
    op.drop_table("billing")
    op.drop_table("messages")
    op.drop_table("documents")
    op.drop_table("cases")
