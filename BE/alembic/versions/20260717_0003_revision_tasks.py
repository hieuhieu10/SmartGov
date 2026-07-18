"""Add revision task workflow."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "20260717_0003"
down_revision = "20260717_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "revision_tasks" in inspector.get_table_names():
        return
    op.create_table(
        "revision_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("repo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("progress_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("reject_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("input_files", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("extracted_comments", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("diff_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("original_document_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("proposed_document_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("approved_document_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("original_file", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("proposed_file", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("final_file", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_revision_tasks_user_id", "revision_tasks", ["user_id"])
    op.create_index("ix_revision_tasks_repo_id", "revision_tasks", ["repo_id"])
    op.create_index("ix_revision_tasks_status", "revision_tasks", ["status"])
    op.create_index("ix_revision_user_created", "revision_tasks", ["user_id", "created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "revision_tasks" not in inspector.get_table_names():
        return
    op.drop_index("ix_revision_user_created", table_name="revision_tasks")
    op.drop_index("ix_revision_tasks_status", table_name="revision_tasks")
    op.drop_index("ix_revision_tasks_repo_id", table_name="revision_tasks")
    op.drop_index("ix_revision_tasks_user_id", table_name="revision_tasks")
    op.drop_table("revision_tasks")
