"""add admin catalog fields

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-22 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("categories") as batch_op:
        batch_op.add_column(sa.Column("description_ru", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("description_en", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("base_price", sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    with op.batch_alter_table("categories") as batch_op:
        batch_op.drop_column("is_active")
        batch_op.drop_column("base_price")
        batch_op.drop_column("description_en")
        batch_op.drop_column("description_ru")
