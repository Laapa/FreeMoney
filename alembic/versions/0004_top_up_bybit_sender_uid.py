"""add sender uid field for bybit top ups

Revision ID: 0004_top_up_bybit_sender_uid
Revises: 0003_top_up_verification_fields
Create Date: 2026-03-17 02:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0004_top_up_bybit_sender_uid"
down_revision: Union[str, None] = "0003_top_up_verification_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("top_up_requests", sa.Column("sender_uid", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("top_up_requests", "sender_uid")
