"""Schema compatibility marker for the retired provider cleanup."""

from typing import Sequence, Union

revision: str = "20260718_0009"
down_revision: Union[str, None] = "20260717_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
