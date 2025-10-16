"""add unique constraint on users.email"""

from typing import Sequence, Union
from alembic import op

# Identifiants de migration
revision: str = "20251016_add_unique_users_email"
down_revision: Union[str, Sequence[str], None] = "6eb33ce0a326"  # ← ta dernière
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Ajoute une contrainte UNIQUE sur users.email."""
    op.create_unique_constraint("uq_users_email", "users", ["email"])


def downgrade() -> None:
    """Supprime la contrainte UNIQUE sur users.email."""
    op.drop_constraint("uq_users_email", "users", type_="unique")
