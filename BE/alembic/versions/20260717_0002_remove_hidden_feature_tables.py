"""Remove DB tables for disabled drafting, template, and audio features."""

from alembic import op

revision = "20260717_0002"
down_revision = "20260717_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS template_tasks CASCADE")
    op.execute("DROP TABLE IF EXISTS draft_tasks CASCADE")
    op.execute("DROP TABLE IF EXISTS audio_tasks CASCADE")
    op.execute("DROP TABLE IF EXISTS document_templates CASCADE")


def downgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audio_tasks (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            filename VARCHAR(500) NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            progress_message TEXT NOT NULL DEFAULT '',
            error_message TEXT NOT NULL DEFAULT '',
            output_file VARCHAR(1000),
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_templates (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            template_file VARCHAR(1000) NOT NULL,
            source_file VARCHAR(1000) NOT NULL DEFAULT '',
            doc_type VARCHAR(100) NOT NULL DEFAULT '',
            placeholders JSONB NOT NULL DEFAULT '[]'::jsonb,
            template_structure JSONB NOT NULL DEFAULT '{}'::jsonb,
            status VARCHAR(50) NOT NULL DEFAULT 'analyzing',
            error_message TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS template_tasks (
            id UUID PRIMARY KEY,
            template_id UUID NOT NULL REFERENCES document_templates(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status VARCHAR(50) NOT NULL DEFAULT 'processing',
            progress_message TEXT NOT NULL DEFAULT '',
            error_message TEXT NOT NULL DEFAULT '',
            output_file VARCHAR(1000),
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS draft_tasks (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            repo_id UUID REFERENCES repositories(id) ON DELETE SET NULL,
            document_type VARCHAR(100) NOT NULL DEFAULT '',
            input_data JSONB NOT NULL DEFAULT '{}'::jsonb,
            draft_data JSONB NOT NULL DEFAULT '{}'::jsonb,
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            progress_message TEXT NOT NULL DEFAULT '',
            error_message TEXT NOT NULL DEFAULT '',
            output_file VARCHAR(1000),
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """
    )
