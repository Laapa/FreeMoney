"""offer-based catalog refactor

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-22 00:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("categories") as batch_op:
        batch_op.add_column(sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "offers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("name_ru", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=False),
        sa.Column("description_ru", sa.Text(), nullable=True),
        sa.Column("description_en", sa.Text(), nullable=True),
        sa.Column("fulfillment_type", sa.Enum("DIRECT_STOCK", "ACTIVATION_TASK", "MANUAL_SUPPLIER", name="fulfillmenttype"), nullable=False),
        sa.Column("base_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_offers_category_id"), "offers", ["category_id"], unique=False)

    op.create_table(
        "user_offer_prices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["offer_id"], ["offers.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "offer_id", name="uq_user_offer_price"),
    )
    op.create_index(op.f("ix_user_offer_prices_user_id"), "user_offer_prices", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_offer_prices_offer_id"), "user_offer_prices", ["offer_id"], unique=False)

    with op.batch_alter_table("products_pool") as batch_op:
        batch_op.add_column(sa.Column("offer_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("offer_id", sa.Integer(), nullable=True))

    op.execute(
        """
        INSERT INTO offers (category_id, name_ru, name_en, description_ru, description_en, fulfillment_type, base_price, is_active, sort_order)
        SELECT id, name_ru, name_en, description_ru, description_en, fulfillment_type, base_price, is_active, 0
        FROM categories
        """
    )

    op.execute(
        """
        INSERT INTO user_offer_prices (user_id, offer_id, price)
        SELECT ucp.user_id, o.id, ucp.price
        FROM user_category_prices ucp
        JOIN offers o ON o.category_id = ucp.category_id
        """
    )

    op.execute(
        """
        UPDATE products_pool
        SET offer_id = (SELECT o.id FROM offers o WHERE o.category_id = products_pool.category_id LIMIT 1)
        WHERE offer_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE orders
        SET offer_id = (SELECT o.id FROM offers o WHERE o.category_id = orders.category_id LIMIT 1)
        WHERE offer_id IS NULL
        """
    )

    with op.batch_alter_table("products_pool") as batch_op:
        batch_op.alter_column("offer_id", nullable=False)
        batch_op.create_foreign_key("fk_products_pool_offer_id", "offers", ["offer_id"], ["id"])
        batch_op.create_index(op.f("ix_products_pool_offer_id"), ["offer_id"], unique=False)

    with op.batch_alter_table("orders") as batch_op:
        batch_op.alter_column("offer_id", nullable=False)
        batch_op.create_foreign_key("fk_orders_offer_id", "offers", ["offer_id"], ["id"])
        batch_op.create_index(op.f("ix_orders_offer_id"), ["offer_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_index(op.f("ix_orders_offer_id"))
        batch_op.drop_constraint("fk_orders_offer_id", type_="foreignkey")
        batch_op.drop_column("offer_id")

    with op.batch_alter_table("products_pool") as batch_op:
        batch_op.drop_index(op.f("ix_products_pool_offer_id"))
        batch_op.drop_constraint("fk_products_pool_offer_id", type_="foreignkey")
        batch_op.drop_column("offer_id")

    op.drop_index(op.f("ix_user_offer_prices_offer_id"), table_name="user_offer_prices")
    op.drop_index(op.f("ix_user_offer_prices_user_id"), table_name="user_offer_prices")
    op.drop_table("user_offer_prices")

    op.drop_index(op.f("ix_offers_category_id"), table_name="offers")
    op.drop_table("offers")

    with op.batch_alter_table("categories") as batch_op:
        batch_op.drop_column("sort_order")
