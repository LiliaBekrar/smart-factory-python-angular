"""set server default on users.created_at and backfill"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20251016_users_created_at"
down_revision: Union[str, Sequence[str], None] = "20251016_merge_heads" 
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1) Backfill si des NULL existent déjà (sécurité)
    op.execute("UPDATE users SET created_at = NOW() WHERE created_at IS NULL;")
    # 2) Poser un DEFAULT côté Postgres pour les futurs INSERT
    op.alter_column(
        "users",
        "created_at",
        existing_type=sa.DateTime(),
        server_default=sa.text("NOW()"),
        existing_nullable=False,
    )

def downgrade() -> None:
    # Retirer seulement le default (on garde NOT NULL)
    op.alter_column(
        "users",
        "created_at",
        existing_type=sa.DateTime(),
        server_default=None,
        existing_nullable=False,
    )
