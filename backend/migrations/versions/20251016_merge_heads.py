"""merge multiple heads into one"""

from typing import Sequence, Union

# Alembic identifiers
revision: str = "20251016_merge_heads"
down_revision: Union[str, Sequence[str], None] = (
    "20251016_add_unique_users_email",  # ← 1er head
    "c8b8646ceb25",                     # ← 2e head
)
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Merge-only migration: pas d'opérations, juste fusion des branches
    pass

def downgrade() -> None:
    # Rien à faire pour "dé-merger"
    pass
