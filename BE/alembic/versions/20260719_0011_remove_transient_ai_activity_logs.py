"""Remove the transient database AI-log table; logs are stored in .codex instead."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0011"
down_revision: Union[str, None] = "20260719_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("ai_activity_logs"):
        op.drop_table("ai_activity_logs")


def downgrade() -> None:
    # Không khôi phục bảng tạm vì log chuẩn được lưu trong thư mục dự án.
    pass
