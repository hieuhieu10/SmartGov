"""Add immutable document version history."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260718_0009"
down_revision: Union[str, None] = "20260717_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("stored_path", sa.String(length=1000), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("file_type", sa.String(length=100), nullable=False, server_default=""),
        sa.Column(
            "changed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("changed_by_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("change_type", sa.String(length=50), nullable=False, server_default="edited"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])
    op.create_index("ix_document_versions_changed_by", "document_versions", ["changed_by"])
    op.create_index("ix_document_versions_created_at", "document_versions", ["created_at"])
    op.create_index(
        "ix_document_versions_doc_number",
        "document_versions",
        ["document_id", "version_number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_document_versions_doc_number", table_name="document_versions")
    op.drop_index("ix_document_versions_created_at", table_name="document_versions")
    op.drop_index("ix_document_versions_changed_by", table_name="document_versions")
    op.drop_index("ix_document_versions_document_id", table_name="document_versions")
    op.drop_table("document_versions")
