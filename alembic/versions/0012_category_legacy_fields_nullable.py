"""make legacy category product fields optional

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-22 01:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("categories") as batch_op:
        batch_op.alter_column("fulfillment_type", existing_type=sa.Enum("DIRECT_STOCK", "ACTIVATION_TASK", "MANUAL_SUPPLIER", name="fulfillmenttype"), nullable=True)

    with op.batch_alter_table("products_pool") as batch_op:
        batch_op.alter_column("category_id", existing_type=sa.Integer(), nullable=True)



def downgrade() -> None:
    with op.batch_alter_table("products_pool") as batch_op:
        batch_op.alter_column("category_id", existing_type=sa.Integer(), nullable=False)

    op.execute("UPDATE categories SET fulfillment_type = 'DIRECT_STOCK' WHERE fulfillment_type IS NULL")
    with op.batch_alter_table("categories") as batch_op:
        batch_op.alter_column("fulfillment_type", existing_type=sa.Enum("DIRECT_STOCK", "ACTIVATION_TASK", "MANUAL_SUPPLIER", name="fulfillmenttype"), nullable=False)
