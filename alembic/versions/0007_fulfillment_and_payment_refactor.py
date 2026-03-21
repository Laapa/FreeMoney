"""fulfillment and payment refactor

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-21 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


fulfillment_type = sa.Enum("DIRECT_STOCK", "ACTIVATION_TASK", "MANUAL_SUPPLIER", name="fulfillmenttype")
fulfillment_status = sa.Enum("PENDING", "PROCESSING", "DELIVERED", "FAILED", "CANCELED", name="fulfillmentstatus")
payment_method = sa.Enum("CRYPTO_PAY", "BYBIT_UID", "TEST_STUB", name="paymentmethod")


def upgrade() -> None:
    bind = op.get_bind()
    fulfillment_type.create(bind, checkfirst=True)
    fulfillment_status.create(bind, checkfirst=True)
    payment_method.create(bind, checkfirst=True)

    with op.batch_alter_table("categories") as batch_op:
        batch_op.add_column(sa.Column("fulfillment_type", fulfillment_type, nullable=True))

    op.execute("UPDATE categories SET fulfillment_type = 'DIRECT_STOCK' WHERE fulfillment_type IS NULL")

    with op.batch_alter_table("categories") as batch_op:
        batch_op.alter_column("fulfillment_type", nullable=False)

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("bybit_uid", sa.String(length=32), nullable=True))

    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("fulfillment_type", fulfillment_type, nullable=True))
        batch_op.add_column(sa.Column("fulfillment_status", fulfillment_status, nullable=True))
        batch_op.add_column(sa.Column("external_task_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("supplier_note", sa.Text(), nullable=True))
        batch_op.alter_column("product_id", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column("reservation_id", existing_type=sa.Integer(), nullable=True)

    op.execute("UPDATE orders SET fulfillment_type = 'DIRECT_STOCK' WHERE fulfillment_type IS NULL")
    op.execute("UPDATE orders SET fulfillment_status = 'DELIVERED' WHERE status = 'DELIVERED'")
    op.execute("UPDATE orders SET fulfillment_status = 'CANCELED' WHERE status = 'CANCELED'")
    op.execute("UPDATE orders SET fulfillment_status = 'PENDING' WHERE fulfillment_status IS NULL")

    with op.batch_alter_table("orders") as batch_op:
        batch_op.alter_column("fulfillment_type", nullable=False)
        batch_op.alter_column("fulfillment_status", nullable=False)

    with op.batch_alter_table("payments") as batch_op:
        batch_op.add_column(sa.Column("method", payment_method, nullable=True))
        batch_op.add_column(sa.Column("provider", sa.String(length=64), nullable=True))

    op.execute("UPDATE payments SET method = 'TEST_STUB' WHERE method IS NULL")
    op.execute("UPDATE payments SET provider = 'test_stub' WHERE provider IS NULL")

    with op.batch_alter_table("payments") as batch_op:
        batch_op.alter_column("method", nullable=False)
        batch_op.alter_column("provider", nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_column("provider")
        batch_op.drop_column("method")

    with op.batch_alter_table("orders") as batch_op:
        batch_op.alter_column("reservation_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("product_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column("supplier_note")
        batch_op.drop_column("external_task_id")
        batch_op.drop_column("fulfillment_status")
        batch_op.drop_column("fulfillment_type")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("bybit_uid")

    with op.batch_alter_table("categories") as batch_op:
        batch_op.drop_column("fulfillment_type")

    bind = op.get_bind()
    payment_method.drop(bind, checkfirst=True)
    fulfillment_status.drop(bind, checkfirst=True)
    fulfillment_type.drop(bind, checkfirst=True)
