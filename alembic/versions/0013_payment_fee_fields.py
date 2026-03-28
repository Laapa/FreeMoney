"""add net fee gross amount fields for payments and topups

Revision ID: 0013
Revises: 0012
Create Date: 2026-03-28 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("payments") as batch_op:
        batch_op.add_column(sa.Column("net_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"))
        batch_op.add_column(sa.Column("fee_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"))
        batch_op.add_column(sa.Column("gross_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"))

    op.execute("UPDATE payments SET net_amount = amount, gross_amount = amount WHERE net_amount = 0 OR gross_amount = 0")

    with op.batch_alter_table("top_up_requests") as batch_op:
        batch_op.add_column(sa.Column("net_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"))
        batch_op.add_column(sa.Column("fee_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"))
        batch_op.add_column(sa.Column("gross_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"))
        batch_op.add_column(sa.Column("provider_payment_url", sa.String(length=1024), nullable=True))
        batch_op.add_column(sa.Column("provider_invoice_url", sa.String(length=1024), nullable=True))
        batch_op.add_column(sa.Column("provider_status", sa.String(length=64), nullable=True))

    op.execute("UPDATE top_up_requests SET net_amount = amount, gross_amount = amount WHERE net_amount = 0 OR gross_amount = 0")


def downgrade() -> None:
    with op.batch_alter_table("top_up_requests") as batch_op:
        batch_op.drop_column("provider_status")
        batch_op.drop_column("provider_invoice_url")
        batch_op.drop_column("provider_payment_url")
        batch_op.drop_column("gross_amount")
        batch_op.drop_column("fee_amount")
        batch_op.drop_column("net_amount")

    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_column("gross_amount")
        batch_op.drop_column("fee_amount")
        batch_op.drop_column("net_amount")
