"""Add cloud connection fields to cameras."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_camera_cloud"
down_revision: Union[str, None] = "002_rule_context"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cameras",
        sa.Column("connection_mode", sa.String(length=20), server_default="local", nullable=False),
    )
    op.add_column("cameras", sa.Column("device_serial", sa.String(length=64), nullable=True))
    op.alter_column("cameras", "ip_address", existing_type=sa.String(length=45), nullable=True)


def downgrade() -> None:
    op.alter_column("cameras", "ip_address", existing_type=sa.String(length=45), nullable=False)
    op.drop_column("cameras", "device_serial")
    op.drop_column("cameras", "connection_mode")
