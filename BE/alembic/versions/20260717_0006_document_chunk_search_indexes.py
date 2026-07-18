"""Add retrieval indexes for document chunks."""

from typing import Sequence, Union

from alembic import op


revision: str = "20260717_0006"
down_revision: Union[str, None] = "20260717_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw
        ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_document_chunks_fts
        ON document_chunks
        USING gin (
            to_tsvector('simple', coalesce(header_path, '') || ' ' || coalesce(chunk_text, ''))
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_fts")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
