"""add index on production_events (machine_id, happened_at)

Revision ID: 7248ba2f79aa
Revises: 6eb33ce0a326
Create Date: 2025-08-29 17:44:19.199566
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "7248ba2f79aa"
down_revision: Union[str, Sequence[str], None] = "6eb33ce0a326"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_production_events_machine_happened",
        "production_events",
        ["machine_id", "happened_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_production_events_machine_happened",
        table_name="production_events",
    )
