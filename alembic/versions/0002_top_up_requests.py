"""add top up requests

Revision ID: 0002_top_up_requests
Revises: 0001_initial
Create Date: 2026-03-17 00:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0002_top_up_requests"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE logeventtype ADD VALUE IF NOT EXISTS 'TOP_UP_REQUEST_CREATED'")
        op.execute("ALTER TYPE logeventtype ADD VALUE IF NOT EXISTS 'TOP_UP_WAITING_VERIFICATION'")

    op.create_table(
        "top_up_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("method", sa.Enum("CRYPTO_TXID", "BYBIT_UID", name="topupmethod"), nullable=False),
        sa.Column(
            "amount",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column("currency", sa.Enum("RUB", "USD", name="currency"), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "WAITING_TXID",
                "WAITING_VERIFICATION",
                "VERIFIED",
                "REJECTED",
                "EXPIRED",
                name="topupstatus",
            ),
            nullable=False,
        ),
        sa.Column("txid", sa.String(length=255), nullable=True),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_top_up_requests_user_id"), "top_up_requests", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_top_up_requests_user_id"), table_name="top_up_requests")
    op.drop_table("top_up_requests")
