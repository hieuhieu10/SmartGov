"""Remove retired NotebookLM and per-user engine metadata."""

from typing import Sequence, Union

from alembic import op

revision: str = "20260718_0009"
down_revision: Union[str, None] = "20260717_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("documents", "notebooklm_source_id")
    op.drop_column("repositories", "notebooklm_session_fingerprint")
    op.drop_column("repositories", "notebook_id")
    op.drop_column("users", "ai_engine")


def downgrade() -> None:
    from sqlalchemy import Column, String
    op.add_column("users", Column("ai_engine", String(50), nullable=True))
    op.add_column("repositories", Column("notebook_id", String(255), nullable=True))
    op.add_column("repositories", Column("notebooklm_session_fingerprint", String(128), nullable=True))
    op.add_column("documents", Column("notebooklm_source_id", String(255), nullable=True))
