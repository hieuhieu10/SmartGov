"""Compatibility marker for existing local databases.

Revision ID: 20260717_0004
Revises: 20260717_0001
Create Date: 2026-07-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260717_0004"
down_revision: Union[str, None] = "20260717_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("documents")}
    if "folder_key" not in columns:
        op.add_column(
            "documents",
            sa.Column("folder_key", sa.String(length=255), nullable=False, server_default=""),
        )
    else:
        op.execute("update documents set folder_key = '' where folder_key is null")
        op.alter_column("documents", "folder_key", nullable=False, server_default="")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("documents")}
    if "folder_key" in columns:
        op.drop_column("documents", "folder_key")
