"""Add created_at columns to users, machines, and work_orders

Revision ID: 20251017_add_created_at_columns
Revises: 20251016_users_created_at
Create Date: 2025-10-17

Ajoute un timestamp automatique de création sur les principales tables métiers :
- users
- machines
- work_orders
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# Identifiants Alembic
revision = "20251017_add_created_at_columns"
down_revision = "20251016_users_created_at"  # adapte à ta dernière révision
branch_labels = None
depends_on = None


def upgrade():
    # === USERS ===================================================
    op.add_column(
        "users",
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )

    # === MACHINES ================================================
    op.add_column(
        "machines",
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )

    # === WORK_ORDERS =============================================
    op.add_column(
        "work_orders",
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )

    print("✅ Colonnes created_at ajoutées sur users, machines, work_orders.")


def downgrade():
    # suppression inverse (rollback)
    op.drop_column("work_orders", "created_at")
    op.drop_column("machines", "created_at")
    op.drop_column("users", "created_at")

    print("⏪ Colonnes created_at supprimées.")
