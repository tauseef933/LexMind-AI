"""Track document ingestion status, error and chunk count; index case_id lookups

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-26
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        # Documents that existed before this migration were already ingested
        batch.add_column(sa.Column("status", sa.Text(), nullable=False, server_default="ready"))
        batch.add_column(sa.Column("error", sa.Text()))
        batch.add_column(sa.Column("chunk_count", sa.Integer()))
    op.create_index("ix_documents_case_id", "documents", ["case_id"])
    op.create_index("ix_messages_case_id", "messages", ["case_id"])
    op.create_index("ix_billing_case_id", "billing", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_billing_case_id", table_name="billing")
    op.drop_index("ix_messages_case_id", table_name="messages")
    op.drop_index("ix_documents_case_id", table_name="documents")
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("chunk_count")
        batch.drop_column("error")
        batch.drop_column("status")
