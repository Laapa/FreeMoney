"""add removed_from_pool flag to products_pool

Revision ID: 0015_pool_removed_flag
Revises: 0014_bybit_auto_verify_fields
Create Date: 2026-04-06 16:05:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0015_pool_removed_flag"
down_revision: str | None = "0014_bybit_auto_verify_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "products_pool",
        sa.Column("removed_from_pool", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("products_pool", "removed_from_pool", server_default=None)


def downgrade() -> None:
    op.drop_column("products_pool", "removed_from_pool")
