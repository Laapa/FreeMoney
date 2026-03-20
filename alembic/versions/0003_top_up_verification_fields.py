"""top up verification fields and log events

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-17 01:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE logeventtype ADD VALUE IF NOT EXISTS 'TOP_UP_VERIFIED'")
        op.execute("ALTER TYPE logeventtype ADD VALUE IF NOT EXISTS 'TOP_UP_REJECTED'")
        op.execute("ALTER TYPE logeventtype ADD VALUE IF NOT EXISTS 'TOP_UP_EXPIRED'")

    op.add_column("top_up_requests", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
    op.add_column("top_up_requests", sa.Column("verification_note", sa.Text(), nullable=True))
    op.add_column("top_up_requests", sa.Column("credited_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("top_up_requests", "credited_at")
    op.drop_column("top_up_requests", "verification_note")
    op.drop_column("top_up_requests", "reviewed_at")
