"""Compatibility revision retained for databases that applied the transient AI-log schema."""

from typing import Sequence, Union

revision: str = "20260719_0010"
down_revision: Union[str, None] = "20260718_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
