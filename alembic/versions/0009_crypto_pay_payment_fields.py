"""add crypto pay payment fields

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-21 01:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("payments") as batch_op:
        batch_op.add_column(sa.Column("provider_payment_url", sa.String(length=1024), nullable=True))
        batch_op.add_column(sa.Column("provider_invoice_url", sa.String(length=1024), nullable=True))
        batch_op.add_column(sa.Column("provider_status", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_column("provider_status")
        batch_op.drop_column("provider_invoice_url")
        batch_op.drop_column("provider_payment_url")
