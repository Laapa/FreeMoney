"""add category reference to orders

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-21 00:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("category_id", sa.Integer(), nullable=True))
        batch_op.create_index(op.f("ix_orders_category_id"), ["category_id"], unique=False)
        batch_op.create_foreign_key("fk_orders_category_id", "categories", ["category_id"], ["id"])

    op.execute(
        """
        UPDATE orders
        SET category_id = (
            SELECT products_pool.category_id
            FROM products_pool
            WHERE products_pool.id = orders.product_id
        )
        WHERE orders.category_id IS NULL AND orders.product_id IS NOT NULL
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_constraint("fk_orders_category_id", type_="foreignkey")
        batch_op.drop_index(op.f("ix_orders_category_id"))
        batch_op.drop_column("category_id")
