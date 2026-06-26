"""Initial database schema for PI Vision AI MVP."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tables are created via SQLAlchemy models in init_db.py for MVP
    # This migration serves as version tracking for Alembic
    pass


def downgrade() -> None:
    pass
