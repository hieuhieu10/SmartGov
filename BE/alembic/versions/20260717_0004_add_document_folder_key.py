"""add document folder key

Revision ID: 20260717_0004
Revises: 20260717_0003
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260717_0004"
down_revision = "20260717_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("documents")}
    indexes = {index["name"] for index in inspector.get_indexes("documents")}

    if "folder_key" not in columns:
        op.add_column(
            "documents",
            sa.Column("folder_key", sa.String(length=80), nullable=False, server_default="draft"),
        )
        op.alter_column("documents", "folder_key", server_default=None)
    if "ix_documents_folder_key" not in indexes:
        op.create_index("ix_documents_folder_key", "documents", ["folder_key"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("documents")}
    indexes = {index["name"] for index in inspector.get_indexes("documents")}

    if "ix_documents_folder_key" in indexes:
        op.drop_index("ix_documents_folder_key", table_name="documents")
    if "folder_key" in columns:
        op.drop_column("documents", "folder_key")
