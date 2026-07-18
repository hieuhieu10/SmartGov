"""Add pgvector-backed document chunks for retrieval."""

from typing import Sequence, Union

from alembic import op

from app.db_models import DocumentChunk


revision: str = "20260717_0005"
down_revision: Union[str, None] = "20260717_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    DocumentChunk.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    DocumentChunk.__table__.drop(bind=bind, checkfirst=True)
