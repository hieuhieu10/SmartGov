"""add document folder key

Revision ID: 20260717_0003
Revises: 20260717_0002
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa


revision = "20260717_0003"
down_revision = "20260717_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("folder_key", sa.String(length=80), nullable=False, server_default="draft"),
    )
    op.create_index("ix_documents_folder_key", "documents", ["folder_key"])
    op.alter_column("documents", "folder_key", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_documents_folder_key", table_name="documents")
    op.drop_column("documents", "folder_key")
