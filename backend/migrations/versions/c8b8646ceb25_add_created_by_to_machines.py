"""add created_by to machines

Revision ID: c8b8646ceb25
Revises: f03bd187e0ea
Create Date: 2025-09-06 19:18:10.005863

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8b8646ceb25'
down_revision: Union[str, Sequence[str], None] = 'f03bd187e0ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('machines', sa.Column('created_by', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_machines_created_by_users',
        'machines', 'users',
        ['created_by'], ['id'],
        ondelete='SET NULL'
    )

def downgrade() -> None:
    op.drop_constraint('fk_machines_created_by_users', 'machines', type_='foreignkey')
    op.drop_column('machines', 'created_by')
