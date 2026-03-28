"""add bybit auto verify bookkeeping fields

Revision ID: 0014
Revises: 0013
Create Date: 2026-03-28 00:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("top_up_requests") as batch_op:
        batch_op.add_column(sa.Column("verification_source", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("matched_provider_tx_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("last_auto_verify_attempt_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("last_auto_verify_note", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("top_up_requests") as batch_op:
        batch_op.drop_column("last_auto_verify_note")
        batch_op.drop_column("last_auto_verify_attempt_at")
        batch_op.drop_column("matched_provider_tx_id")
        batch_op.drop_column("verification_source")
